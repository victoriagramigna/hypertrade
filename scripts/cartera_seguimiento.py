"""
Seguimiento activo de "Mi Cartera" -- replica en Python las mismas
reglas que ya corren en el dashboard (JavaScript), pero acá SÍ pueden
disparar un mail, porque el backend corre sola varias veces por día
sin que Victoria tenga que tener la página abierta.

data/mi_cartera.json es el puente entre el navegador (donde se carga
la posición) y este pipeline: Victoria pega ahí el JSON que exporta
el dashboard cuando compra o vende algo. Este módulo LEE ese archivo,
actualiza el trailing stop, y lo vuelve a guardar con el stop nuevo
-- así el archivo del repo va evolucionando solo día a día, sin que
haga falta volver a pegar nada salvo cuando cambia la cartera en sí.
"""
import json
import logging
import os

from notificador_email import enviar_email

log = logging.getLogger("radar.cartera")

RUTA_CARTERA = "data/mi_cartera.json"

# Mismos umbrales que en el dashboard (docs/index.html) -- si cambiás
# uno, cambiá el otro para que no queden desincronizados.
STOP_PCT_INICIAL = 0.08
GANANCIA_PARCIAL_PCT = 20
GANANCIA_TRAILING_PCT = 35
CAIDA_RADAR_SCORE = 15
AVISO_PREVIO_STOP_PCT = 1


def cargar_cartera() -> list:
    if not os.path.exists(RUTA_CARTERA):
        return []
    try:
        with open(RUTA_CARTERA, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"No se pudo leer {RUTA_CARTERA}: {e}")
        return []


def guardar_cartera(posiciones: list):
    os.makedirs("data", exist_ok=True)
    with open(RUTA_CARTERA, "w", encoding="utf-8") as f:
        json.dump(posiciones, f, ensure_ascii=False, indent=2)


def _calcular_stop_inicial(precio_compra: float, sma50) -> float:
    stop_pct = precio_compra * (1 - STOP_PCT_INICIAL)
    if sma50 is not None and sma50 < precio_compra:
        return max(stop_pct, sma50 * 0.98)
    return stop_pct


