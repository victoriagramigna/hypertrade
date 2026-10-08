"""
Punto de entrada principal del Radar de Mercado / HyperTrade (v3 + Radar
Score v2.1).

CAMBIOS v2.1:
- Distribution Days deja de multiplicar el Radar Score -- queda solo como
  badge de contexto (dist_days, mult_dist_badge siguen en el JSON para el
  dashboard, pero calcular_radar_score() ya no los usa para puntuar).
- La narrativa ahora recibe también SMA50 y SMA200 de cada ticker, para
  poder mostrar el valor exacto entre paréntesis en cada condición.
- Mi Cartera: seguimiento activo (trailing stop, objetivos, caída de
  Radar Score) + mail si hay algo nuevo para avisar.
- Seguimiento de precios de la bitácora, para el backtest futuro que
  compara radar-mercado (v1) vs. hypertrade (v2).
- Evaluación del sistema (una vez por semana, los viernes): responde si
  el Radar Score y sus señales individuales realmente anticipan un
  movimiento rentable, y si le ganan al mercado (alpha vs. SPY).
"""
import json
import logging
import math
import os
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

from config import (TICKERS, BENCHMARK, SCORE_MINIMO_ALERTA, MODO, VIX_TICKER,
                     UMBRAL_MOVIMIENTO_DIARIO_PCT, UMBRAL_CORRIDA_DEGRADADA_PCT)
from datos import traer_datos
from rs_score import calcular_rs_score
from alertas import detectar_alertas
from contexto import escanear_titulares, evaluar_contexto_macro, recomendacion_final
from regimen_mercado import evaluar_regimen_mercado
from historial import cargar_historial, guardar_historial
from telegram_bot import (notificar_alertas, notificar_datos_desactualizados, notificar_cambios_cuadrante,
                           notificar_golden_cross, notificar_squeeze)
from macro_local import traer_contexto_macro
from frescura import evaluar_frescura
from cedear_pricing import calcular_brechas_cedear
from movimientos import detectar_movimientos_diarios
from bitacora import registrar_eventos
from top30_nuevos import registrar_y_comparar_top30, registrar_y_comparar_top30_radar
from rs_deltas import registrar_y_calcular_deltas
from rebote_ema200 import detectar_rebote_ema200
from radar_score import calcular_radar_score
from narrativa import armar_narrativa
from senales_nuevas import calcular_distribution_days, multiplicador_distribution
from cartera_seguimiento import procesar_cartera
from seguimiento_precios import procesar_seguimiento
from evaluacion_sistema import evaluar_sistema
from auditoria import correr_auditoria
from regimen_score import calcular_regimen_score, contar_extremos_52w
from amplitud_historial import registrar_y_obtener_serie
from cuidados import puntos_de_cuidado
from confluencia import detectar_confluencia
from rotacion_sectorial import actualizar_rotacion_sectorial
from rotacion_ticker import actualizar_rotacion_ticker
from auditoria_rotacion import correr_auditoria_rotacion
from golden_cross import actualizar_golden_cross
from bollinger_squeeze import actualizar_squeeze
from zonas_smc import actualizar_zonas, guardar_zonas
from auditoria_golden_cross import correr_auditoria_golden_cross
from auditoria_squeeze import correr_auditoria_squeeze
from niveles_seguimiento import procesar_niveles

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("radar.main")


