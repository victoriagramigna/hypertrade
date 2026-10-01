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

# Mismo mecanismo, ahora también para el Top 30 por RADAR SCORE (a pedido
# de Victoria, 1/10: "quiero el ranking del score, de características
# similares al de fuerza relativa") -- archivo de historial aparte, nunca
# se mezcla con el de RS Score.
RUTA_HISTORIAL_DIARIO_RADAR = "data/top30_radar_diario.jsonl"


def _leer_fotos(ruta):
    if not os.path.exists(ruta):
        return []
    fotos = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                fotos.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return fotos


def _registrar_y_comparar(df_rs, columna: str, ruta_historial: str, fecha_hoy: str) -> dict:
    """
    Motor genérico: arma el Top 30 por la columna indicada (RS_Score o
    Radar_Score), lo compara contra la última foto guardada en
    ruta_historial, y appendea la foto de hoy (salvo que ya exista una).

    Devuelve {"nuevos": [...], "salientes": [...], "fecha_comparacion": str|None}
    """
    vacio = {"nuevos": [], "salientes": [], "fecha_comparacion": None}
    if df_rs is None or df_rs.empty or columna not in df_rs.columns:
        return vacio

    top30_hoy = set(
        df_rs.sort_values(columna, ascending=False).head(30)["Ticker"].tolist()
    )

    fotos = _leer_fotos(ruta_historial)
    ya_hoy = any(f.get("fecha") == fecha_hoy for f in fotos)
    if not ya_hoy:
        with open(ruta_historial, "a", encoding="utf-8") as f:
            f.write(json.dumps({"fecha": fecha_hoy, "tickers": sorted(top30_hoy)}, ensure_ascii=False) + "\n")
        log.info(f"Top 30 ({columna}) de hoy ({fecha_hoy}) guardado en {ruta_historial}")

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


def registrar_y_comparar_top30(df_rs, fecha_hoy: str) -> dict:
    """Top 30 por Fuerza Relativa (RS Score) -- el de siempre."""
    return _registrar_y_comparar(df_rs, "RS_Score", RUTA_HISTORIAL_DIARIO, fecha_hoy)


def registrar_y_comparar_top30_radar(df_rs, fecha_hoy: str) -> dict:
    """Top 30 por Radar Score -- el compuesto con volumen/tendencia/AVWAP/etc."""
    return _registrar_y_comparar(df_rs, "Radar_Score", RUTA_HISTORIAL_DIARIO_RADAR, fecha_hoy)
