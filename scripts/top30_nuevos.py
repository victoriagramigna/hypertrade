"""
Nuevos ingresos diarios al Top 30 de Fuerza Relativa (RS Score).

Guarda, una vez por día, la lista de tickers que integran el Top 30 de
RS Score en un historial diario (data/top30_diario.jsonl, append-only --
nunca se reescribe ni se borra). Comparando la foto de hoy contra la
última foto guardada (normalmente ayer, o el último día hábil anterior)
se puede mostrar qué tickers son NUEVOS en el Top 30 hoy -- una señal
temprana de liderazgo que recién está apareciendo, útil para ver de un
vistazo "quién está entrando" sin tener que revisar los 30 todos los
días a mano.

Es información puramente agregada sobre algo que YA existía (el Top 30
de RS Score de siempre, que se muestra hace rato en "Universo"). No
cambia ni un solo cálculo de ninguna señal existente, ni de la
Auditoría -- por eso no necesita ningún corte de metodología.
"""
import json
import logging
import os

log = logging.getLogger("radar.top30_nuevos")

RUTA_HISTORIAL_DIARIO = "data/top30_diario.jsonl"


def _leer_fotos():
    if not os.path.exists(RUTA_HISTORIAL_DIARIO):
        return []
    fotos = []
    with open(RUTA_HISTORIAL_DIARIO, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                fotos.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return fotos


def registrar_y_comparar_top30(df_rs, fecha_hoy: str) -> dict:
    """
    df_rs: DataFrame ya calculado, con columnas 'Ticker' y 'RS_Score'.
    fecha_hoy: 'YYYY-MM-DD'.

    Devuelve:
        {"nuevos": [...], "salientes": [...], "fecha_comparacion": str|None}

    Y de paso appendea la foto de hoy al historial diario -- salvo que ya
    haya una foto de hoy guardada (una segunda corrida el mismo día no
    debe duplicar ni pisar la entrada).
    """
    vacio = {"nuevos": [], "salientes": [], "fecha_comparacion": None}
    if df_rs is None or df_rs.empty or "RS_Score" not in df_rs.columns:
        return vacio

    top30_hoy = set(
        df_rs.sort_values("RS_Score", ascending=False).head(30)["Ticker"].tolist()
    )

    fotos = _leer_fotos()
    ya_hoy = any(f.get("fecha") == fecha_hoy for f in fotos)
    if not ya_hoy:
        with open(RUTA_HISTORIAL_DIARIO, "a", encoding="utf-8") as f:
            f.write(json.dumps({"fecha": fecha_hoy, "tickers": sorted(top30_hoy)}, ensure_ascii=False) + "\n")
        log.info(f"Top 30 de hoy ({fecha_hoy}) guardado en {RUTA_HISTORIAL_DIARIO}")

    # Foto previa: la última guardada con fecha ANTERIOR a hoy (ignora la
    # que se acaba de agregar arriba, si la hubo).
    previas = [f for f in fotos if f.get("fecha") and f["fecha"] < fecha_hoy]
    if not previas:
        return vacio
    previa = max(previas, key=lambda f: f["fecha"])
    top30_previo = set(previa.get("tickers", []))

    return {
        "nuevos": sorted(top30_hoy - top30_previo),
        "salientes": sorted(top30_previo - top30_hoy),
        "fecha_comparacion": previa["fecha"],
    }
