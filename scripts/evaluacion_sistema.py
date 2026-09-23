"""
Evaluación del sistema: responde, con datos reales acumulados en
data/seguimiento_resultados.jsonl, si el Radar Score y sus señales
individuales realmente anticipan un movimiento rentable -- y si le
ganan al mercado (alpha vs. SPY), no solo si suben en términos
absolutos.

Pensado para correr aparte del pipeline principal (no en cada
corrida de 30 min, no hace falta) -- por ejemplo, una vez por semana,
o a demanda. Escribe un único JSON con el resultado más reciente en
data/evaluacion_sistema.json (se pisa cada vez, no es un log).

Ninguna conclusión se muestra sin dejar en claro el tamaño de
muestra que la respalda -- con pocas alertas, "no sabemos todavía"
es la respuesta honesta, no un número que parezca definitivo.
"""
import json
import logging
import os
from datetime import datetime, timezone
from statistics import mean, stdev

log = logging.getLogger("radar.evaluacion")

RUTA_RESULTADOS = "data/seguimiento_resultados.jsonl"
RUTA_SALIDA = "data/evaluacion_sistema.json"
HORIZONTES_RUEDAS = (5, 10, 20)

# Con menos muestras que esto en un grupo, el promedio es apenas
# anecdótico -- el reporte lo marca como "sin datos suficientes" en
# vez de mostrar un número que invite a sacar una conclusión.
UMBRAL_MUESTRA_MINIMA = 10

# Rangos del Radar Score para la pregunta 1 (¿predice algo el score?)
BUCKETS_RADAR_SCORE = [
    ("70-100 (alto)", 70, 100),
    ("45-69 (medio)", 45, 69.999),
    ("0-44 (bajo)", 0, 44.999),
]

# Señales individuales a evaluar por separado (pregunta 2)
SEÑALES_INDIVIDUALES = ["apoyo_avwap", "cruce_avwap_52w", "atr_contraction", "pendiente_ok"]


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


def _stats(valores):
    """Promedio, desvío estándar y tamaño de muestra -- o None si no
    alcanza el umbral mínimo para confiar en el número."""
    n = len(valores)
    if n < UMBRAL_MUESTRA_MINIMA:
        return {"n_muestras": n, "suficiente_data": False}
    return {
        "n_muestras": n,
        "suficiente_data": True,
        "promedio_pct": round(mean(valores), 2),
        "desvio_pct": round(stdev(valores), 2) if n > 1 else 0.0,
    }


def _pregunta1_radar_score(filas):
    """¿El Radar Score predice el retorno? Agrupa por rango de score
    y compara el retorno promedio de cada bucket."""
    resultado = {}
    for nombre, minimo, maximo in BUCKETS_RADAR_SCORE:
        valores = [
            r["variacion_pct"] for r in filas
            if r.get("radar_score") is not None and minimo <= r["radar_score"] <= maximo
        ]
        resultado[nombre] = _stats(valores)
    return resultado


def _pregunta2_señales_individuales(filas):
    """¿Qué señal individual aporta de verdad? Compara el retorno
    promedio de las alertas CON la señal prendida vs. SIN ella."""
    resultado = {}
    for señal in SEÑALES_INDIVIDUALES:
        con_señal = [r["variacion_pct"] for r in filas if r.get(señal) is True]
        sin_señal = [r["variacion_pct"] for r in filas if r.get(señal) is False]
        resultado[señal] = {
            "con_señal": _stats(con_señal),
            "sin_señal": _stats(sin_señal),
        }
    return resultado


def _pregunta3_alpha_vs_spy(filas):
    """¿Le gana al mercado, o solo sube porque el mercado sube?
    Usa alpha_pct (ya calculado en seguimiento_precios.py: retorno
    del ticker menos retorno del SPY en la misma ventana exacta)."""
    valores = [r["alpha_pct"] for r in filas if r.get("alpha_pct") is not None]
    return _stats(valores)


def evaluar_sistema():
    filas = _leer_jsonl(RUTA_RESULTADOS)

    if not filas:
        salida = {
            "generado_utc": datetime.now(timezone.utc).isoformat(),
            "suficiente_data": False,
            "motivo": "Todavía no hay resultados acumulados -- seguimiento_precios.py recién empieza a llenar data/seguimiento_resultados.jsonl.",
        }
        _guardar(salida)
        return salida

    por_horizonte = {}
    for horizonte in HORIZONTES_RUEDAS:
        filas_h = [r for r in filas if r.get("horizonte_ruedas") == horizonte]
        por_horizonte[str(horizonte)] = {
            "n_muestras_total": len(filas_h),
            "retorno_promedio_pct": _stats([r["variacion_pct"] for r in filas_h]),
            "por_radar_score": _pregunta1_radar_score(filas_h),
            "por_señal_individual": _pregunta2_señales_individuales(filas_h),
            "alpha_vs_spy": _pregunta3_alpha_vs_spy(filas_h),
        }

    salida = {
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "suficiente_data": True,
        "umbral_muestra_minima": UMBRAL_MUESTRA_MINIMA,
        "n_muestras_total_todos_horizontes": len(filas),
        "horizontes": por_horizonte,
    }
    _guardar(salida)
    return salida


def _guardar(salida):
    os.makedirs("data", exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    log.info(f"Evaluación del sistema guardada en {RUTA_SALIDA}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    resultado = evaluar_sistema()
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
