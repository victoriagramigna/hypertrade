"""
Frescura del dato. No usa una librería de feriados (evita otra dependencia
a mantener) -- en cambio, calcula cuántos DÍAS HÁBILES pasaron desde el
último dato de mercado hasta hoy. Un feriado normal (1-2 días hábiles
"saltados") es esperable y no dispara alerta. Un gap más largo sí, porque
sugiere que algo se rompió (la fuente de datos, el cron, etc.), no un
feriado común.
"""
import logging
import pandas as pd
from datetime import datetime, timezone

log = logging.getLogger("radar.frescura")

DIAS_HABILES_GAP_SOSPECHOSO = 3  # más de esto sin dato nuevo = alerta


def evaluar_frescura(ultima_fecha_dato) -> dict:
    """
    ultima_fecha_dato: el índice de fecha del último precio del benchmark
    (pandas Timestamp o similar). Devuelve un dict con la fecha, cuántos
    días hábiles de gap hay, y si es sospechoso.
    """
    if ultima_fecha_dato is None:
        return {"fecha_ultimo_dato": None, "gap_dias_habiles": None, "sospechoso": True,
                "motivo": "no se pudo determinar la fecha del último dato"}

    hoy = pd.Timestamp(datetime.now(timezone.utc).date())
    fecha_dato = pd.Timestamp(ultima_fecha_dato).normalize()
    if fecha_dato.tz is not None:
        fecha_dato = fecha_dato.tz_localize(None)

    # Días hábiles (lunes a viernes) entre el último dato y hoy, sin contar el propio día del dato
    rango = pd.bdate_range(start=fecha_dato, end=hoy)
    gap = max(len(rango) - 1, 0)

    sospechoso = gap > DIAS_HABILES_GAP_SOSPECHOSO
    resultado = {
        "fecha_ultimo_dato": fecha_dato.strftime("%Y-%m-%d"),
        "gap_dias_habiles": gap,
        "sospechoso": sospechoso,
    }
    if sospechoso:
        resultado["motivo"] = (f"último dato de mercado es de hace {gap} días hábiles -- "
                                f"más que un feriado común, revisar si la fuente de datos falló")
        log.warning(resultado["motivo"])
    return resultado