def _evaluar_posicion(p: dict, ticker_data: dict, fecha_hoy: str) -> tuple:
    """
    Devuelve (posicion_actualizada, lista_de_avisos_nuevos). Un aviso
    es un dict {tipo, texto} -- "nuevo" significa que hoy todavía no
    se había mandado ese mismo tipo de aviso para esta posición.
    """
    precio_actual = ticker_data.get("Precio") if ticker_data else None
    sma50 = ticker_data.get("SMA50") if ticker_data else None
    radar_score_actual = ticker_data.get("Radar_Score") if ticker_data else None
    sobre_sma50 = ticker_data.get("Sobre_SMA50") if ticker_data else None

    if p.get("stopInicial") is None:
        p["stopInicial"] = _calcular_stop_inicial(p["precio"], sma50)
        p["stopActual"] = p["stopInicial"]

    ganancia_pct = None
    if precio_actual is not None and p["precio"] > 0:
        ganancia_pct = (precio_actual / p["precio"] - 1) * 100

    # Trailing: el stop solo puede subir
    if ganancia_pct is not None:
        if ganancia_pct >= GANANCIA_TRAILING_PCT and sma50 is not None:
            p["stopActual"] = max(p["stopActual"], sma50 * 0.98)
        elif ganancia_pct >= GANANCIA_PARCIAL_PCT:
            p["stopActual"] = max(p["stopActual"], p["precio"])

    avisos_candidatos = []  # (tipo, texto)

    if precio_actual is not None and p.get("stopActual") is not None:
        dist_stop_pct = (precio_actual - p["stopActual"]) / p["stopActual"] * 100
        if dist_stop_pct <= 0:
            avisos_candidatos.append(("stop_tocado", f"🛑 {p['ticker']}: tocó el stop sugerido (${p['stopActual']:.2f}) -- considerar vender"))
        elif dist_stop_pct <= AVISO_PREVIO_STOP_PCT:
            avisos_candidatos.append(("stop_cerca", f"⚠️ {p['ticker']}: a {dist_stop_pct:.1f}% del stop (${p['stopActual']:.2f}) -- atenta"))

    if ganancia_pct is not None:
        if ganancia_pct >= GANANCIA_TRAILING_PCT:
            avisos_candidatos.append(("ganancia_35", f"💰 {p['ticker']}: +{GANANCIA_TRAILING_PCT}% de ganancia -- evaluar tomar ganancia parcial adicional"))
        elif ganancia_pct >= GANANCIA_PARCIAL_PCT:
            avisos_candidatos.append(("ganancia_20", f"💰 {p['ticker']}: +{GANANCIA_PARCIAL_PCT}% de ganancia -- punto clásico para vender una porción"))

    if radar_score_actual is not None and p.get("radarScoreCompra") is not None:
        caida = p["radarScoreCompra"] - radar_score_actual
        if caida >= CAIDA_RADAR_SCORE:
            avisos_candidatos.append(("radar_score_cae", f"⚠️ {p['ticker']}: Radar Score bajó de {p['radarScoreCompra']:.0f} a {radar_score_actual:.0f} desde la compra"))

    if sobre_sma50 is False:
        avisos_candidatos.append(("perdio_sma50", f"⚠️ {p['ticker']}: perdió el soporte de su SMA50"))

    # Dedup: solo se considera "nuevo" un aviso que hoy todavía no se mandó
    p.setdefault("_avisos_enviados", {})
    avisos_nuevos = []
    for tipo, texto in avisos_candidatos:
        clave = f"{fecha_hoy}|{tipo}"
        if p["_avisos_enviados"].get(tipo) != clave:
            avisos_nuevos.append({"tipo": tipo, "texto": texto})
            p["_avisos_enviados"][tipo] = clave

    return p, avisos_nuevos


def procesar_cartera(df_rs, fecha_hoy: str, email_user: str, email_password: str, email_to: str, modo: str):
    """
    Punto de entrada desde main.py. df_rs: el DataFrame completo del
    universo (con Precio, SMA50, Radar_Score, Sobre_SMA50 ya
    calculados). Lee data/mi_cartera.json, evalúa cada posición,
    manda UN SOLO mail con todos los avisos nuevos juntos (no uno por
    posición, para no saturar), y guarda el archivo actualizado.
    """
    posiciones = cargar_cartera()
    if not posiciones:
        return  # nadie cargó nada en Mi Cartera todavía -- no hay nada que hacer

    ranking_por_ticker = {}
    if not df_rs.empty:
        ranking_por_ticker = df_rs.set_index("Ticker").to_dict(orient="index")

    todos_los_avisos = []
    for p in posiciones:
        ticker_data = ranking_por_ticker.get(p.get("ticker", "").upper()) or ranking_por_ticker.get(p.get("ticker"))
        p_actualizada, avisos = _evaluar_posicion(p, ticker_data, fecha_hoy)
        todos_los_avisos.extend(avisos)

    guardar_cartera(posiciones)

    if not todos_los_avisos:
        log.info("Cartera: sin avisos nuevos")
        return

    log.info(f"Cartera: {len(todos_los_avisos)} aviso(s) nuevo(s)")
    for a in todos_los_avisos:
        log.info(f"  [CARTERA] {a['texto']}")

    if modo != "produccion":
        log.info("MODO=test -- no se envía el mail real, solo se loguea arriba")
        return

    cuerpo = "\n".join(a["texto"] for a in todos_los_avisos)
    enviar_email(
        asunto=f"[Mi Cartera] {len(todos_los_avisos)} aviso(s) -- {fecha_hoy}",
        cuerpo=cuerpo,
        email_user=email_user,
        email_password=email_password,
        email_to=email_to,
    )
