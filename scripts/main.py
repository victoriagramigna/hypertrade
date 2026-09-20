"""
Punto de entrada principal del Radar de Mercado (v3).
Suma sobre v2: RSI/RVOL/SMA200 expuestos para todo el universo (no solo
alertas), fix del bug de expiración de alertas (ventana de 48hs), nueva
señal "líder apoyando en soporte", y estimación de próxima corrida (para
que sea más fácil distinguir "no corrió todavía" de "corrió y no hubo
novedades").
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("radar.main")


def limpiar_para_json(obj):
    """
    Recorre recursivamente el resultado antes de guardarlo y convierte
    cualquier NaN/infinito o tipo de NumPy no serializable a algo válido
    para JSON estándar. Sin esto, un solo NaN suelto en cualquier campo
    (por ejemplo, un indicador que no se pudo calcular para algún ticker)
    rompe el parseo en el navegador -- JSON.parse() no acepta el literal
    NaN, aunque Python lo escriba en el archivo sin quejarse.
    Idea original: propuesta de Gemini, ampliada acá para cubrir también
    infinitos y los tipos numéricos propios de NumPy/Pandas (np.float64,
    np.int64, np.bool_), que tampoco son serializables tal cual.
    """
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
    """Placeholder -- se conecta Finnhub /news más adelante."""
    return []


def traer_vix(precios: dict):
    if VIX_TICKER in precios and not precios[VIX_TICKER].empty:
        return float(precios[VIX_TICKER].iloc[-1])
    return None


def estimar_proxima_corrida(ahora: datetime) -> str:
    """
    Estimación INFORMATIVA de la próxima corrida programada, según el cron
    (cada hora en punto de 14 a 21 UTC, lunes a viernes). GitHub Actions
    corre los crons en modo "best effort" -- puede demorarse minutos u
    horas en momentos de alta demanda de su infraestructura compartida
    gratuita, así que esto es una referencia, no una garantía exacta.
    """
    candidato = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    for _ in range(24 * 8):  # tope de seguridad, no debería iterar tanto
        es_habil = candidato.weekday() < 5  # 0=lunes ... 4=viernes
        en_horario = 14 <= candidato.hour <= 21
        if es_habil and en_horario:
            return candidato.isoformat()
        candidato += timedelta(hours=1)
    return None  # no debería pasar nunca, pero mejor no romper si pasa


def main():
    log.info(f"=== Radar de Mercado — corrida iniciada (modo={MODO}) ===")
    ahora = datetime.now(timezone.utc)
    timestamp = ahora.isoformat()
    fecha_hoy = ahora.strftime("%Y-%m-%d")

    # 1. Datos (se pide también el VIX, sumándolo como si fuera un ticker más)
    tickers_a_pedir = {**TICKERS}
    precios, volumenes, fallidos = traer_datos({**tickers_a_pedir, VIX_TICKER: "Índice"}, BENCHMARK)
    if BENCHMARK not in precios:
        log.error("El benchmark no se pudo traer -- abortando la corrida")
        return

    # 1b. Estado de fuentes -- ¿falló poco (normal) o falló tanto que el RS
    # Score de esta corrida ya no es confiable (percentil sobre un universo
    # chico y no representativo)?
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

    # 3. RS Score + indicadores completos (RSI, RVOL, SMA50/200) para TODO el universo
    df_rs = calcular_rs_score(precios, TICKERS, BENCHMARK, volumenes)
    rs_por_sector = df_rs.groupby("Sector")["RS_Score"].mean().to_dict() if not df_rs.empty else {}
    rs_por_ticker = dict(zip(df_rs["Ticker"], df_rs["RS_Score"])) if not df_rs.empty else {}

    # 3a-bis. Radar Score v1 (compuesto, pensado para timing de entrada --
    # ver radar_score.py para la definición completa de cada componente)
    bench_close = precios[BENCHMARK].dropna()
    spy_sma50 = bench_close.rolling(50).mean().iloc[-1] if len(bench_close) >= 50 else None
    spy_sobre_sma50 = bool(bench_close.iloc[-1] > spy_sma50) if spy_sma50 is not None and not math.isnan(spy_sma50) else True
    df_rs = calcular_radar_score(df_rs, rs_por_sector, spy_sobre_sma50, regimen)

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

    # 5. Alertas técnicas (v3: expiran a las 48hs, + señal "líder en soporte")
    df_alertas, historial = detectar_alertas(precios, volumenes, TICKERS, BENCHMARK,
                                              rs_por_sector, rs_por_ticker, historial,
                                              fecha_hoy, timestamp)
    guardar_historial(historial)

    # 6. Contexto (noticias + macro-local)
    titulares = traer_titulares_ejemplo()  # Finnhub -- pendiente de conectar
    alertas_sector = escanear_titulares(titulares)
    riesgo_pais, riesgo_pais_ayer, brecha = traer_contexto_macro()  # ArgentinaDatos -- real
    contexto_macro = evaluar_contexto_macro(riesgo_pais, riesgo_pais_ayer, brecha)
    log.info(f"Contexto macro-local: {contexto_macro}")

    # 7. Recomendación final
    radar_score_por_ticker = dict(zip(df_rs["Ticker"], df_rs["Radar_Score"])) if not df_rs.empty else {}
    dist_52w_por_ticker = dict(zip(df_rs["Ticker"], df_rs["Dist_Max52w_%"])) if not df_rs.empty else {}

    # Variación de SPY HOY (cierre de hoy vs. cierre de ayer) -- para poder
    # comparar el movimiento de cada alerta contra el del mercado en general
    # ese mismo día, no solo contra su propio historial.
    bench_close_serie = precios[BENCHMARK].dropna()
    var_spy_dia_pct = None
    if len(bench_close_serie) >= 2:
        var_spy_dia_pct = round((bench_close_serie.iloc[-1] / bench_close_serie.iloc[-2] - 1) * 100, 2)

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
        recomendaciones.append({**fila.to_dict(), **rec})

    # 8. Guardar resultado para el dashboard
    salida = {
        "generado_utc": timestamp,
        "proxima_corrida_estimada_utc": estimar_proxima_corrida(ahora),
        "tickers_ok": len(precios) - 2,  # -1 benchmark, -1 VIX
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
    }

    salida_limpia = limpiar_para_json(salida)
    with open("data/ultimo.json", "w", encoding="utf-8") as f:
        json.dump(salida_limpia, f, ensure_ascii=False, indent=2)
    log.info("Guardado en data/ultimo.json")

    # 9. Notificaciones (dedup por día+estado; "líder en soporte" no usa la escala 0-7)
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
            # OJO: el marcado de "ya notificado" se hace más abajo, recién
            # cuando efectivamente se envía (o se loguea en modo test) --
            # no acá, para que una alerta salteada por corrida degradada
            # pueda mandarse igual en una corrida sana posterior el mismo día.

    if alertas_relevantes:
        log.info(f"{len(alertas_relevantes)} alerta(s) relevante(s), {len(alertas_nuevas)} nueva(s) (no notificadas aún hoy)")

    # 9b. Bitácora de eventos (para el backtest futuro) -- se saltea en
    # corridas degradadas, por la misma razón que Telegram: el RS Score de
    # esta corrida no es confiable, así que no vale la pena dejarlo grabado
    # como si lo fuera.
    if alertas_nuevas and not corrida_degradada:
        registrar_eventos(alertas_nuevas, rs_por_ticker, precios_usd_actuales, timestamp,
                           radar_score_por_ticker)
    elif alertas_nuevas and corrida_degradada:
        log.info("Bitácora: se salteó el registro de esta corrida (degradada)")

    if alertas_nuevas and corrida_degradada:
        log.warning(f"Se salteó el envío de {len(alertas_nuevas)} alerta(s) a Telegram "
                    f"-- corrida degradada ({pct_fallidos}% del universo falló), "
                    f"el ranking de esta corrida no es confiable. NO se marcan como "
                    f"notificadas, para poder reintentar en una corrida sana.")
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
                log.info(f"  [TEST] {a['Ticker']}: {a['Estado']} ({a['Score']}) — {a['Recomendación final']}")
    else:
        log.info("Sin alertas nuevas para notificar en esta corrida")

    guardar_historial(historial)

    log.info("=== Corrida finalizada ===")


if __name__ == "__main__":
    main()
