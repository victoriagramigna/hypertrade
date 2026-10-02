"""
Confluencia Alcista -- filtro duro sobre chips que YA se calculan hoy
(AVWAP SOPORTE, CRUCE 52W, TENDENCIA+, ATR COMPRIMIDO), ignorando a
propósito el Radar Score. Idea sugerida por Victoria a partir de una
conversación con Gemini sobre el "Warren Dashboard".

Filosofía: un solo número compuesto (el Radar Score) puede esconder que
varias razones técnicas INDEPENDIENTES están apuntando para el mismo lado
al mismo tiempo. Si un ticker prende al menos CHIPS_MINIMOS de estos 4
chips dentro de las últimas VENTANA_CHIP_HORAS horas, hay más de una
confirmación distinta -- vale la pena mirarlo aunque su Radar Score no sea
el más alto del universo ese día.

No agrega ningún indicador nuevo: los 4 chips ya se calculan en
radar_score.py para TODO el universo (no solo los tickers con alerta
activa). Lo único nuevo acá es la MEMORIA de "cuándo se vio por última vez
cada chip", necesaria porque "Cruce_AVWAP_52w" es un evento de un solo día
(hoy vs. ayer) y los otros tres son condiciones que pueden prenderse y
apagarse de una corrida a otra sin que eso signifique que dejaron de tener
vigencia dentro de las 48hs.

Guarda su PROPIO archivo persistente (data/chips_historial.json), separado
de data/historial_alertas.json a propósito: ese otro archivo lo reescribe
alertas.py por ticker ENTERO en cada corrida (historial[ticker] = {...}),
así que cualquier campo nuevo que se guardara ahí se perdería en la
corrida siguiente sin este archivo aparte.

Las filas que devuelve detectar_confluencia() están armadas con el MISMO
formato que usa alertas.py, para poder sumarse directamente a df_alertas
en main.py y pasar por el mismo camino de siempre (recomendación final,
puntos de cuidado, narrativa, notificación por Telegram, bitácora y
Auditoría) -- no es un sistema paralelo, es una lectura distinta de datos
que ya existían.
"""
import json
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger("radar.confluencia")

ARCHIVO_CHIPS = "data/chips_historial.json"

# Qué chip vive en qué columna de df_rs (ver radar_score.py), y cómo se
# llama en el dashboard (mismas etiquetas que ya usa docs/index.html).
CHIPS = {
    "apoyo_avwap":     ("Apoyo_AVWAP",      "AVWAP SOPORTE"),
    "cruce_avwap_52w": ("Cruce_AVWAP_52w",  "CRUCE 52W"),
    "pendiente_ok":    ("Pendiente_OK",     "TENDENCIA+"),
    "atr_contraction": ("ATR_Contraction",  "ATR COMPRIMIDO"),
}

VENTANA_CHIP_HORAS = 48      # un chip "cuenta" si estuvo encendido dentro de esta ventana
CHIPS_MINIMOS = 3            # a partir de acá se considera "confluencia" (de 4 chips posibles)
VENTANA_VIGENCIA_HORAS = 48  # cuánto tiempo se sigue mostrando la tarjeta, desde que arrancó


def cargar_chips() -> dict:
    if not os.path.exists(ARCHIVO_CHIPS):
        return {}
    try:
        with open(ARCHIVO_CHIPS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"No se pudo leer {ARCHIVO_CHIPS} ({e}) -- se arranca vacío")
        return {}


def guardar_chips(chips_historial: dict):
    os.makedirs(os.path.dirname(ARCHIVO_CHIPS), exist_ok=True)
    with open(ARCHIVO_CHIPS, "w", encoding="utf-8") as f:
        json.dump(chips_historial, f, ensure_ascii=False, indent=2)


def _horas_desde(fecha_iso, ahora: datetime) -> float:
    if not fecha_iso:
        return float("inf")
    try:
        entonces = datetime.fromisoformat(fecha_iso)
        if entonces.tzinfo is None:
            entonces = entonces.replace(tzinfo=timezone.utc)
        return (ahora - entonces).total_seconds() / 3600
    except Exception:
        return float("inf")


def detectar_confluencia(df_rs, ahora: datetime) -> list:
    """
    df_rs: el universo completo (con las columnas Apoyo_AVWAP,
    Cruce_AVWAP_52w, Pendiente_OK, ATR_Contraction ya calculadas por
    radar_score.py) -- no el subconjunto de alertas activas.

    Devuelve una lista de filas (dict) para los tickers que llegan a
    CHIPS_MINIMOS chips dentro de la ventana, listas para sumarse a
    df_alertas. No filtra ni ordena por Radar Score en ningún paso.
    """
    if df_rs is None or df_rs.empty:
        return []

    chips_historial = cargar_chips()
    filas = []

    for _, fila in df_rs.iterrows():
        ticker = fila.get("Ticker")
        if not ticker:
            continue
        entrada = chips_historial.setdefault(ticker, {})

        chips_activos = []
        chips_prendidos = {}  # clave -> bool, para el desglose con tildes del dashboard
        for clave, (columna, etiqueta) in CHIPS.items():
            if bool(fila.get(columna)):
                entrada[clave] = ahora.isoformat()
            prendido = _horas_desde(entrada.get(clave), ahora) <= VENTANA_CHIP_HORAS
            chips_prendidos[clave] = prendido
            if prendido:
                chips_activos.append(etiqueta)

        if len(chips_activos) >= CHIPS_MINIMOS:
            if not entrada.get("confluencia_activa"):
                # Recién llega a 3+ chips en esta corrida -- arranca la
                # ventana de vigencia ahora, no cada corrida que sigue activa.
                entrada["fecha_evento_confluencia"] = ahora.isoformat()
            entrada["confluencia_activa"] = True
        else:
            entrada["confluencia_activa"] = False

        vigente = (
            entrada.get("confluencia_activa")
            and _horas_desde(entrada.get("fecha_evento_confluencia"), ahora) <= VENTANA_VIGENCIA_HORAS
        )
        if vigente:
            filas.append({
                "Ticker": ticker,
                "Sector": fila.get("Sector"),
                "Tipo": "confluencia_alcista",
                "Estado": "🎯 Confluencia Alcista",
                "Score": f"{len(chips_activos)}/4 chips",
                "Score_num": None,
                "Señales": chips_activos,
                # Mismo desglose con tildes que el resto de las señales
                # (ver alertas.py) -- a pedido de Victoria (1/10), faltaba
                # acá. Los 4 chips son justamente los que ya se muestran
                # arriba como badges; esto solo los repite en formato
                # desplegable con su explicación de qué significa cada uno.
                "Score_detalle": chips_prendidos,
                "RSI": fila.get("RSI"),
                "Vol_rel": fila.get("Vol_rel"),
                "Precio": fila.get("Precio"),
                "fecha_evento": entrada["fecha_evento_confluencia"],
            })

    guardar_chips(chips_historial)
    return filas
