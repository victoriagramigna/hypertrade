"""
Cuadrante de Rotación Sectorial -- idea del dossier "Warren Bife" que trajo
Victoria, adaptada para que además de graficarse, SUME algo medible (ella
misma lo señaló: "no sería poner en un gráfico cosas que ya medimos?").

Cada sector se ubica en uno de 4 cuadrantes según:
  - Eje Y: su RS_Score sectorial de HOY (0-100, el mismo promedio que ya
    se muestra en "Rotación Sectorial") -- ¿está fuerte o débil?
  - Eje X: cuánto cambió ese RS_Score en los últimos 7 días -- ¿está
    mejorando o empeorando?

    RS alto  | DEBILITÁNDOSE   |   LÍDER
             |-----------------+-----------------
    RS bajo  | REZAGADO        |   MEJORANDO
             empeorando (X<0)     mejorando (X>0)

Lo nuevo de verdad (lo que lo hace medible, no solo un gráfico): cuando un
sector CAMBIA de cuadrante, se registra el evento con fecha en
data/log_rotacion_sectorial.jsonl -- igual que cualquier otra señal de la
app. auditoria_rotacion.py después revisa: cuando un sector entra a Líder
o Mejorando, ¿sus tickers le ganaron al SPY en las semanas siguientes? Y
al revés para Debilitándose/Rezagado. Esa es la hipótesis que se pone a
prueba, no solo una foto bonita.
"""
import json
import logging
import os
from datetime import datetime, timezone, timedelta

log = logging.getLogger("radar.rotacion_sectorial")

RUTA_HISTORIAL_RS = "data/rs_sector_historial.jsonl"   # snapshots diarios de RS por sector
RUTA_ESTADO = "data/rotacion_sectorial_estado.json"     # último cuadrante conocido de cada sector
RUTA_LOG_TRANSICIONES = "data/log_rotacion_sectorial.jsonl"  # bitácora de cambios de cuadrante

UMBRAL_FUERTE_DEBIL = 50   # eje Y: RS sectorial a partir de acá se considera "fuerte"
DIAS_DELTA = 7             # eje X: contra qué antigüedad se mide el cambio
TOLERANCIA_DIAS = 2        # margen para encontrar el snapshot de "hace 7 días" (no siempre va a caer justo)

