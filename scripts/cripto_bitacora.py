"""
Bitácora de eventos de cripto: mismo concepto que bitacora.py (log de SOLO
AGREGADO, nunca pisa nada) pero en su propio archivo, separado del de
acciones -- así no se mezclan esquemas distintos ni se rompe nada de lo que
ya lee data/log_alertas.jsonl (evaluacion_sistema.py, auditoria.py).

Formato JSONL (un evento por línea): la "foto" de cada alerta al momento en
que se disparó, para poder medir más adelante (con datos de varias semanas)
si de verdad anticipó un movimiento rentable.
"""
import json
import os

ARCHIVO_LOG = "data/log_alertas_cripto.jsonl"


def registrar_eventos_cripto(eventos: list):
    """
    Agrega una línea por cada alerta de cripto que se mandó (o se iba a
    mandar) en esta corrida.

    Recibe una lista de tuplas (nombre, ticker, alerta_dict, resultado_dict),
    donde resultado_dict es la entrada completa de ese ticker en cripto.json
    (para sacar precio/score/indicadores en el momento del evento).
    """
    if not eventos:
        return 0

    lineas = []
    for timestamp, nombre, ticker, alerta, r in eventos:
        evento = {
            "timestamp": timestamp,
            "ticker": ticker,
            "nombre": nombre,
            "tipo": alerta.get("tipo"),
            "narrativa": alerta.get("narrativa"),
            "precio": r.get("precio"),
            "score": r.get("score"),
            "score_version": r.get("score_version", "v1"),
            "rsi": r.get("rsi"),
            "vol_rel": r.get("vol_rel"),
            "sma50": r.get("sma50"),
            "sma200": r.get("sma200"),
            "dist_max52w_pct": r.get("dist_max52w_pct"),
            "tendencia_alcista": r.get("tendencia_alcista"),
        }
        lineas.append(json.dumps(evento, ensure_ascii=False))

    os.makedirs(os.path.dirname(ARCHIVO_LOG), exist_ok=True)
    with open(ARCHIVO_LOG, "a", encoding="utf-8") as f:
        for linea in lineas:
            f.write(linea + "\n")

    return len(lineas)
