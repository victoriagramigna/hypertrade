"""
Golden Cross / Death Cross (SMA50 vs. SMA200) -- a pedido de Victoria,
charla sobre el indicador "All-in-One Pro" (ver resumen de esa
conversación). Golden Cross = SMA50 cruza POR ENCIMA de SMA200 (señal
alcista de mediano/largo plazo). Death Cross = SMA50 cruza POR DEBAJO de
SMA200 (señal bajista).

No agrega ningún cálculo de precio nuevo: SMA50 y SMA200 YA se calculan
para todo el universo en rs_score.py -- este módulo solo mira la relación
entre esos dos valores que ya vienen en df_rs.

EL PROBLEMA QUE RESUELVE "CONFIRMACIÓN CON DEMORA" (charla con Victoria):
cuando el precio está lateralizando, SMA50 y SMA200 pueden terminar muy
parecidas y cruzarse varias veces en pocos días sin que haya una tendencia
real -- eso generaría avisos de "Golden Cross" y "Death Cross" alternados
que no significan nada (ruido, no señal). La solución (mismo espíritu que
"confirmación con demora" que ya se usa en otras señales de esta app, ver
config.py): un cruce CRUDO (SMA50 pasa de un lado al otro de SMA200) no se
cuenta como evento real hasta que el nuevo estado se sostiene
DIAS_CONFIRMACION ruedas seguidas. Si se da vuelta antes de eso, el
contador arranca de nuevo y nunca llega a confirmarse -- exactamente el
comportamiento que evita el ruido de la lateralización.

¿Se pierde la oportunidad por esperar esos días? El estado CRUDO (sin
confirmar todavía) queda visible igual en el dashboard desde el día 1,
con la leyenda de "confirmando, día X de N" -- Victoria no pierde
visibilidad temprana. Lo único que espera la confirmación es lo que
podría generar ruido si se actuara de una: el aviso de Telegram y el
registro en la bitácora/Auditoría (que mide si la señal "funciona" --
medir un cruce que se deshizo al día siguiente ensuciaría esa medición).

Igual que rotacion_sectorial.py / rotacion_ticker.py: estado persistente
en JSON, bitácora propia append-only en JSONL, no toca ningún otro
cálculo ni archivo de esta app.
"""
import json
import logging
import os

log = logging.getLogger("radar.golden_cross")

RUTA_ESTADO = "data/golden_cross_estado.json"
RUTA_LOG = "data/log_golden_cross.jsonl"

# Cuántas ruedas seguidas tiene que sostenerse el nuevo estado (SMA50 por
# encima/por debajo de SMA200) para contarlo como cruce CONFIRMADO. 3
# ruedas: alcanza para filtrar un vaivén de un par de días sin demorar
# tanto la confirmación como para que la señal llegue tarde.
DIAS_CONFIRMACION = 3


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


def actualizar_golden_cross(df_rs, ahora) -> dict:
    """
    df_rs: necesita columnas Ticker, Sector, SMA50, SMA200 (ya las calcula
    rs_score.py para todo el universo). Un ticker sin SMA200 todavía
    (menos de 200 ruedas de historia) queda simplemente sin estado -- no
    se inventa nada.

    Devuelve {"puntos": [...], "eventos": [...]}.
      - puntos: uno por ticker, con el estado crudo de HOY, cuántas ruedas
        lleva así, si ya está confirmado, y cuál fue el último estado
        CONFIRMADO (puede ser distinto del crudo mientras se confirma).
      - eventos: los cruces CONFIRMADOS detectados en ESTA corrida (lista
        vacía si no hubo ninguno). Ya quedan logueados en RUTA_LOG de
        todos modos; esto es para poder avisar por Telegram sin releer
        el archivo.
    """
    vacio = {"puntos": [], "eventos": []}
    if df_rs is None or df_rs.empty or "SMA50" not in df_rs.columns or "SMA200" not in df_rs.columns:
        return vacio

    estado = _cargar_estado()
    puntos = []
    eventos_nuevos = []
    hoy_iso = ahora.isoformat()
    hoy_fecha = ahora.date().isoformat()

    for _, fila in df_rs.iterrows():
        ticker = fila.get("Ticker")
        sma50 = fila.get("SMA50")
        sma200 = fila.get("SMA200")
        if ticker is None or sma50 is None or sma200 is None:
            continue  # sin suficiente historia todavía -- no se calcula nada

        estado_crudo_hoy = "alcista" if sma50 > sma200 else "bajista"
        previo = estado.get(ticker)

        if previo is None:
            # Primera vez que se ve este ticker (arranque de la app, o
            # ticker nuevo en config.py): se "siembra" el estado como YA
            # confirmado, sin loguear ningún evento. Si en vez de esto
            # arrancara el contador de confirmación desde cero, un ticker
            # que viene en tendencia alcista sostenida hace MESES se
            # mostraría como "confirmando, día 1 de 3" -- un estado que en
            # realidad ya está establecido, no un cruce reciente. Mejor
            # asumir que el estado de hoy es el de siempre hasta que se
            # vea lo contrario, que inventar una confirmación en curso.
            dias_en_estado = DIAS_CONFIRMACION
            confirmado_estado = estado_crudo_hoy
        else:
            if estado_crudo_hoy == previo.get("estado_crudo"):
                dias_en_estado = previo.get("dias_en_estado", 1) + 1
            else:
                dias_en_estado = 1  # el crudo cambió hoy -- arranca de nuevo el contador

            confirmado_estado = previo.get("confirmado")
            confirmado_hoy = dias_en_estado >= DIAS_CONFIRMACION

            if confirmado_hoy and confirmado_estado != estado_crudo_hoy:
                # Se sostuvo DIAS_CONFIRMACION ruedas en el estado nuevo:
                # recién ACÁ se cuenta como cruce real.
                tipo = "Golden Cross" if estado_crudo_hoy == "alcista" else "Death Cross"
                evento = {
                    "timestamp": hoy_iso,
                    "ticker": ticker,
                    "sector": fila.get("Sector"),
                    "tipo": tipo,
                    "estado_anterior_confirmado": confirmado_estado,
                    "sma50": round(float(sma50), 2),
                    "sma200": round(float(sma200), 2),
                    "dias_confirmacion": DIAS_CONFIRMACION,
                }
                eventos_nuevos.append(evento)
                confirmado_estado = estado_crudo_hoy

        estado[ticker] = {
            "estado_crudo": estado_crudo_hoy,
            "dias_en_estado": dias_en_estado,
            "confirmado": confirmado_estado,
            "fecha_actualizado": hoy_fecha,
        }

        puntos.append({
            "Ticker": ticker,
            "Sector": fila.get("Sector"),
            "SMA50": round(float(sma50), 2),
            "SMA200": round(float(sma200), 2),
            "Estado_Crudo": estado_crudo_hoy,
            "Dias_En_Estado": dias_en_estado,
            "Confirmado": bool(dias_en_estado >= DIAS_CONFIRMACION),
            "Dias_Para_Confirmar": DIAS_CONFIRMACION,
            "Estado_Confirmado": confirmado_estado,
        })

    if eventos_nuevos:
        os.makedirs(os.path.dirname(RUTA_LOG), exist_ok=True)
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            for ev in eventos_nuevos:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        log.info(f"Golden/Death Cross: {len(eventos_nuevos)} cruce(s) confirmado(s): "
                 + ", ".join(f"{e['ticker']} -> {e['tipo']}" for e in eventos_nuevos))

    _guardar_estado(estado)

    return {
        "puntos": sorted(puntos, key=lambda p: p["Ticker"]),
        "eventos": eventos_nuevos,
    }