CUADRANTES = {
    (True, True):   "Líder",           # fuerte + mejorando
    (True, False):  "Debilitándose",   # fuerte + empeorando
    (False, True):  "Mejorando",       # débil + mejorando
    (False, False): "Rezagado",        # débil + empeorando
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


def _guardar_snapshot_diario(rs_por_sector: dict, ahora: datetime):
    """Un snapshot por DÍA, no por corrida -- si no, con corridas cada 30
    min este archivo crecería sin sentido. Si ya se guardó uno hoy, no
    duplica (pisa el de hoy con el valor más reciente de la jornada)."""
    fecha_hoy = ahora.date().isoformat()
    filas = _leer_jsonl(RUTA_HISTORIAL_RS)
    filas = [f for f in filas if f.get("fecha") != fecha_hoy]
    filas.append({"fecha": fecha_hoy, "timestamp": ahora.isoformat(), "rs_por_sector": rs_por_sector})
    # Nunca hace falta más de ~60 días de historial para un delta de 7 días
    # -- se poda para que el archivo no crezca indefinidamente.
    filas = sorted(filas, key=lambda f: f.get("fecha", ""))[-60:]
    os.makedirs(os.path.dirname(RUTA_HISTORIAL_RS), exist_ok=True)
    with open(RUTA_HISTORIAL_RS, "w", encoding="utf-8") as f:
        for fila in filas:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return filas


def _valor_hace_7_dias(historial: list, sector: str, ahora: datetime):
    """Busca, entre los snapshots guardados, el más cercano a hace 7 días
    (con tolerancia) para este sector. None si todavía no hay suficiente
    historial (recién arrancando) o el sector no estaba en ese snapshot."""
    objetivo = ahora.date() - timedelta(days=DIAS_DELTA)
    mejor, mejor_dist = None, None
    for fila in historial:
        try:
            fecha = datetime.fromisoformat(fila["fecha"]).date()
        except (KeyError, ValueError):
            continue
        dist = abs((fecha - objetivo).days)
        if dist <= TOLERANCIA_DIAS and (mejor_dist is None or dist < mejor_dist):
            valor = fila.get("rs_por_sector", {}).get(sector)
            if valor is not None:
                mejor, mejor_dist = valor, dist
    return mejor


def actualizar_rotacion_sectorial(rs_por_sector: dict, tickers_sector: dict, ahora: datetime) -> tuple:
    """
    rs_por_sector: {sector: RS_Score promedio}, el mismo dato que ya arma
    main.py para "Rotación Sectorial" -- no se recalcula nada de cero.
    tickers_sector: TICKERS de config.py, para contar cuántos tickers tiene
    cada sector (contexto, se muestra en el punto del gráfico).

    Devuelve (puntos, eventos_nuevos):
      - puntos: la lista para el gráfico (uno por sector) -- MISMO formato
        de siempre, lo que ya consumen el dashboard y la Auditoría de
        Rotación no cambia en nada.
      - eventos_nuevos: las transiciones de cuadrante detectadas en ESTA
        corrida (lista vacía si no hubo ninguna). Ya quedan logueadas en
        RUTA_LOG_TRANSICIONES de todos modos (como siempre); esto solo se
        agrega (10/2) para que quien llama pueda avisar por Telegram sin
        tener que releer ese archivo.
    """
    if not rs_por_sector:
        return [], []

    historial = _guardar_snapshot_diario(rs_por_sector, ahora)
    estado = _cargar_estado()
    n_por_sector = {}
    for _, sector in tickers_sector.items():
        n_por_sector[sector] = n_por_sector.get(sector, 0) + 1

    puntos = []
    eventos_nuevos = []

    for sector, rs_hoy in rs_por_sector.items():
        rs_hace_7d = _valor_hace_7_dias(historial, sector, ahora)
        delta_7d = round(rs_hoy - rs_hace_7d, 1) if rs_hace_7d is not None else None

        cuadrante = None
        if delta_7d is not None:
            fuerte = rs_hoy >= UMBRAL_FUERTE_DEBIL
            mejorando = delta_7d > 0
            cuadrante = CUADRANTES[(fuerte, mejorando)]

        punto = {
            "Sector": sector,
            "RS_Sector": round(rs_hoy, 1),
            "Delta_7d": delta_7d,
            "Cuadrante": cuadrante,
            "N_Tickers": n_por_sector.get(sector, 0),
        }
        puntos.append(punto)

        # --- Transición de cuadrante: solo se registra si CAMBIÓ respecto
        # a la última vez, y solo si hay cuadrante calculado (con historial
        # insuficiente, no se loguea nada -- mejor no medir que medir mal). ---
        if cuadrante is None:
            continue
        previo = estado.get(sector, {})
        cuadrante_previo = previo.get("cuadrante")
        if cuadrante_previo == cuadrante:
            continue  # sigue en el mismo cuadrante, nada que registrar

        evento = {
            "timestamp": ahora.isoformat(),
            "sector": sector,
            "cuadrante_anterior": cuadrante_previo,  # None la primera vez que se puede clasificar
            "cuadrante_nuevo": cuadrante,
            "rs_sector": punto["RS_Sector"],
            "delta_7d": delta_7d,
            "n_tickers": punto["N_Tickers"],
        }
        eventos_nuevos.append(evento)
        estado[sector] = {"cuadrante": cuadrante, "fecha_evento": ahora.isoformat()}

    if eventos_nuevos:
        os.makedirs(os.path.dirname(RUTA_LOG_TRANSICIONES), exist_ok=True)
        with open(RUTA_LOG_TRANSICIONES, "a", encoding="utf-8") as f:
            for ev in eventos_nuevos:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        log.info(f"Rotación sectorial: {len(eventos_nuevos)} transición(es) de cuadrante nueva(s): "
                 + ", ".join(f"{e['sector']} -> {e['cuadrante_nuevo']}" for e in eventos_nuevos))
        _guardar_estado(estado)

    return sorted(puntos, key=lambda p: p["Sector"]), eventos_nuevos
