"""
Contexto macro-local real, vía ArgentinaDatos (api.argentinadatos.com -- gratis,
sin token). Si alguna fuente falla, devuelve None en vez de romper la corrida --
evaluar_contexto_macro() en contexto.py ya sabe manejar ese caso ("sin_datos").
"""
import logging
import requests

log = logging.getLogger("radar.macro_local")

BASE = "https://api.argentinadatos.com/v1"
TIMEOUT = 10


def traer_riesgo_pais():
    """Devuelve (valor_hoy, valor_ayer) o (None, None) si falla."""
    try:
        resp = requests.get(f"{BASE}/finanzas/indices/riesgo-pais", timeout=TIMEOUT)
        resp.raise_for_status()
        serie = resp.json()
        if len(serie) < 2:
            return None, None
        valor_hoy = float(serie[-1]["valor"])
        valor_ayer = float(serie[-2]["valor"])
        return valor_hoy, valor_ayer
    except Exception as e:
        log.warning(f"No se pudo traer riesgo país: {e}")
        return None, None


def traer_brecha_cambiaria():
    """Devuelve el % de brecha entre dólar blue y oficial, o None si falla."""
    try:
        resp = requests.get(f"{BASE}/cotizaciones/dolares", timeout=TIMEOUT)
        resp.raise_for_status()
        cotizaciones = resp.json()
        oficial = next((c for c in cotizaciones if c["casa"] == "oficial"), None)
        blue = next((c for c in cotizaciones if c["casa"] == "blue"), None)
        if not oficial or not blue:
            return None
        venta_oficial = float(oficial["venta"])
        venta_blue = float(blue["venta"])
        if venta_oficial <= 0:
            return None
        return (venta_blue / venta_oficial - 1) * 100
    except Exception as e:
        log.warning(f"No se pudo traer cotizaciones de dólar: {e}")
        return None


def traer_contexto_macro():
    """Punto de entrada único: trae todo lo necesario para evaluar_contexto_macro()."""
    riesgo_hoy, riesgo_ayer = traer_riesgo_pais()
    brecha = traer_brecha_cambiaria()
    return riesgo_hoy, riesgo_ayer, brecha
