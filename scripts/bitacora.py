"""
Bitácora de eventos: un log de SOLO AGREGADO (nunca pisa nada, a diferencia
de historial_alertas.json que guarda el estado actual de cada ticker) con
cada alerta que se disparó y los valores de sus componentes en ese momento
-- la "foto" necesaria para poder medir más adelante (backtest, dentro de
un par de meses) qué señales realmente anticiparon un movimiento rentable.

Formato JSONL (un evento por línea) para poder ir agregando sin tener que
reescribir ni parsear un archivo gigante en cada corrida.
"""
import json
import logging

log = logging.getLogger("radar.bitacora")

ARCHIVO_LOG = "data/log_alertas.jsonl"


def registrar_eventos(alertas_nuevas: list, rs_por_ticker: dict, precios_usd: dict, timestamp: str,
                       radar_score_por_ticker: dict = None):
    """
    Agrega una línea por cada alerta NUEVA de esta corrida a la bitácora.

    Recibe específicamente alertas_nuevas (ya deduplicadas por la lógica de
    notificaciones, no todas las alertas activas) para que un evento = una
    alerta genuinamente nueva -- si una alerta sigue activa sin cambiar de
    estado en corridas sucesivas, no se vuelve a loguear cada vez.
    """
    if not alertas_nuevas:
        return 0

    radar_score_por_ticker = radar_score_por_ticker or {}
    lineas = []
    for a in alertas_nuevas:
        ticker = a["Ticker"]
        vcp_info = a.get("VCP") or {}
        rs_ticker = rs_por_ticker.get(ticker)
        radar_score_ticker = radar_score_por_ticker.get(ticker)
        evento = {
            "timestamp": timestamp,
            "ticker": ticker,
            "sector": a.get("Sector"),
            "tipo": a.get("Tipo"),
            "estado": a.get("Estado"),
            "score_num": a.get("Score_num"),
            "rs_score": round(rs_ticker, 1) if rs_ticker is not None else None,
            "radar_score": radar_score_ticker,
            "vol_rel": a.get("Vol_rel"),
            "rsi": a.get("RSI"),
            "vcp_valido": vcp_info.get("valido") if isinstance(vcp_info, dict) else None,
            "precio": precios_usd.get(ticker),
            "recomendacion": a.get("Recomendación final"),
            # Régimen de mercado 0-100 al momento de la alerta -- para que la
            # Auditoría compare aciertos con clima bueno vs. clima malo
            "regimen_score": a.get("Regimen_Score"),
            # Qué puntos de cuidado tenía (lista vacía = ninguno) -- para ver
            # si las alertas con advertencias de verdad rinden peor
            "cuidados": a.get("Cuidados_claves"),
            # --- Nuevo: la "foto" de señales individuales, para poder
            # evaluar más adelante cuáles de verdad anticipan movimiento
            # rentable (ver evaluacion_sistema.py) -- sin esto, el backtest
            # solo puede evaluar el Radar Score en conjunto, nunca sus partes.
            "apoyo_avwap": a.get("Apoyo_AVWAP"),
            "cruce_avwap_52w": a.get("Cruce_AVWAP_52w"),
            "atr_contraction": a.get("ATR_Contraction"),
            "pendiente_ok": a.get("Pendiente_OK"),
            "dist_max52w_pct": a.get("Dist_Max52w_%"),
            "var_dia_pct": a.get("Var_dia_%"),
            "var_spy_dia_pct": a.get("Var_SPY_dia_%"),
        }
        lineas.append(json.dumps(evento, ensure_ascii=False))

    with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
        for linea in lineas:
            f.write(linea + "\n")

    log.info(f"Bitácora: {len(lineas)} evento(s) nuevo(s) agregado(s) a {ARCHIVO_LOG}")
    return len(lineas)
