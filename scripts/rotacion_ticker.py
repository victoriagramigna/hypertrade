"""
Cuadrante de Rotación por TICKER -- misma idea que rotacion_sectorial.py
(mismo dossier "Warren Bife"), pero mirando cada ticker individual en vez
del promedio del sector. Pedido de Victoria (2/10, viendo la versión de
"Warren Bife" con buscador de ticker): poder ubicar un ticker puntual
(ej. "XLK") en el cuadrante, no solo el sector entero al que pertenece.

No inventa ningún cálculo nuevo -- reutiliza datos que YA existen:
  - Eje Y: RS_Score de HOY de cada ticker (el de siempre, contra el SPY)
  - Eje X: Delta_RS_semana (de rs_deltas.py -- ya guarda un historial
    diario de RS_Score por ticker en data/rs_score_historial.jsonl desde
    el 1/10; main.py se lo agrega a df_rs antes de llamar a este módulo)

Mismos cuadrantes, mismo umbral (RS >= 50 = "fuerte") que la versión
sectorial -- para que ambas vistas sean comparables y no haya dos
criterios distintos convivendo en la app.

Igual que en el sectorial, cuando un ticker CAMBIA de cuadrante se
registra el evento con fecha -- eso es lo que alimenta "Recién a
Líderes" y, más adelante, permitiría auditar si un ticker que entra a
Líder/Mejorando le gana después al SPY (misma lógica que
auditoria_rotacion.py, pero no se integra todavía: es un paso futuro,
no bloquea esta entrega).

"Aceleración inusual": los tickers con el Delta_RS_semana más alto de
HOY (no negativo) -- no es un cálculo nuevo, es ordenar una columna que
ya existe. No confundir con el Radar Score ni con ninguna alerta.
"""
import json
import logging
import os
from datetime import datetime

log = logging.getLogger("radar.rotacion_ticker")

RUTA_ESTADO = "data/rotacion_ticker_estado.json"
RUTA_LOG_TRANSICIONES = "data/log_rotacion_ticker.jsonl"

UMBRAL_FUERTE_DEBIL = 50
DIAS_RECIEN_A_LIDERES = 10   # ventana para considerar una transición "reciente"
TOPE_ACELERACION_INUSUAL = 12

CUADRANTES = {
    (True, True): "Líder",
    (True, False): "Debilitándose",
    (False, True): "Mejorando",
    (False, False): "Rezagado",
}


def _leer_jsonl(ruta):
    if not os.path.exists(ruta):
        return []
    filas = []
    with open(ruta, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                filas.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return filas


def _cargar_estado():
    if not os.path.exists(RUTA_ESTADO):
        return {}
    try:
        with open(RUTA_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"No se pudo leer {RUTA_ESTADO} ({e}) -- se arranca vacío")
        return {}


def _guardar_estado(estado: dict):
    os.makedirs(os.path.dirname(RUTA_ESTADO), exist_ok=True)
    with open(RUTA_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def _recien_a_lideres(ahora: datetime, dias: int = DIAS_RECIEN_A_LIDERES) -> list:
    eventos = _leer_jsonl(RUTA_LOG_TRANSICIONES)
    por_ticker_mas_reciente = {}
    for ev in eventos:
        if ev.get("cuadrante_nuevo") not in ("Líder", "Mejorando"):
            continue
        try:
            fecha_ev = datetime.fromisoformat(ev["timestamp"]).date()
        except (KeyError, ValueError):
            continue
        dias_desde = (ahora.date() - fecha_ev).days
        if not (0 <= dias_desde <= dias):
            continue
        ev_con_dias = {**ev, "dias_desde": dias_desde}
        ticker = ev["ticker"]
        actual = por_ticker_mas_reciente.get(ticker)
        if actual is None or ev["timestamp"] > actual["timestamp"]:
            por_ticker_mas_reciente[ticker] = ev_con_dias
    return sorted(por_ticker_mas_reciente.values(), key=lambda e: e["timestamp"], reverse=True)


def actualizar_rotacion_ticker(df_rs, ahora: datetime) -> dict:
    """
    df_rs: necesita columnas Ticker, Sector, RS_Score y, si ya está
    disponible, Delta_RS_semana (main.py se la agrega antes de llamar
    acá, vía rs_deltas.py). Si todavía no hay suficiente historial para
    calcular el delta semanal, el ticker queda sin cuadrante -- no se
    inventa ni se estima nada (mismo criterio que rotacion_sectorial.py).

    Devuelve {"puntos": [...], "recien_a_lideres": [...],
    "aceleracion_inusual": [...]}.
    """
    vacio = {"puntos": [], "recien_a_lideres": [], "aceleracion_inusual": []}
    if df_rs is None or df_rs.empty or "Delta_RS_semana" not in df_rs.columns:
        return vacio

    estado = _cargar_estado()
    puntos = []
    eventos_nuevos = []

    for _, fila in df_rs.iterrows():
        ticker = fila.get("Ticker")
        rs_hoy = fila.get("RS_Score")
        if ticker is None or rs_hoy is None:
            continue
        delta = fila.get("Delta_RS_semana")

        cuadrante = None
        if delta is not None:
            fuerte = rs_hoy >= UMBRAL_FUERTE_DEBIL
            mejorando = delta > 0
            cuadrante = CUADRANTES[(fuerte, mejorando)]

        sobre_sma50 = fila.get("Sobre_SMA50")
        punto = {
            "Ticker": ticker,
            "Sector": fila.get("Sector"),
            "Es_ETF": fila.get("Sector") == "ETF",
            "RS_Score": round(float(rs_hoy), 1),
            "Delta_RS_semana": delta,
            "Sobre_SMA50": bool(sobre_sma50) if sobre_sma50 is not None else None,
            "Cuadrante": cuadrante,
        }
        puntos.append(punto)

        if cuadrante is None:
            continue
        previo = estado.get(ticker, {})
        cuadrante_previo = previo.get("cuadrante")
        if cuadrante_previo == cuadrante:
            continue

        evento = {
            "timestamp": ahora.isoformat(),
            "ticker": ticker,
            "sector": fila.get("Sector"),
            "es_etf": punto["Es_ETF"],
            "cuadrante_anterior": cuadrante_previo,
            "cuadrante_nuevo": cuadrante,
            "rs_score": punto["RS_Score"],
            "delta_rs_semana": delta,
        }
        eventos_nuevos.append(evento)
        estado[ticker] = {"cuadrante": cuadrante, "fecha_evento": ahora.isoformat()}

    if eventos_nuevos:
        os.makedirs(os.path.dirname(RUTA_LOG_TRANSICIONES), exist_ok=True)
        with open(RUTA_LOG_TRANSICIONES, "a", encoding="utf-8") as f:
            for ev in eventos_nuevos:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        log.info(f"Rotación por ticker: {len(eventos_nuevos)} transición(es) nueva(s): "
                 + ", ".join(f"{e['ticker']} -> {e['cuadrante_nuevo']}" for e in eventos_nuevos))
        _guardar_estado(estado)

    candidatos_aceleracion = [p for p in puntos if (p["Delta_RS_semana"] or 0) > 0]
    aceleracion_inusual = sorted(
        candidatos_aceleracion, key=lambda p: p["Delta_RS_semana"], reverse=True
    )[:TOPE_ACELERACION_INUSUAL]

    return {
        "puntos": sorted(puntos, key=lambda p: p["Ticker"]),
        "recien_a_lideres": _recien_a_lideres(ahora),
        "aceleracion_inusual": aceleracion_inusual,
    }