def limpiar_para_json(obj):
    if isinstance(obj, dict):
        return {k: limpiar_para_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [limpiar_para_json(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        valor = float(obj)
        return None if (math.isnan(valor) or math.isinf(valor)) else valor
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def traer_titulares_ejemplo():
    return []


def traer_vix(precios: dict):
    if VIX_TICKER in precios and not precios[VIX_TICKER].empty:
        return float(precios[VIX_TICKER].iloc[-1])
    return None


def estimar_proxima_corrida(ahora: datetime) -> str:
    candidato = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    for _ in range(24 * 8):
        es_habil = candidato.weekday() < 5
        en_horario = 14 <= candidato.hour <= 21
        if es_habil and en_horario:
            return candidato.isoformat()
        candidato += timedelta(hours=1)
    return None


def main():
    log.info(f"=== Radar de Mercado -- corrida iniciada (modo={MODO}) ===")
    ahora = datetime.now(timezone.utc)
    timestamp = ahora.isoformat()
    fecha_hoy = ahora.strftime("%Y-%m-%d")

    # 1. Datos
    tickers_a_pedir = {**TICKERS}
    precios, volumenes, precios_ohlc, fallidos, desactualizados = traer_datos(
        {**tickers_a_pedir, VIX_TICKER: "Índice"}, BENCHMARK)
    if BENCHMARK not in precios:
        log.error("El benchmark no se pudo traer -- abortando la corrida")
        return

    fallidos_universo = [f for f in fallidos if f["ticker"] in TICKERS]
    pct_fallidos = round(len(fallidos_universo) / len(TICKERS) * 100, 1) if TICKERS else 0
    corrida_degradada = pct_fallidos >= UMBRAL_CORRIDA_DEGRADADA_PCT
    if corrida_degradada:
        log.warning(f"CORRIDA DEGRADADA: falló el {pct_fallidos}% del universo "
                    f"({len(fallidos_universo)}/{len(TICKERS)}) -- se guarda igual, "
                    f"pero se saltea el envío de Telegram esta corrida")

    # 1b. Tickers con dato desactualizado (ver datos.py): no se calcula
    # ninguna señal para ellos en esta corrida, para no repetir el caso de
    # Gap alcista con el cierre del día hábil anterior.
    desactualizados_universo = [d for d in desactualizados if d["ticker"] in TICKERS]
    if desactualizados_universo:
        log.warning(f"{len(desactualizados_universo)} ticker(s) del universo quedaron desactualizados "
                    f"y se omiten de esta corrida: {[d['ticker'] for d in desactualizados_universo]}")

    # 2. Régimen de mercado (VIX)
    vix_actual = traer_vix(precios)
    regimen = evaluar_regimen_mercado(vix_actual)
    log.info(f"Régimen de mercado: {regimen}")

    # 2b. Frescura del dato
    ultima_fecha_benchmark = precios[BENCHMARK].dropna().index[-1] if not precios[BENCHMARK].dropna().empty else None
    frescura = evaluar_frescura(ultima_fecha_benchmark)
    log.info(f"Frescura del dato: {frescura}")

    # 2b-bis. Nunca retroceder: si Yahoo devuelve datos MÁS VIEJOS que los ya
    # guardados (ej. corrida de madrugada sin el cierre del día), se aborta
    # la corrida entera para no pisar el dato bueno -- caso real del 8/10:
    # MU pasó de 1088 (cierre del 7/10) a 1045,56 (cierre del 6/10).
    try:
        if frescura.get("fecha_ultimo_dato") and os.path.exists("data/ultimo.json"):
            with open("data/ultimo.json", "r", encoding="utf-8") as f_prev:
                fecha_prev = (json.load(f_prev).get("frescura_dato") or {}).get("fecha_ultimo_dato")
            if fecha_prev and frescura["fecha_ultimo_dato"] < fecha_prev:
                log.warning(f"Dato más viejo ({frescura['fecha_ultimo_dato']}) que el ya guardado ({fecha_prev}) "
                            f"-- se aborta la corrida para no retroceder")
                return
    except Exception as e:
        log.warning(f"No se pudo comparar con el dato guardado ({e}); sigo normal")

    # 2c. Distribution Days -- v2.1: SOLO informativo (badge), ya no
    # multiplica el Radar Score (ver radar_score.py). Se sigue calculando
    # y guardando en el JSON para que el dashboard lo muestre.
    dist_days = calcular_distribution_days(precios[BENCHMARK], volumenes[BENCHMARK])
    mult_dist_badge = multiplicador_distribution(dist_days)  # solo para colorear el badge

    # Régimen de mercado 0-100 (clima general para comprar). NO toca el
    # Radar Score de cada ticker -- se muestra aparte, se agrega como
    # dato a cada alerta y se guarda en la bitácora para la Auditoría.
    try:
        regimen_score = calcular_regimen_score(precios, list(TICKERS), vix_actual, dist_days)
    except Exception as e:
        log.error(f"Régimen de mercado 0-100 falló, no afecta al resto de la corrida: {e}")
        regimen_score = None
    log.info(f"Distribution Days (25 ruedas): {dist_days} -- (informativo, ya no penaliza el score)")

    # 2a. Nuevos máximos/mínimos de 52 semanas hoy + historial de amplitud
    # para graficar la tendencia -- puramente informativo, no afecta el
    # Régimen Score ni ningún otro cálculo (ver charla con Victoria, 30/9,
    # comparando contra otro panel de régimen de mercado).
    try:
        extremos_52w = contar_extremos_52w(precios, precios_ohlc, list(TICKERS))
    except Exception as e:
        log.error(f"Nuevos máximos/mínimos 52w falló, no afecta al resto de la corrida: {e}")
        extremos_52w = None

    if corrida_degradada or regimen_score is None:
        # Igual que el Top 30 nuevo y el Δ RS: con medio universo caído no
        # se guarda la foto, para no ensuciar el historial con un dato
        # armado con datos incompletos.
        amplitud_historial = []
    else:
        try:
            amplitud_historial = registrar_y_obtener_serie(
                regimen_score.get("amplitud_sma50_pct"),
                regimen_score.get("amplitud_sma200_pct"),
                fecha_hoy,
            )
        except Exception as e:
            log.error(f"Historial de amplitud falló, no afecta al resto de la corrida: {e}")
            amplitud_historial = []

    # 3. RS Score + indicadores completos
    df_rs = calcular_rs_score(precios, TICKERS, BENCHMARK, volumenes, precios_ohlc)
    rs_por_sector = df_rs.groupby("Sector")["RS_Score"].mean().to_dict() if not df_rs.empty else {}
    rs_por_ticker = dict(zip(df_rs["Ticker"], df_rs["RS_Score"])) if not df_rs.empty else {}

    # 3a. Cuadrante de Rotación Sectorial (Líder/Mejorando/Debilitándose/
    # Rezagado) -- no se calcula de nuevo nada, usa el rs_por_sector de
    # arriba. Si un sector cambia de cuadrante, queda logueado para que
    # auditoria_rotacion.py lo pueda medir más adelante (ver módulo).
    try:
        rotacion_sectorial, eventos_rotacion_sectorial = actualizar_rotacion_sectorial(rs_por_sector, TICKERS, ahora)
    except Exception as e:
        log.error(f"Rotación sectorial falló, no afecta al resto de la corrida: {e}")
        rotacion_sectorial, eventos_rotacion_sectorial = [], []

    # 3a-bis. Radar Score v2.1 (compuesto 0-100 -- Distribution Days ya NO
    # se pasa acá, ver nota arriba)
    bench_close = precios[BENCHMARK].dropna()
    spy_sma50 = bench_close.rolling(50).mean().iloc[-1] if len(bench_close) >= 50 else None
    spy_sobre_sma50 = bool(bench_close.iloc[-1] > spy_sma50) if spy_sma50 is not None and not math.isnan(spy_sma50) else True
    df_rs = calcular_radar_score(df_rs, rs_por_sector, spy_sobre_sma50, regimen, precios_ohlc)

    # 3a-ter. Δ del RS Score (día/semana/mes) -- igual que el Top 30 nuevo,
    # en una corrida degradada no se guarda la foto (el RS no es confiable
    # con medio universo caído).
    rs_deltas_por_ticker = {} if corrida_degradada else registrar_y_calcular_deltas(df_rs, fecha_hoy)
    if rs_deltas_por_ticker and not df_rs.empty:
        df_rs["Delta_RS_dia"] = df_rs["Ticker"].map(lambda t: rs_deltas_por_ticker.get(t, {}).get("Delta_RS_dia"))
        df_rs["Delta_RS_semana"] = df_rs["Ticker"].map(lambda t: rs_deltas_por_ticker.get(t, {}).get("Delta_RS_semana"))
        df_rs["Delta_RS_mes"] = df_rs["Ticker"].map(lambda t: rs_deltas_por_ticker.get(t, {}).get("Delta_RS_mes"))

    # 3a-quater. Cuadrante de Rotación por TICKER (Líder/Mejorando/
    # Debilitándose/Rezagado) -- misma idea que la Rotación Sectorial de
    # 3a, pero para cada ticker individual en vez del promedio del sector
    # (pedido de Victoria, 2/10, viendo la versión "Warren Bife" con
    # buscador de ticker). Reutiliza Delta_RS_semana, que recién se
    # calculó arriba -- no agrega ningún cálculo nuevo. Si Delta_RS_semana
    # no está disponible (corrida degradada, o todavía no hay 1 semana de
    # historial), simplemente no hay cuadrante por ticker todavía.
    try:
        rotacion_ticker = actualizar_rotacion_ticker(df_rs, ahora)
    except Exception as e:
        log.error(f"Rotación por ticker falló, no afecta al resto de la corrida: {e}")
        rotacion_ticker = {"puntos": [], "recien_a_lideres": [], "aceleracion_inusual": [], "eventos": []}

    # 3a-quinquies. Golden Cross / Death Cross (SMA50 vs. SMA200, con
    # confirmación con demora -- ver golden_cross.py) y Squeeze de
    # Bollinger (compresión + liberación con volumen -- ver
    # bollinger_squeeze.py). Las dos reutilizan columnas que rs_score.py
    # YA calcula para todo el universo (SMA50/SMA200/BB_*), no agregan
    # ningún cálculo de precio nuevo. Cada una con su propio estado y
    # bitácora, totalmente separadas de la Auditoría de siempre -- ver
    # charla con Victoria sobre Beta/Golden-Cross/Squeeze.
    try:
        golden_cross = actualizar_golden_cross(df_rs, ahora)
    except Exception as e:
        log.error(f"Golden/Death Cross falló, no afecta al resto de la corrida: {e}")
        golden_cross = {"puntos": [], "eventos": []}

    try:
        squeeze = actualizar_squeeze(df_rs, ahora)
    except Exception as e:
        log.error(f"Squeeze de Bollinger falló, no afecta al resto de la corrida: {e}")
        squeeze = {"puntos": [], "eventos": []}

    # 3a-sexies. Zonas de oferta/demanda (Order Blocks) y FVG -- replica del
    # indicador All-in-One Pro de Victoria (ver zonas_smc.py). ADITIVO: no
    # toca el Radar Score, las alertas ni la Auditoría; solo informa. Si
    # falla, no tumba la corrida.
    try:
        zonas = actualizar_zonas(df_rs, precios_ohlc, ahora)
    except Exception as e:
        log.error(f"Zonas oferta/demanda falló, no afecta al resto de la corrida: {e}")
        zonas = {"puntos": [], "eventos": [], "estado": {}}

    # 3b. Señal de CEDEAR caro/barato
    precios_usd_actuales = dict(zip(df_rs["Ticker"], df_rs["Precio"])) if not df_rs.empty else {}
    # El benchmark (SPY) nunca aparece en df_rs -- no tiene sentido rankearlo
    # contra sí mismo -- pero sí tiene CEDEAR propio y ratio configurado
    # (RATIOS_CEDEAR), así que sin este agregado quedaba afuera del panel de
    # CEDEAR caro/barato y de "Balance real" en Mi Cartera. Solo se agrega acá,
    # a esta copia local del dict: no toca df_rs ni ningún otro cálculo (RS
    # Score, Alertas, Auditoría siguen exactamente igual que antes).
    if not bench_close.empty:
        precios_usd_actuales[BENCHMARK] = float(bench_close.iloc[-1])
    cedears_pricing = calcular_brechas_cedear(precios_usd_actuales)
    log.info(f"CEDEARs -- CCL: {cedears_pricing.get('ccl')}, "
             f"{len(cedears_pricing.get('cedears', []))} calculados")

    # 3c. Panel de movimientos diarios inusuales
    movimientos_dia = detectar_movimientos_diarios(precios, TICKERS)
    log.info(f"Movimientos del día: {len(movimientos_dia)} ticker(s) con variación >= "
             f"{UMBRAL_MOVIMIENTO_DIARIO_PCT}%")

    # 4. Historial persistente
    historial = cargar_historial()

    # 5. Alertas técnicas
    df_alertas, historial = detectar_alertas(precios, volumenes, TICKERS, BENCHMARK,
                                              rs_por_sector, rs_por_ticker, historial,
                                              fecha_hoy, timestamp, precios_ohlc)
    guardar_historial(historial)

    # 5b. Confluencia Alcista -- filtro duro sobre chips que YA se calculan
    # para todo el universo (AVWAP SOPORTE, CRUCE 52W, TENDENCIA+, ATR
    # COMPRIMIDO), ignorando a propósito el Radar Score (ver confluencia.py
    # para la lógica completa). Se suma a df_alertas para pasar por el
    # MISMO camino de siempre (recomendación, cuidados, narrativa,
    # notificación, bitácora, Auditoría) -- no es un sistema paralelo.
    try:
        filas_confluencia = detectar_confluencia(df_rs, ahora)
        if filas_confluencia:
            df_alertas = pd.concat([df_alertas, pd.DataFrame(filas_confluencia)], ignore_index=True)
        log.info(f"Confluencia Alcista: {len(filas_confluencia)} ticker(s) con 3+ señales en las últimas 48hs")
    except Exception as e:
        log.error(f"Confluencia Alcista falló, no afecta al resto de la corrida: {e}")

    # 6. Contexto (noticias + macro-local)
    titulares = traer_titulares_ejemplo()
    alertas_sector = escanear_titulares(titulares)
    riesgo_pais, riesgo_pais_ayer, brecha = traer_contexto_macro()
    contexto_macro = evaluar_contexto_macro(riesgo_pais, riesgo_pais_ayer, brecha)
    log.info(f"Contexto macro-local: {contexto_macro}")

    # 7. Recomendación final
    radar_score_por_ticker = dict(zip(df_rs["Ticker"], df_rs["Radar_Score"])) if not df_rs.empty else {}
    dist_52w_por_ticker = dict(zip(df_rs["Ticker"], df_rs["Dist_Max52w_%"])) if not df_rs.empty else {}

    bench_close_serie = precios[BENCHMARK].dropna()
    var_spy_dia_pct = None
    if len(bench_close_serie) >= 2:
        var_spy_dia_pct = round((bench_close_serie.iloc[-1] / bench_close_serie.iloc[-2] - 1) * 100, 2)

    # Columnas de df_rs que hay que traspasar a cada alerta a mano (df_rs
    # es el universo completo; df_alertas es un subconjunto sin estas
    # columnas nuevas). v2.1: se suman SMA50 y SMA200 para que la
    # narrativa pueda mostrar el valor exacto de cada condición.
    columnas_extra_narrativa = [
        "RS_Score", "VCP_valido", "Sobre_SMA50", "Dist_SMA200_%", "Dist_SMA50_%",
        "SMA50", "SMA200",
        "AVWAP_YTD", "AVWAP_52W_High", "AVWAP_Ultimo_Gap", "Apoyo_AVWAP",
        "ATR_Ratio", "ATR_Contraction", "Pendiente_OK", "Cruce_AVWAP_52w",
        # RS Score contra el sector (además del RS Score contra el mercado
        # de siempre) -- ver rs_score.py. Puramente informativo, no toca
        # ninguna cuenta existente.
        "RS_Score_Sector", "Perfil_Fuerza",
        # Tendencia Semanal (RSI+MACD) -- ver tendencia_semanal.py. También
        # puramente informativa: no toca el Score ni la Recomendación de
        # ninguna alerta, solo viaja junto para mostrarse y auditarse aparte.
        "Tendencia_Semanal", "RSI_Semanal", "MACD_Semanal", "MACD_Señal_Semanal",
        # Subcategoría (ver config.py/rs_score.py) -- faltaba en esta lista,
        # por eso no aparecía en las tarjetas de Alertas aunque el HTML ya
        # estaba listo para mostrarla (bug encontrado 1/10): en el Top 30 y
        # en el buscador de tickers SÍ se veía, porque esas dos pantallas
        # leen directo de df_rs (el universo completo), que siempre la tuvo.
        # Puramente informativa, igual que las de arriba.
        "Subcategoria",
        # Los 6 ingredientes del Radar Score, por separado -- ver
        # radar_score.py. Mismo motivo que todo lo de arriba: existían pero
        # no llegaban a la tarjeta de Alertas (bug encontrado 1/10).
        "Radar_Comp_FR", "Radar_Comp_Contraccion", "Radar_Comp_Volumen",
        "Radar_Comp_Tendencia", "Radar_Comp_AVWAP", "Radar_Comp_52w",
        "Radar_Bono_Cruce",
        # Beta vs. SPY y Bollinger Bands (ver rs_score.py) -- puramente
        # informativas, no tocan el Radar Score ni la Recomendación de
        # ninguna alerta, solo viajan junto para mostrarse en la tarjeta.
        "Beta", "BB_SMA20", "BB_Upper", "BB_Lower", "BB_Bandwidth_%", "Squeeze_Comprimido",
    ]
    columnas_extra_presentes = [c for c in columnas_extra_narrativa if c in df_rs.columns]
    extras_por_ticker = (
        df_rs.set_index("Ticker")[columnas_extra_presentes].to_dict(orient="index")
        if not df_rs.empty and columnas_extra_presentes else {}
    )

    recomendaciones = []
    for _, fila in df_alertas.iterrows():
        rec = recomendacion_final(fila["Sector"], fila["Score_num"], fila["Estado"],
                                   alertas_sector, contexto_macro)
        if not regimen.get("sin_datos") and not regimen.get("sano") and rec["Recomendación final"] == "COMPRA":
            rec["Recomendación final"] = "MANTENER"
            rec["Ajustado por"] += f"; régimen de mercado volátil ({regimen['motivo']})"
        rec["Radar_Score"] = radar_score_por_ticker.get(fila["Ticker"])
        rec["Dist_Max52w_%"] = dist_52w_por_ticker.get(fila["Ticker"])
        rec["RS_sector"] = round(rs_por_sector[fila["Sector"]], 1) if fila["Sector"] in rs_por_sector else None
        rec["Var_SPY_dia_%"] = var_spy_dia_pct
        rec["Regimen_Score"] = regimen_score["score"] if regimen_score else None

        fila_completa = {**fila.to_dict(), **rec, **extras_por_ticker.get(fila["Ticker"], {})}
        # Puntos de cuidado: lo que está EN CONTRA de una alerta alcista
        # (SMA50 bajando, techo en el AVWAP del máximo, extensión, etc.)
        try:
            cuid = puntos_de_cuidado(fila_completa, precios.get(fila["Ticker"]))
        except Exception as e:
            log.debug(f"Puntos de cuidado de {fila['Ticker']} fallaron: {e}")
            cuid = []
        fila_completa["Cuidados"] = [c["texto"] for c in cuid]
        fila_completa["Cuidados_claves"] = [c["clave"] for c in cuid]
        fila_completa["Narrativa"] = armar_narrativa(fila_completa, dist_days, mult_dist_badge, regimen.get("sano", True),
                                                     regimen_score)
        recomendaciones.append(fila_completa)

    # 7b. Nuevos ingresos diarios al Top 30 de RS Score -- igual que la
    # foto semanal de Auditoría, en una corrida degradada NO se guarda
    # (el RS no es confiable con medio universo caído), para no ensuciar
    # el historial con un Top 30 armado con datos incompletos.
    top30_nuevos_hoy = ({"nuevos": [], "salientes": [], "fecha_comparacion": None}
                         if corrida_degradada
                         else registrar_y_comparar_top30(df_rs, fecha_hoy))

    # 7c. Mismo mecanismo, ahora para el Top 30 por RADAR SCORE (el
    # compuesto con volumen/tendencia/AVWAP/52w, no la Fuerza Relativa) --
    # a pedido de Victoria (1/10), con las mismas características que el
    # de arriba: nuevos ingresos/salientes diarios.
    top30_radar_nuevos_hoy = ({"nuevos": [], "salientes": [], "fecha_comparacion": None}
                               if corrida_degradada
                               else registrar_y_comparar_top30_radar(df_rs, fecha_hoy))

    # 8. Guardar resultado para el dashboard
    salida = {
        "generado_utc": timestamp,
        "proxima_corrida_estimada_utc": estimar_proxima_corrida(ahora),
        "tickers_ok": len(precios) - 2,
        "tickers_fallidos": fallidos,
        "pct_fallidos": pct_fallidos,
        "corrida_degradada": corrida_degradada,
        "tickers_desactualizados": desactualizados_universo,
        "frescura_dato": frescura,
        "ranking": df_rs.to_dict(orient="records") if not df_rs.empty else [],
        "rs_por_sector": rs_por_sector,
        "rotacion_sectorial": rotacion_sectorial,
        "rotacion_ticker": rotacion_ticker,
        "golden_cross": golden_cross["puntos"],
        "squeeze": squeeze["puntos"],
        "zonas": zonas["puntos"],
        "regimen_mercado": regimen,
        "regimen_score": regimen_score,
        "alertas": recomendaciones,
        "contexto_macro": contexto_macro,
        "cedears_pricing": cedears_pricing,
        "movimientos_dia": movimientos_dia,
        # Precio del SPY -- Mi Cartera lo guarda al comprar y al vender, para
        # poder comparar cada operación real contra el mercado (Auditoría)
        "spy_precio": round(float(precios[BENCHMARK].dropna().iloc[-1]), 2),
        "distribution_days": dist_days,
        "multiplicador_distribution": mult_dist_badge,
        "top30_nuevos_hoy": top30_nuevos_hoy["nuevos"],
        "top30_salientes_hoy": top30_nuevos_hoy["salientes"],
        "top30_fecha_comparacion": top30_nuevos_hoy["fecha_comparacion"],
        "top30_radar_nuevos_hoy": top30_radar_nuevos_hoy["nuevos"],
        "top30_radar_salientes_hoy": top30_radar_nuevos_hoy["salientes"],
        "top30_radar_fecha_comparacion": top30_radar_nuevos_hoy["fecha_comparacion"],
        "extremos_52w": extremos_52w,
        "amplitud_historial": amplitud_historial,
    }

    salida_limpia = limpiar_para_json(salida)
    with open("data/ultimo.json", "w", encoding="utf-8") as f:
        json.dump(salida_limpia, f, ensure_ascii=False, indent=2)
    log.info("Guardado en data/ultimo.json")

    # 9. Notificaciones
    alertas_relevantes = [
        a for a in recomendaciones
        if (a.get("Score_num") and a["Score_num"] >= SCORE_MINIMO_ALERTA)
        or a.get("Tipo") in ("lider_soporte", "gap_alcista", "confluencia_alcista", "ruptura_confirmada")
    ]
    # Dos memorias separadas:
    #  - _notificaciones: qué ya se mandó por Telegram. Solo la marca el
    #    modo PRODUCCIÓN -- así una corrida de prueba (test) no se "traga"
    #    un aviso que después la corrida real ya no mandaría.
    #  - _bitacora: qué ya se registró en la bitácora. La marcan los dos
    #    modos, para que la bitácora no duplique eventos.
    historial.setdefault("_notificaciones", {})
    if "_bitacora" not in historial:
        # Primera vez: arranca desde lo ya notificado, para no volver a
        # registrar en la bitácora lo que ya estaba registrado
        historial["_bitacora"] = dict(historial["_notificaciones"])
    alertas_nuevas = []
    alertas_bitacora = []
    for a in alertas_relevantes:
        ticker = a["Ticker"]
        clave_estado = f"{fecha_hoy}|{a['Tipo']}|{a['Estado']}"
        if historial["_notificaciones"].get(ticker) != clave_estado:
            alertas_nuevas.append(a)
        if historial["_bitacora"].get(ticker) != clave_estado:
            alertas_bitacora.append(a)

    if alertas_relevantes:
        log.info(f"{len(alertas_relevantes)} alerta(s) relevante(s), {len(alertas_nuevas)} nueva(s) (no notificadas aún hoy)")

    if alertas_bitacora and not corrida_degradada:
        registrar_eventos(alertas_bitacora, rs_por_ticker, precios_usd_actuales, timestamp,
                           radar_score_por_ticker)
        for a in alertas_bitacora:
            historial["_bitacora"][a["Ticker"]] = f"{fecha_hoy}|{a['Tipo']}|{a['Estado']}"
    elif alertas_bitacora and corrida_degradada:
        log.info("Bitácora: se salteó el registro de esta corrida (degradada)")

    if alertas_nuevas and corrida_degradada:
        log.warning(f"Se salteó el envío de {len(alertas_nuevas)} alerta(s) a Telegram "
                    f"-- corrida degradada ({pct_fallidos}% del universo falló)")
    elif alertas_nuevas:
        if MODO == "produccion":
            for a in alertas_nuevas:
                historial["_notificaciones"][a["Ticker"]] = f"{fecha_hoy}|{a['Tipo']}|{a['Estado']}"
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID")
            enviados = notificar_alertas(token, chat_id, alertas_nuevas, fecha_hoy)
            log.info(f"MODO=produccion -- {enviados} mensaje(s) enviado(s) a Telegram")
        else:
            log.info("MODO=test -- NO se envían notificaciones reales ni se marcan como avisadas")
            for a in alertas_nuevas:
                log.info(f"  [TEST] {a['Ticker']}: {a['Estado']} ({a['Score']}) -- {a['Recomendación final']}")
    else:
        log.info("Sin alertas nuevas para notificar en esta corrida")

    # 9b. Aviso de tickers desactualizados -- un solo mensaje, solo si hubo
    # alguno esta corrida (no todos los días), para no sumar ruido al
    # mensaje diario cuando no hace falta.
    if desactualizados_universo and MODO == "produccion" and not corrida_degradada:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        notificar_datos_desactualizados(token, chat_id, desactualizados_universo, fecha_hoy)

    # 9b-ter. Cambios de cuadrante de rotación (sectorial y por ticker) --
    # pedido de Victoria (2/10): avisar apenas un sector o un ticker CAMBIA
    # de cuadrante (Líder/Mejorando/Debilitándose/Rezagado), no solo que
    # quede logueado para la Auditoría de Rotación. No es una alerta nueva
    # ni cambia ningún cálculo -- son los mismos eventos que
    # rotacion_sectorial.py / rotacion_ticker.py ya detectan y loguean en
    # sus propios archivos, esto solo los manda también por Telegram. En
    # corrida degradada se salta igual que el resto de las notificaciones
    # (con medio universo caído, un "cambio de cuadrante" podría ser el
    # dato viejo asomando, no un cambio real).
    #
    # Sectores: son pocos (~16), se avisan TODOS los cambios (hacia
    # cualquier cuadrante). Tickers: es todo el universo -- avisar cada
    # cambio generaría demasiado ruido (y alguno justo en el límite entre
    # dos cuadrantes podría cruzar la línea varias veces en el mismo día).
    # Por pedido de Victoria (2/10), para tickers solo se avisa cuando
    # ENTRAN a Líder o Mejorando -- mismo criterio que ya usa "Recién a
    # Líderes" en el dashboard (rotacion_ticker.py). Los eventos hacia
    # Debilitándose/Rezagado igual quedan logueados en
    # log_rotacion_ticker.jsonl como siempre, para la Auditoría -- esto
    # solo decide cuáles se mandan por Telegram.
    eventos_cuadrante_ticker = [
        e for e in rotacion_ticker.get("eventos", [])
        if e.get("cuadrante_nuevo") in ("Líder", "Mejorando")
    ]
    if (eventos_rotacion_sectorial or eventos_cuadrante_ticker) and MODO == "produccion" and not corrida_degradada:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        enviados_cuadrante = notificar_cambios_cuadrante(
            token, chat_id, eventos_rotacion_sectorial, eventos_cuadrante_ticker, fecha_hoy)
        log.info(f"Cambios de cuadrante: {len(eventos_rotacion_sectorial)} sector(es), "
                 f"{len(eventos_cuadrante_ticker)} ticker(s) -- {enviados_cuadrante} mensaje(s) enviado(s) a Telegram")
    elif eventos_rotacion_sectorial or eventos_cuadrante_ticker:
        log.info(f"MODO=test o corrida degradada -- NO se avisan los {len(eventos_rotacion_sectorial)} "
                 f"cambio(s) de cuadrante sectorial y {len(eventos_cuadrante_ticker)} de ticker de esta corrida")

    # 9b-quater. Golden Cross / Death Cross confirmados -- mismo criterio
    # de corrida degradada que el resto: con medio universo caído, un
    # "cruce confirmado" podría estar armado con SMA50/SMA200 de datos
    # incompletos.
    eventos_golden_cross = golden_cross.get("eventos", [])
    if eventos_golden_cross and MODO == "produccion" and not corrida_degradada:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        enviados_gc = notificar_golden_cross(token, chat_id, eventos_golden_cross, fecha_hoy)
        log.info(f"Golden/Death Cross: {len(eventos_golden_cross)} confirmado(s) -- {enviados_gc} mensaje(s) enviado(s) a Telegram")
    elif eventos_golden_cross:
        log.info(f"MODO=test o corrida degradada -- NO se avisan los {len(eventos_golden_cross)} "
                 f"cruce(s) confirmado(s) de esta corrida")

    # 9b-quinquies. Liberaciones de squeeze confirmadas (banda + volumen).
    # Mismo criterio de corrida degradada.
    eventos_squeeze = squeeze.get("eventos", [])
    if eventos_squeeze and MODO == "produccion" and not corrida_degradada:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        enviados_sq = notificar_squeeze(token, chat_id, eventos_squeeze, fecha_hoy)
        log.info(f"Squeeze: {len(eventos_squeeze)} liberación(es) confirmada(s) -- {enviados_sq} mensaje(s) enviado(s) a Telegram")
    elif eventos_squeeze:
        log.info(f"MODO=test o corrida degradada -- NO se avisan las {len(eventos_squeeze)} "
                 f"liberación(es) de squeeze de esta corrida")

    # 9b-quinquies-bis. Zonas de oferta/demanda: estado + bitácora de "zona de
    # interés" (solo se escribe en producción y sin corrida degradada, igual
    # que el resto de los registros). Sin aviso a Telegram: por ahora solo
    # se registra para poder medirlo más adelante.
    if MODO == "produccion" and not corrida_degradada:
        try:
            guardar_zonas(zonas)
            if zonas.get("eventos"):
                log.info(f"Zonas: {len(zonas['eventos'])} activo(s) entraron en zona de interés (registrado en la bitácora)")
        except Exception as e:
            log.warning(f"Zonas: no se pudo guardar el estado/bitácora ({e})")

    # 9b-sexies. Avisos de niveles en seguimiento (ver niveles_seguimiento.py).
    # ADITIVO: no usa ni modifica ninguna señal del radar ni la Auditoría; baja
    # sus propios precios. Aparte de los demás avisos, si falla no tumba la
    # corrida.
    try:
        procesar_niveles(MODO, os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID"))
    except Exception as e:
        log.warning(f"Niveles de seguimiento: falló esta pasada ({e}) -- se sigue con el resto de la corrida")

    # 9b-bis. Rebote en EMA200 -- EXPERIMENTAL, "solo medir" (ver charla
    # con Victoria, 30/9): se registra en la bitácora para que la
    # Auditoría la mida con el tiempo, pero todavía NO aparece como
    # alerta (ni tarjeta ni Telegram) hasta tener resultados reales que
    # la respalden.
    if not corrida_degradada:
        try:
            candidatos_rebote, historial = detectar_rebote_ema200(precios, TICKERS, rs_por_ticker, historial)
            if candidatos_rebote:
                registrar_eventos(candidatos_rebote, rs_por_ticker, precios_usd_actuales, timestamp,
                                   radar_score_por_ticker)
                log.info(f"Rebote en EMA200 (experimental): {len(candidatos_rebote)} episodio(s) nuevo(s) "
                         f"registrado(s) en bitácora -- todavía sin mostrarse como alerta")
        except Exception as e:
            log.error(f"Rebote en EMA200 (experimental) falló, no afecta al resto de la corrida: {e}")

    guardar_historial(historial)

    # 9c. Seguimiento de precios de la bitácora -- para el backtest futuro
    # (compara radar-mercado v1 vs. hypertrade v2). No depende de que
    # haya alertas nuevas hoy, revisa TODA la bitácora acumulada cada vez.
    try:
        procesar_seguimiento(precios)
    except Exception as e:
        log.error(f"Seguimiento de precios falló, no afecta al resto de la corrida: {e}")

    # 9c-bis. Auditoría (solapa Auditoría del dashboard) -- resultados reales
    # por señal, foto semanal del Top 30 y simulación hacia atrás. En una
    # corrida degradada NO se guarda la foto del Top 30 (el RS no es
    # confiable con medio universo caído), pero el resto se calcula igual.
    try:
        correr_auditoria(precios, None if corrida_degradada else df_rs, list(TICKERS), ahora)
    except Exception as e:
        log.error(f"Auditoría falló, no afecta al resto de la corrida: {e}")

    # 9c-ter. Auditoría de Rotación Sectorial -- mide si entrar a Líder/
    # Mejorando (o Debilitándose/Rezagado) realmente anticipó que el sector
    # le gane (o le pierda) al SPY. Ver auditoria_rotacion.py.
    try:
        correr_auditoria_rotacion(precios, TICKERS, BENCHMARK, ahora)
    except Exception as e:
        log.error(f"Auditoría de rotación sectorial falló, no afecta al resto de la corrida: {e}")

    # 9c-quater. Auditoría de Golden Cross / Death Cross -- ver
    # auditoria_golden_cross.py. Completamente separada de la Auditoría de
    # siempre y de la de Rotación: no toca ninguna medición existente.
    try:
        correr_auditoria_golden_cross(precios, BENCHMARK, ahora)
    except Exception as e:
        log.error(f"Auditoría de Golden/Death Cross falló, no afecta al resto de la corrida: {e}")

    # 9c-quinquies. Auditoría de Squeeze Release -- ver auditoria_squeeze.py.
    try:
        correr_auditoria_squeeze(precios, BENCHMARK, ahora)
    except Exception as e:
        log.error(f"Auditoría de Squeeze falló, no afecta al resto de la corrida: {e}")

    # 9d. Evaluación del sistema -- responde si el Radar Score y sus
    # señales individuales realmente anticipan un movimiento rentable.
    # No hace falta correrla en cada corrida de 30 min (es una foto sobre
    # datos que se acumulan lento) -- una vez por semana alcanza. Se
    # puede ajustar el día si se prefiere otro.
    try:
        if ahora.weekday() == 4:  # viernes
            evaluar_sistema()
    except Exception as e:
        log.error(f"Evaluación del sistema falló, no afecta al resto de la corrida: {e}")

    # 10. Mi Cartera -- seguimiento activo (trailing stop, objetivos,
    # caída de Radar Score) + Telegram si hay algo nuevo para avisar. No
    # rompe la corrida si falla (try/except propio adentro del módulo
    # para el envío de mail; acá solo por las dudas de que falte el
    # archivo o algo raro en el parseo).
    try:
        procesar_cartera(
            df_rs,
            fecha_hoy,
            email_user=os.environ.get("EMAIL_USER"),
            email_password=os.environ.get("EMAIL_PASSWORD"),
            email_to=os.environ.get("EMAIL_TO"),
            modo=MODO,
            precios=precios,
        )
    except Exception as e:
        log.error(f"Seguimiento de cartera falló, no afecta al resto de la corrida: {e}")

    log.info("=== Corrida finalizada ===")


if __name__ == "__main__":
    main()
