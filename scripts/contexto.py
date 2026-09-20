"""
Capa de contexto: ajusta la señal técnica según noticias sectoriales y
contexto macro-local. Si una fuente falla, se degrada a "sin datos de contexto"
en vez de romper la corrida -- ver punto de robustez acordado en el diseño.
"""
import logging
from config import PALABRAS_CLAVE_SECTOR, RIESGO_PAIS_VARIACION_ALERTA, BRECHA_CAMBIARIA_ALERTA_PCT

log = logging.getLogger("radar.contexto")


def escanear_titulares(titulares: list[str]) -> dict:
    alertas_sector = {}
    for titular in titulares:
        titular_lower = titular.lower()
        for sector, palabras in PALABRAS_CLAVE_SECTOR.items():
            for palabra in palabras:
                if palabra in titular_lower:
                    alertas_sector.setdefault(sector, []).append(titular)
                    break
    return alertas_sector


def evaluar_contexto_macro(riesgo_pais, riesgo_pais_ayer, brecha_cambiaria_pct) -> dict:
    """Si algún dato viene None (fuente falló), se marca 'sin_datos' en vez de fallar."""
    if riesgo_pais is None or riesgo_pais_ayer is None or brecha_cambiaria_pct is None:
        return {"estable": None, "sin_datos": True, "motivos": ["fuente de contexto macro no disponible hoy"]}

    variacion = (riesgo_pais - riesgo_pais_ayer) / riesgo_pais_ayer if riesgo_pais_ayer else 0
    inestable, motivos = False, []
    if abs(variacion) > RIESGO_PAIS_VARIACION_ALERTA:
        inestable = True
        motivos.append(f"riesgo país {'subió' if variacion > 0 else 'bajó'} {abs(variacion)*100:.1f}% hoy")
    if brecha_cambiaria_pct > BRECHA_CAMBIARIA_ALERTA_PCT:
        inestable = True
        motivos.append(f"brecha cambiaria en {brecha_cambiaria_pct:.0f}%")

    return {
        "estable": not inestable, "sin_datos": False,
        "riesgo_pais": riesgo_pais, "variacion_riesgo_%": round(variacion * 100, 1),
        "brecha_cambiaria_%": brecha_cambiaria_pct, "motivos": motivos,
    }


def recomendacion_final(sector, score_tecnico, evento_tecnico, alertas_sector, contexto_macro):
    if evento_tecnico and "Rompió piso" in evento_tecnico:
        base = "VENTA"
    elif evento_tecnico and ("Líder apoyando en soporte" in evento_tecnico or "Gap alcista" in evento_tecnico):
        base = "COMPRA"  # tipos de señal distintos al score 0-7 -- ya vienen con su propia lógica de entrada
    elif evento_tecnico and score_tecnico and score_tecnico >= 4:
        base = "COMPRA"
    else:
        base = "MANTENER"

    ajustes, final = [], base
    if sector in alertas_sector:
        ajustes.append(f"riesgo sectorial activo ({len(alertas_sector[sector])} titular/es)")
        if base == "COMPRA":
            final = "MANTENER"

    if contexto_macro.get("sin_datos"):
        ajustes.append("contexto macro no disponible hoy — recomendación basada solo en lo técnico")
    elif not contexto_macro["estable"]:
        ajustes.append("contexto macro inestable: " + "; ".join(contexto_macro["motivos"]))
        if base == "COMPRA":
            final = "MANTENER"

    return {
        "Señal técnica": base,
        "Recomendación final": final,
        "Ajustado por": "; ".join(ajustes) if ajustes else "sin ajustes",
        "disclaimer": "Señal técnica basada en reglas propias, no es recomendación de inversión.",
    }
