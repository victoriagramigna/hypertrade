"""
Régimen de mercado general, vía VIX (índice de volatilidad).
Un VIX alto indica nerviosismo generalizado -- baja la confianza en TODAS
las señales técnicas individuales ese día, independientemente del sector.
"""
import logging
from config import VIX_UMBRAL_ALTO

log = logging.getLogger("radar.regimen")


def evaluar_regimen_mercado(vix_actual: float | None) -> dict:
    """Devuelve si el régimen general es 'sano' o 'volátil'. Si el VIX no
    se pudo traer, se marca sin_datos en vez de romper la corrida."""
    if vix_actual is None:
        return {"sano": None, "sin_datos": True, "vix": None,
                "motivo": "VIX no disponible hoy"}

    sano = vix_actual < VIX_UMBRAL_ALTO
    return {
        "sano": sano,
        "sin_datos": False,
        "vix": round(vix_actual, 2),
        "motivo": None if sano else f"VIX en {vix_actual:.1f} (umbral: {VIX_UMBRAL_ALTO}) -- mercado nervioso",
    }
