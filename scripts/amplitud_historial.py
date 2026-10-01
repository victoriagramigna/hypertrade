"""
Historial diario de amplitud del mercado (% del universo sobre su SMA50
y su SMA200) -- para poder graficar la TENDENCIA de los últimos ~2 meses,
no solo la foto de hoy. Responde a la pregunta "¿cada vez son menos las
acciones que sostienen el mercado?" (ver charla con Victoria, 30/9,
comparando contra otro panel).

Guarda, una vez por día, los mismos dos porcentajes que ya calcula
regimen_score.py (amplitud_sma50_pct, amplitud_sma200_pct) en un
historial append-only (data/amplitud_historial.jsonl). Es puramente
informativo: no cambia el Régimen Score ni ningún otro cálculo, solo
guarda día a día un número que ya se calculaba.
"""
import json
import logging
import os

log = logging.getLogger("radar.amplitud_historial")

RUTA_HISTORIAL = "data/amplitud_historial.jsonl"
DIAS_A_DEVOLVER = 45   # ~2 meses de ruedas hábiles, como el panel que la inspiró


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


def registrar_y_obtener_serie(pct_sma50, pct_sma200, fecha_hoy: str) -> list:
    """
    Appendea la foto de hoy (si no hay una ya) y devuelve los últimos
    DIAS_A_DEVOLVER días como lista de {fecha, pct_sma50, pct_sma200},
    ordenada de más vieja a más nueva (lista para graficar tal cual).
    """
    fotos = _leer_fotos()
    ya_hoy = any(f.get("fecha") == fecha_hoy for f in fotos)
    if not ya_hoy and pct_sma50 is not None and pct_sma200 is not None:
        nueva = {"fecha": fecha_hoy, "pct_sma50": round(float(pct_sma50), 1),
                  "pct_sma200": round(float(pct_sma200), 1)}
        with open(RUTA_HISTORIAL, "a", encoding="utf-8") as f:
            f.write(json.dumps(nueva, ensure_ascii=False) + "\n")
        fotos.append(nueva)
        log.info(f"Amplitud de hoy ({fecha_hoy}) guardada en {RUTA_HISTORIAL}")

    # Una entrada por fecha (si hay duplicados, se queda con la última).
    por_fecha = {}
    for f in fotos:
        if f.get("fecha"):
            por_fecha[f["fecha"]] = f
    serie = [por_fecha[fch] for fch in sorted(por_fecha.keys())]
    return serie[-DIAS_A_DEVOLVER:]
