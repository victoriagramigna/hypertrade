"""
Score Compuesto v2 — HyperTrade
==================================

Combina las señales existentes del radar (RS Score, gap alcista, VCP,
líder en soporte) con las nuevas (Stage 2, AVWAP, cruce AVWAP_52W_High,
contracción ATR) y el contexto global (Distribution Days).

Reemplaza al score 0-7 actual por un score 0-10 (con piso teórico
negativo, ver más abajo), con cada señal pesada según su valor
predictivo relativo, no por cuántas hay.

Este módulo NO recalcula las señales en sí — reutiliza las funciones
que ya existen en tu pipeline (radar_score.py actual) más las nuevas
de avwap.py y senales_nuevas.py. Se limita a sumar y armar el
diccionario de "qué disparó", que después usa narrativa.py para
armar el texto.
"""

import pandas as pd

# Pesos de cada señal — ver la conversación donde se definieron para
# el razonamiento detrás de cada número
PESOS = {
    "rs_alto": 3,           # RS Score > 80
    "stage2": 2,             # Precio > SMA50 > SMA200, alineadas y con pendiente
    "apoyo_soporte": 1,      # SMA50, AVWAP_YTD o AVWAP_Ultimo_Gap (±2%)
    "vcp": 1,                 # Contracción de rango (VCP existente)
    "gap_alcista": 1,        # Gap >=3% con macrotendencia (existente)
    "cruce_avwap_52w": 1,    # Cruce alcista del AVWAP anclado al máx. 52w
    "atr_contraction": 1,    # ATR10/ATR50 < 0.75
    # Distribution Days no está acá: se aplica aparte, es contexto
    # global (ver evaluar_penalizacion_distribution en senales_nuevas.py)
}


def calcular_score_compuesto(
    row: pd.Series,
    señales: dict,
    penalizacion_mercado: int = 0,
) -> dict:
    """
    row: la fila de hoy del DataFrame del ticker (para casos donde
    alguna señal necesite el valor crudo, no solo el booleano)
    señales: diccionario booleano con el resultado de CADA señal ya
    evaluada, por ejemplo:
        {
            "rs_alto": row["RS_Score"] > 80,
            "stage2": evaluar_stage2(row),
            "apoyo_soporte": evaluar_lider_soporte(row),   # de avwap.py
            "vcp": tu_funcion_vcp_existente(row),
            "gap_alcista": tu_funcion_gap_existente(row),
            "cruce_avwap_52w": detectar_cruce_avwap_52w(df),  # de avwap.py
            "atr_contraction": evaluar_atr_contraction(row),   # de senales_nuevas.py
        }
    penalizacion_mercado: el resultado de
        evaluar_penalizacion_distribution() de senales_nuevas.py,
        calculado UNA VEZ por corrida (no por ticker) y pasado igual
        a todos los tickers de esa corrida.

    Devuelve un diccionario con:
        - score_tecnico: suma de señales del ticker, sin penalización
        - score_compuesto: score_tecnico + penalizacion_mercado
        - señales_activas: lista de las señales que dispararon (para narrativa.py)
        - max_score_tecnico: el techo teórico (7 en esta configuración)
    """
    señales_activas = [nombre for nombre, activa in señales.items() if activa]

    score_tecnico = sum(PESOS.get(nombre, 0) for nombre in señales_activas)
    score_compuesto = score_tecnico + penalizacion_mercado

    return {
        "score_tecnico": score_tecnico,
        "score_compuesto": score_compuesto,
        "señales_activas": señales_activas,
        "max_score_tecnico": sum(PESOS.values()),  # = 10 con los pesos actuales
    }


# ---------------------------------------------------------------------------
# EJEMPLO DE INTEGRACIÓN CON EL RESTO DEL PIPELINE
# ---------------------------------------------------------------------------
#
#   from avwap import agregar_avwaps, evaluar_lider_soporte, detectar_cruce_avwap_52w
#   from senales_nuevas import (
#       agregar_columnas_pendiente, evaluar_stage2,
#       agregar_atr_contraction, evaluar_atr_contraction,
#       calcular_distribution_days, evaluar_penalizacion_distribution,
#   )
#   from radar_score_v2 import calcular_score_compuesto
#
#   # Una vez por corrida:
#   df_spy = descargar_datos_yfinance("SPY")
#   dist_days = calcular_distribution_days(df_spy)
#   penalizacion_mercado = evaluar_penalizacion_distribution(dist_days)
#
#   for ticker in universo:
#       df = descargar_datos_yfinance(ticker)
#       df = agregar_avwaps(df)
#       df = agregar_columnas_pendiente(df)
#       df = agregar_atr_contraction(df)
#
#       fila_hoy = df.iloc[-1]
#
#       señales = {
#           "rs_alto": fila_hoy.get("RS_Score", 0) > 80,
#           "stage2": evaluar_stage2(fila_hoy),
#           "apoyo_soporte": evaluar_lider_soporte(fila_hoy),
#           "vcp": tu_funcion_vcp_existente(fila_hoy),          # ya la tenés
#           "gap_alcista": tu_funcion_gap_existente(fila_hoy),  # ya la tenés
#           "cruce_avwap_52w": detectar_cruce_avwap_52w(df),
#           "atr_contraction": evaluar_atr_contraction(fila_hoy),
#       }
#
#       resultado_score = calcular_score_compuesto(fila_hoy, señales, penalizacion_mercado)
#
#       # resultado_score["score_compuesto"] es el número final para el ranking
#       # resultado_score["señales_activas"] alimenta a narrativa.py
#
# ---------------------------------------------------------------------------
