"""
Variación del RS Score en el tiempo (Δ día / Δ semana / Δ mes).

Inspirado en un panel que Victoria vio en otra herramienta (columnas
"Δ día", "Δ sem", "Δ mes" junto al RS Score de cada ticker). Guarda, una
vez por día, el RS Score de TODO el universo (no solo el Top 30) en un
historial diario (data/rs_score_historial.jsonl), y con eso calcula
cuánto cambió el RS Score de cada ticker hoy respecto de ayer, de hace
~1 semana (5 ruedas hábiles) y de hace ~1 mes (21 ruedas hábiles).

El historial se poda a los últimos TOPE_DIAS_HISTORIAL días guardados
(2/10): nada en la app necesita mirar más atrás que eso -- el Δ mes
usa come mucho 21 ruedas, y la cola del Cuadrante de Rotación por
Ticker (rotacion_ticker.py) usa como mucho 8 semanas -- así que 90
días de margen no le recorta nada a ninguna de las dos, ni tampoco a
la Auditoría (que no lee este archivo en absoluto, mide con sus
propias "fotos" semanales aparte). Sin la poda, este archivo iba a
crecer para siempre.

Es información puramente agregada sobre un número que YA se calcula (el
RS Score de siempre, contra el SPY) -- no cambia su cálculo en absoluto,
ni el de ninguna otra señal ni el de la Auditoría. Un ticker sin
suficiente historial todavía (recién agregado al universo, o el sistema
recién arrancó a guardar esto) simplemente muestra None en esa columna
en particular -- no se inventa ni se estima nada.
"""
import json
import logging
import os

log = logging.getLogger("radar.rs_deltas")

RUTA_HISTORIAL = "data/rs_score_historial.jsonl"
VENTANA_SEMANA_RUEDAS = 5    # ~5 ruedas hábiles = 1 semana de mercado
VENTANA_MES_RUEDAS = 21      # ~21 ruedas hábiles = 1 mes de mercado
TOPE_DIAS_HISTORIAL = 90     # margen de sobra sobre los ~21 que necesita el Δ mes y las ~40 ruedas que usa la cola por ticker


def _leer_fotos():
    if not os.path.exists(RUTA_HISTORIAL):
        return []
    fotos = []
    with open(RUTA_HISTORIAL, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                fotos.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return fotos


def registrar_y_calcular_deltas(df_rs, fecha_hoy: str) -> dict:
    """
    df_rs: DataFrame con columnas 'Ticker' y 'RS_Score'.
    fecha_hoy: 'YYYY-MM-DD'.

    Devuelve {ticker: {"Delta_RS_dia": float|None, "Delta_RS_semana": ...,
    "Delta_RS_mes": ...}}. Appendea la foto de hoy al historial (salvo
    que ya exista una foto de hoy -- no duplica en corridas repetidas).
    """
    if df_rs is None or df_rs.empty or "RS_Score" not in df_rs.columns:
        return {}

    rs_hoy = {t: v for t, v in zip(df_rs["Ticker"], df_rs["RS_Score"]) if v is not None}

    fotos = _leer_fotos()
    ya_hoy = any(f.get("fecha") == fecha_hoy for f in fotos)
    if not ya_hoy:
        foto_nueva = {"fecha": fecha_hoy, "rs": {t: round(float(v), 1) for t, v in rs_hoy.items()}}
        fotos.append(foto_nueva)
        # Poda a los últimos TOPE_DIAS_HISTORIAL (2/10) -- por eso ahora se
        # reescribe el archivo entero en vez de solo appendear una línea;
        # nada que lea este archivo necesita más que eso (ver docstring).
        fotos = sorted(fotos, key=lambda f: f.get("fecha", ""))[-TOPE_DIAS_HISTORIAL:]
        with open(RUTA_HISTORIAL, "w", encoding="utf-8") as f:
            for foto in fotos:
                f.write(json.dumps(foto, ensure_ascii=False) + "\n")
        log.info(f"RS Score de hoy ({fecha_hoy}) guardado en {RUTA_HISTORIAL} ({len(rs_hoy)} tickers, {len(fotos)} días en historial)")

    # Una foto por fecha (si por algún motivo hay dos líneas de la misma
    # fecha en el archivo, se queda con la última).
    por_fecha = {}
    for f in fotos:
        if f.get("fecha"):
            por_fecha[f["fecha"]] = f.get("rs", {})
    fechas = sorted(por_fecha.keys())
    if fecha_hoy not in fechas:
        return {}
    idx_hoy = fechas.index(fecha_hoy)

    def _foto_hace(n_ruedas):
        idx = idx_hoy - n_ruedas
        return por_fecha[fechas[idx]] if idx >= 0 else None

    foto_ayer = _foto_hace(1)
    foto_semana = _foto_hace(VENTANA_SEMANA_RUEDAS)
    foto_mes = _foto_hace(VENTANA_MES_RUEDAS)

    def _delta(foto, ticker, actual):
        if foto is None:
            return None
        previo = foto.get(ticker)
        if previo is None:
            return None
        return round(actual - previo, 1)

    deltas = {}
    for ticker, actual in rs_hoy.items():
        deltas[ticker] = {
            "Delta_RS_dia": _delta(foto_ayer, ticker, actual),
            "Delta_RS_semana": _delta(foto_semana, ticker, actual),
            "Delta_RS_mes": _delta(foto_mes, ticker, actual),
        }
    return deltas
