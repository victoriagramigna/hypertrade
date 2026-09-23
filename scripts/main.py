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
from datetime import datetime, timezone, timedelta

from config import (TICKERS, BENCHMARK, SCORE_MINIMO_ALERTA, MODO, VIX_TICKER,
                     UMBRAL_MOVIMIENTO_DIARIO_PCT, UMBRAL_CORRIDA_DEGRADADA_PCT)
from datos import traer_datos
from rs_score import calcular_rs_score
from alertas import detectar_alertas
from contexto import escanear_titulares, evaluar_contexto_macro, recomendacion_final
from regimen_mercado import evaluar_regimen_mercado
from historial import cargar_historial, guardar_historial
from telegram_bot import notificar_alertas
from macro_local import traer_contexto_macro
from frescura import evaluar_frescura
from cedear_pricing import calcular_brechas_cedear
from movimientos import detectar_movimientos_diarios
from bitacora import registrar_eventos
from radar_score import calcular_radar_score
from narrativa import armar_narrativa
from senales_nuevas import calcular_distribution_days, multiplicador_distribution
from cartera_seguimiento import procesar_cartera
from seguimiento_precios import procesar_seguimiento
from evaluacion_sistema import evaluar_sistema
from auditoria import correr_auditoria

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
    precios, volumenes, precios_ohlc, fallidos = traer_datos({**tickers_a_pedir, VIX_TICKER: "Índice"}, BENCHMARK)
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

    # 2. Régimen de mercado (VIX)
    vix_actual = traer_vix(precios)
    regimen = evaluar_regimen_mercado(vix_actual)
    log.info(f"Régimen de mercado: {regimen}")

    # 2b. Frescura del dato
    ultima_fecha_benchmark = precios[BENCHMARK].dropna().index[-1] if not precios[BENCHMARK].dropna().empty else None
    frescura = evaluar_frescura(ultima_fecha_benchmark)
    log.info(f"Frescura del dato: {frescura}")

    # 2c. Distribution Days -- v2.1: SOLO informativo (badge), ya no
    # multiplica el Radar Score (ver radar_score.py). Se sigue calculando
    # y guardando en el JSON para que el dashboard lo muestre.
    dist_days = calcular_distribution_days(precios[BENCHMARK], volumenes[BENCHMARK])
    mult_dist_badge = multiplicador_distribution(dist_days)  # solo para colorear el badge
    log.info(f"Distribution Days (25 ruedas): {dist_days} -- (informativo, ya no penaliza el score)")

    # 3. RS Score + indicadores completos
    df_rs = calcular_rs_score(precios, TICKERS, BENCHMARK, volumenes)
    rs_por_sector = df_rs.groupby("Sector")["RS_Score"].mean().to_dict() if not df_rs.empty else {}
    rs_por_ticker = dict(zip(df_rs["Ticker"], df_rs["RS_Score"])) if not df_rs.empty else {}

    # 3a-bis. Radar Score v2.1 (compuesto 0-100 -- Distribution Days ya NO
    # se pasa acá, ver nota arriba)
    bench_close = precios[BENCHMARK].dropna()
    spy_sma50 = bench_close.rolling(50).mean().iloc[-1] if len(bench_close) >= 50 else None
    spy_sobre_sma50 = bool(bench_close.iloc[-1] > spy_sma50) if spy_sma50 is not None and not math.isnan(spy_sma50) else True
    df_rs = calcular_radar_score(df_rs, rs_por_sector, spy_sobre_sma50, regimen, precios_ohlc)

    # 3b. Señal de CEDEAR caro/barato
    precios_usd_actuales = dict(zip(df_rs["Ticker"], df_rs["Precio"])) if not df_rs.empty else {}
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
                                              fecha_hoy, timestamp)
    guardar_historial(historial)

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
        "RS_Score", "VCP_valido", "Sobre_SMA50", "Dist_SMA200_%",
        "SMA50", "SMA200",
        "AVWAP_YTD", "AVWAP_52W_High", "AVWAP_Ultimo_Gap", "Apoyo_AVWAP",
        "ATR_Ratio", "ATR_Contraction", "Pendiente_OK", "Cruce_AVWAP_52w",
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

        fila_completa = {**fila.to_dict(), **rec, **extras_por_ticker.get(fila["Ticker"], {})}
        fila_completa["Narrativa"] = armar_narrativa(fila_completa, dist_days, mult_dist_badge, regimen.get("sano", True))
        recomendaciones.append(fila_completa)

    # 8. Guardar resultado para el dashboard
    salida = {
        "generado_utc": timestamp,
        "proxima_corrida_estimada_utc": estimar_proxima_corrida(ahora),
        "tickers_ok": len(precios) - 2,
        "tickers_fallidos": fallidos,
        "pct_fallidos": pct_fallidos,
        "corrida_degradada": corrida_degradada,
        "frescura_dato": frescura,
        "ranking": df_rs.to_dict(orient="records") if not df_rs.empty else [],
        "rs_por_sector": rs_por_sector,
        "regimen_mercado": regimen,
        "alertas": recomendaciones,
        "contexto_macro": contexto_macro,
        "cedears_pricing": cedears_pricing,
        "movimientos_dia": movimientos_dia,
        "distribution_days": dist_days,
        "multiplicador_distribution": mult_dist_badge,
    }

    salida_limpia = limpiar_para_json(salida)
    with open("data/ultimo.json", "w", encoding="utf-8") as f:
        json.dump(salida_limpia, f, ensure_ascii=False, indent=2)
    log.info("Guardado en data/ultimo.json")

    # 9. Notificaciones
    alertas_relevantes = [
        a for a in recomendaciones
        if (a.get("Score_num") and a["Score_num"] >= SCORE_MINIMO_ALERTA) or a.get("Tipo") in ("lider_soporte", "gap_alcista")
    ]
    historial.setdefault("_notificaciones", {})
    alertas_nuevas = []
    for a in alertas_relevantes:
        ticker = a["Ticker"]
        clave_estado = f"{fecha_hoy}|{a['Tipo']}|{a['Estado']}"
        ya_notificado = historial["_notificaciones"].get(ticker) == clave_estado
        if not ya_notificado:
            alertas_nuevas.append(a)

    if alertas_relevantes:
        log.info(f"{len(alertas_relevantes)} alerta(s) relevante(s), {len(alertas_nuevas)} nueva(s) (no notificadas aún hoy)")

    if alertas_nuevas and not corrida_degradada:
        registrar_eventos(alertas_nuevas, rs_por_ticker, precios_usd_actuales, timestamp,
                           radar_score_por_ticker)
    elif alertas_nuevas and corrida_degradada:
        log.info("Bitácora: se salteó el registro de esta corrida (degradada)")

    if alertas_nuevas and corrida_degradada:
        log.warning(f"Se salteó el envío de {len(alertas_nuevas)} alerta(s) a Telegram "
                    f"-- corrida degradada ({pct_fallidos}% del universo falló)")
    elif alertas_nuevas:
        for a in alertas_nuevas:
            ticker = a["Ticker"]
            clave_estado = f"{fecha_hoy}|{a['Tipo']}|{a['Estado']}"
            historial["_notificaciones"][ticker] = clave_estado

        if MODO == "produccion":
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID")
            enviados = notificar_alertas(token, chat_id, alertas_nuevas, fecha_hoy)
            log.info(f"MODO=produccion -- {enviados} mensaje(s) enviado(s) a Telegram")
        else:
            log.info("MODO=test -- NO se envían notificaciones reales, solo se loguea")
            for a in alertas_nuevas:
                log.info(f"  [TEST] {a['Ticker']}: {a['Estado']} ({a['Score']}) -- {a['Recomendación final']}")
    else:
        log.info("Sin alertas nuevas para notificar en esta corrida")

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
    # caída de Radar Score) + mail si hay algo nuevo para avisar. No
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
        )
    except Exception as e:
        log.error(f"Seguimiento de cartera falló, no afecta al resto de la corrida: {e}")

    log.info("=== Corrida finalizada ===")


if __name__ == "__main__":
    main()
