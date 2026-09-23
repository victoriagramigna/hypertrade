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

from telegram_bot import enviar_mensaje

log = logging.getLogger("radar.cartera")

RUTA_CARTERA = "data/mi_cartera.json"
# Memoria de avisos ya mandados, APARTE de mi_cartera.json: ese archivo lo
# pisa el dashboard cada vez que sincroniza, así que cualquier marca que
# se guardara adentro se perdía y el mismo aviso salía en cada corrida.
# Este archivo solo lo escribe el radar y lo sube el workflow.
RUTA_AVISOS = "data/cartera_avisos.json"
SMA50_TOLERANCIA_PCT = 2  # mismo margen que el dashboard y Alertas

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

    # Trailing: el stop solo puede subir -- mismas reglas que el dashboard
    # (SMA50 -2% en cada corrida si protege más, equilibrio desde +20%)
    if sma50 is not None:
        p["stopActual"] = max(p["stopActual"], sma50 * 0.98)
    if ganancia_pct is not None and ganancia_pct >= GANANCIA_PARCIAL_PCT:
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

    dist50 = ticker_data.get("Dist_SMA50_%") if ticker_data else None
    if dist50 is not None and dist50 < -SMA50_TOLERANCIA_PCT:
        avisos_candidatos.append(("perdio_sma50", f"⚠️ {p['ticker']}: perdió el soporte de su SMA50 ({dist50:.1f}%)"))

    return p, avisos_candidatos


def _clave_posicion(p: dict) -> str:
    return f"{p.get('ticker', '').upper()}|{p.get('fecha')}|{p.get('precio')}"


def _cargar_avisos() -> dict:
    if not os.path.exists(RUTA_AVISOS):
        return {}
    try:
        with open(RUTA_AVISOS, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_avisos(avisos: dict):
    os.makedirs("data", exist_ok=True)
    with open(RUTA_AVISOS, "w", encoding="utf-8") as f:
        json.dump(avisos, f, ensure_ascii=False, indent=2)


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

    # Un aviso se manda cuando la condición EMPIEZA (no estaba activa en la
    # corrida anterior). Mientras siga igual, no se repite. Si desaparece
    # (ej: el precio se aleja del stop) y después vuelve, se avisa de nuevo.
    memoria = _cargar_avisos()
    memoria_nueva = {}
    todos_los_avisos = []
    for p in posiciones:
        ticker_data = ranking_por_ticker.get(p.get("ticker", "").upper()) or ranking_por_ticker.get(p.get("ticker"))
        _, candidatos = _evaluar_posicion(p, ticker_data, fecha_hoy)
        clave = _clave_posicion(p)
        activos_antes = set(memoria.get(clave, []))
        for tipo, texto in candidatos:
            if tipo not in activos_antes:
                todos_los_avisos.append({"tipo": tipo, "texto": texto})
        memoria_nueva[clave] = [tipo for tipo, _ in candidatos]

    # mi_cartera.json NO se reescribe acá: lo maneja el dashboard (que es
    # quien sincroniza el stop). Pisarlo desde el radar podía borrar una
    # compra o venta recién cargada en el celular.

    if not todos_los_avisos:
        log.info("Cartera: sin avisos nuevos")
        if modo == "produccion":
            _guardar_avisos(memoria_nueva)
        return

    log.info(f"Cartera: {len(todos_los_avisos)} aviso(s) nuevo(s)")
    for a in todos_los_avisos:
        log.info(f"  [CARTERA] {a['texto']}")

    if modo != "produccion":
        # En test no se manda nada NI se guarda la memoria: así la próxima
        # corrida real sí manda estos avisos.
        log.info("MODO=test -- no se envía nada a Telegram ni se marca como avisado")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    texto = f"<b>💼 Mi Cartera -- {len(todos_los_avisos)} aviso(s)</b>\n\n" + "\n".join(a["texto"] for a in todos_los_avisos)
    if enviar_mensaje(token, chat_id, texto):
        log.info("Cartera: avisos enviados a Telegram")
        _guardar_avisos(memoria_nueva)
    else:
        # No se guarda la memoria: la próxima corrida lo reintenta
        log.warning("Cartera: no se pudo mandar el Telegram -- se reintenta en la próxima corrida")
