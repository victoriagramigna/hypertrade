"""
Seguimiento de resultados de la bitácora -- para el backtest futuro
que compara radar-mercado (v1) vs. hypertrade (v2).

No modifica data/log_alertas.jsonl (la bitácora original queda
intacta). Lee esos eventos, y para cada uno que ya tenga 5, 10 o 20
ruedas de antigüedad Y todavía no tenga ese horizonte evaluado,
calcula la variación de precio desde el momento de la alerta y la
guarda en un archivo nuevo: data/seguimiento_resultados.jsonl

Cada línea de salida:
  {ticker, timestamp_evento, horizonte_ruedas, precio_entrada,
   precio_horizonte, fecha_horizonte, variacion_pct, radar_score,
   recomendacion, tipo, sector, apoyo_avwap, cruce_avwap_52w,
   atr_contraction, pendiente_ok, spy_variacion_pct, alpha_pct}
"""
import json
import logging
import os
from datetime import datetime

from config import BENCHMARK

log = logging.getLogger("radar.seguimiento")

RUTA_LOG = "data/log_alertas.jsonl"
RUTA_RESULTADOS = "data/seguimiento_resultados.jsonl"
HORIZONTES_RUEDAS = (5, 10, 20)


def _leer_jsonl(ruta):
    if not os.path.exists(ruta):
        return []
    eventos = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                eventos.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return eventos


def _variacion_en_horizonte(serie, fecha_evento, horizonte):
    """Devuelve (precio_entrada, precio_horizonte, fecha_horizonte, variacion_pct)
    para una serie de precios dada, o None si todavía no hay suficientes ruedas
    posteriores a fecha_evento. precio_entrada se toma de la última rueda
    disponible EN o ANTES de fecha_evento (necesario para SPY, que no tiene
    el precio_entrada ya guardado como sí lo tiene el ticker en la bitácora)."""
    if serie is None:
        return None
    serie = serie.dropna()
    if serie.empty:
        return None

    anteriores_o_igual = serie[serie.index.date <= fecha_evento]
    if anteriores_o_igual.empty:
        return None
    precio_entrada = float(anteriores_o_igual.iloc[-1])

    posteriores = serie[serie.index.date > fecha_evento]
    if len(posteriores) < horizonte:
        return None

    precio_horizonte = float(posteriores.iloc[horizonte - 1])
    fecha_horizonte = posteriores.index[horizonte - 1]
    variacion_pct = round((precio_horizonte / precio_entrada - 1) * 100, 2)
    return precio_entrada, precio_horizonte, fecha_horizonte, variacion_pct


def procesar_seguimiento(precios: dict):
    """
    precios: el mismo dict {ticker: pd.Series de Close} que ya se usa
    en el resto del pipeline (main.py). Se llama una vez por corrida,
    después de tener los precios descargados. Incluye BENCHMARK (SPY)
    porque main.py ya lo agrega al universo para el cálculo de RS.
    """
    eventos = _leer_jsonl(RUTA_LOG)
    if not eventos:
        log.info("Seguimiento: bitácora vacía todavía, nada que evaluar")
        return

    ya_evaluados = {
        (r["ticker"], r["timestamp_evento"], r["horizonte_ruedas"])
        for r in _leer_jsonl(RUTA_RESULTADOS)
    }

    serie_spy = precios.get(BENCHMARK)
    nuevos_resultados = []

    for ev in eventos:
        ticker = ev.get("ticker")
        ts = ev.get("timestamp")
        precio_entrada = ev.get("precio")
        if not ticker or not ts or precio_entrada is None:
            continue
        if ticker not in precios:
            continue

        try:
            fecha_evento = datetime.fromisoformat(ts).date()
        except ValueError:
            continue

        serie = precios[ticker].dropna()
        if serie.empty:
            continue

        # Todas las ruedas que vinieron DESPUÉS del día de la alerta,
        # en orden cronológico -- de ahí sacamos la rueda #5, #10, #20
        posteriores = serie[serie.index.date > fecha_evento]
        if posteriores.empty:
            continue

        for horizonte in HORIZONTES_RUEDAS:
            clave = (ticker, ts, horizonte)
            if clave in ya_evaluados:
                continue
            if len(posteriores) < horizonte:
                continue  # todavía no pasaron suficientes ruedas

            precio_horizonte = float(posteriores.iloc[horizonte - 1])
            fecha_horizonte = posteriores.index[horizonte - 1]
            variacion_pct = round((precio_horizonte / precio_entrada - 1) * 100, 2)

            # Alpha vs. SPY en la misma ventana exacta de tiempo -- sin esto,
            # una suba de +10% no dice si el ticker le ganó al mercado o
            # si todo el mercado subió +10% ese mismo período (ver pregunta
            # 3 del plan de evaluación).
            spy_variacion_pct = None
            alpha_pct = None
            resultado_spy = _variacion_en_horizonte(serie_spy, fecha_evento, horizonte)
            if resultado_spy is not None:
                _, _, _, spy_variacion_pct = resultado_spy
                alpha_pct = round(variacion_pct - spy_variacion_pct, 2)

            nuevos_resultados.append({
                "ticker": ticker,
                "timestamp_evento": ts,
                "horizonte_ruedas": horizonte,
                "precio_entrada": precio_entrada,
                "precio_horizonte": precio_horizonte,
                "fecha_horizonte": fecha_horizonte.isoformat(),
                "variacion_pct": variacion_pct,
                "radar_score": ev.get("radar_score"),
                "recomendacion": ev.get("recomendacion"),
                "tipo": ev.get("tipo"),
                "sector": ev.get("sector"),
                # --- Señales individuales, reenviadas desde la bitácora
                # (ver bitacora.py) -- necesarias para la pregunta 2 del
                # plan de evaluación: ¿qué señal individual importa?
                "apoyo_avwap": ev.get("apoyo_avwap"),
                "cruce_avwap_52w": ev.get("cruce_avwap_52w"),
                "atr_contraction": ev.get("atr_contraction"),
                "pendiente_ok": ev.get("pendiente_ok"),
                "spy_variacion_pct": spy_variacion_pct,
                "alpha_pct": alpha_pct,
            })

    if not nuevos_resultados:
        log.info("Seguimiento: sin resultados nuevos para evaluar esta corrida")
        return

    os.makedirs("data", exist_ok=True)
    with open(RUTA_RESULTADOS, "a", encoding="utf-8") as f:
        for r in nuevos_resultados:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    log.info(f"Seguimiento: {len(nuevos_resultados)} resultado(s) nuevo(s) agregado(s) a {RUTA_RESULTADOS}")
