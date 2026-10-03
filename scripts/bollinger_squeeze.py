"""
Squeeze de Bollinger -- a pedido de Victoria, charla sobre "All-in-One
Pro". El squeeze (compresión de las bandas, ver BB_Bandwidth_% y
Squeeze_Comprimido en rs_score.py) NO dice para qué lado va a romper --
eso ya se discutió con Victoria: a diferencia del Golden/Death Cross
(donde el problema es el RUIDO en lateralización), aquí el squeeze está
HECHO para detectar lateralización/compresión, así que no hace falta
"confirmarlo" con demora. El problema real es la ambigüedad de dirección:
lo único auditable de verdad es la LIBERACIÓN (squeeze release) -- el
momento en que el precio rompe una banda viniendo de un squeeze reciente.

Por eso, a diferencia de golden_cross.py, esta señal no espera N ruedas
sosteniendo el nuevo estado: una ruptura de banda ya es, por definición,
un movimiento de un solo día que o se confirma con volumen o no vale
nada. El filtro de calidad es VOLUMEN_RELATIVO_MINIMO (mismo umbral que
ya usa el resto de la app para "ruptura con volumen", ver config.py), no
una demora de varios días.

Estado persistente (igual que golden_cross.py): para cada ticker, si
estaba en squeeze en la corrida anterior y cuántas ruedas lleva así (dato
de contexto, no se usa para filtrar nada). La liberación se detecta
mirando si ESTABA en squeeze (estado guardado) y HOY el precio cierra
fuera de la banda con volumen -- no se exige que el squeeze ya se haya
"apagado" formalmente hoy, porque el mismo movimiento que rompe la banda
puede no alcanzar a mover el ancho de la banda ese mismo día.
"""
import json
import logging
import os

from config import VOLUMEN_RELATIVO_MINIMO

log = logging.getLogger("radar.bollinger_squeeze")

RUTA_ESTADO = "data/squeeze_estado.json"
RUTA_LOG = "data/log_squeeze.jsonl"


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


def actualizar_squeeze(df_rs, ahora) -> dict:
    """
    df_rs: necesita Ticker, Sector, Precio, BB_Upper, BB_Lower,
    BB_Bandwidth_%, Squeeze_Comprimido, Vol_rel (todas ya calculadas en
    rs_score.py). Un ticker sin esos datos todavía (poca historia) queda
    afuera -- no se inventa nada.

    Devuelve {"puntos": [...], "eventos": [...]}.
      - puntos: uno por ticker con su estado de squeeze actual (para
        mostrar en el dashboard "comprimido hace N ruedas" aunque todavía
        no haya roto para ningún lado).
      - eventos: liberaciones (squeeze release) CONFIRMADAS por banda +
        volumen detectadas en ESTA corrida.
    """
    vacio = {"puntos": [], "eventos": []}
    columnas_necesarias = ("BB_Upper", "BB_Lower", "BB_Bandwidth_%", "Squeeze_Comprimido")
    if df_rs is None or df_rs.empty or any(c not in df_rs.columns for c in columnas_necesarias):
        return vacio

    estado = _cargar_estado()
    puntos = []
    eventos_nuevos = []
    hoy_iso = ahora.isoformat()
    hoy_fecha = ahora.date().isoformat()

    for _, fila in df_rs.iterrows():
        ticker = fila.get("Ticker")
        comprimido_hoy = fila.get("Squeeze_Comprimido")
        if ticker is None or comprimido_hoy is None:
            continue  # sin suficiente historia para juzgar squeeze todavía

        precio = fila.get("Precio")
        bb_upper, bb_lower = fila.get("BB_Upper"), fila.get("BB_Lower")
        vol_rel = fila.get("Vol_rel")
        previo = estado.get(ticker, {})
        estaba_en_squeeze = bool(previo.get("en_squeeze"))

        dias_en_squeeze = previo.get("dias_en_squeeze", 0)
        if comprimido_hoy:
            dias_en_squeeze = dias_en_squeeze + 1 if estaba_en_squeeze else 1
        else:
            dias_en_squeeze = 0

        # Liberación: VENÍA de squeeze (estado de la corrida anterior, no
        # necesariamente el de hoy -- el mismo movimiento que rompe la
        # banda puede no alcanzar a "desinflar" el ancho ese mismo día) y
        # HOY el precio cierra afuera de alguna banda con volumen que
        # confirma (mismo umbral que ya usa el resto de la app).
        liberacion = None
        if estaba_en_squeeze and precio is not None and bb_upper is not None and bb_lower is not None:
            volumen_confirma = vol_rel is not None and vol_rel >= VOLUMEN_RELATIVO_MINIMO
            if precio > bb_upper and volumen_confirma:
                liberacion = "alcista"
            elif precio < bb_lower and volumen_confirma:
                liberacion = "bajista"

        if liberacion is not None:
            evento = {
                "timestamp": hoy_iso,
                "ticker": ticker,
                "sector": fila.get("Sector"),
                "direccion": liberacion,
                "precio": precio,
                "bb_upper": bb_upper,
                "bb_lower": bb_lower,
                "vol_rel": vol_rel,
                "dias_en_squeeze_previos": previo.get("dias_en_squeeze", 0),
            }
            eventos_nuevos.append(evento)
            # Una vez liberado, se resetea -- si vuelve a comprimirse más
            # adelante es un squeeze nuevo, no una continuación de este.
            dias_en_squeeze = 0

        estado[ticker] = {
            "en_squeeze": bool(comprimido_hoy) and liberacion is None,
            "dias_en_squeeze": dias_en_squeeze,
            "fecha_actualizado": hoy_fecha,
        }

        puntos.append({
            "Ticker": ticker,
            "Sector": fila.get("Sector"),
            "BB_Bandwidth_%": fila.get("BB_Bandwidth_%"),
            "Squeeze_Comprimido": bool(comprimido_hoy),
            "Dias_En_Squeeze": dias_en_squeeze,
            "Liberacion_Hoy": liberacion,
        })

    if eventos_nuevos:
        os.makedirs(os.path.dirname(RUTA_LOG), exist_ok=True)
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            for ev in eventos_nuevos:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        log.info(f"Squeeze release: {len(eventos_nuevos)} liberación(es) confirmada(s): "
                 + ", ".join(f"{e['ticker']} -> {e['direccion']}" for e in eventos_nuevos))

    _guardar_estado(estado)

    return {
        "puntos": sorted(puntos, key=lambda p: p["Ticker"]),
        "eventos": eventos_nuevos,
    }
