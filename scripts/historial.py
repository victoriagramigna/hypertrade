"""
Historial persistente entre corridas. Sin esto, "confirmación con demora" y
"stop-loss tras rebote" no se pueden calcular -- necesitan saber qué pasó
en corridas anteriores, no solo el estado de hoy.

Se guarda como JSON en el propio repo (data/historial_alertas.json) y el
workflow de GitHub Actions lo commitea junto con ultimo.json en cada corrida.
"""
import json
import logging
import os
from config import ARCHIVO_HISTORIAL

log = logging.getLogger("radar.historial")


def cargar_historial() -> dict:
    if not os.path.exists(ARCHIVO_HISTORIAL):
        return {}
    try:
        with open(ARCHIVO_HISTORIAL, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"No se pudo leer el historial ({e}) -- se arranca vacío")
        return {}


def guardar_historial(historial: dict):
    os.makedirs(os.path.dirname(ARCHIVO_HISTORIAL), exist_ok=True)
    with open(ARCHIVO_HISTORIAL, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)


def actualizar_estado_ticker(historial: dict, ticker: str, fecha: str, **campos):
    """Actualiza (o crea) la entrada de un ticker en el historial con los campos dados."""
    entrada = historial.get(ticker, {})
    entrada["ultima_fecha"] = fecha
    entrada.update(campos)
    historial[ticker] = entrada
    return historial
