"""
Señales nuevas para HyperTrade
================================

Tres señales que se suman al AVWAP (ver avwap.py) para el nuevo Score
Compuesto. Todas trabajan sobre el mismo DataFrame diario de yfinance
que ya usa el resto del pipeline — no piden ninguna llamada extra.

1. Stage 2 (Stan Weinstein / Mark Minervini): confirma que el ticker
   está en una tendencia alcista real, no en un rebote de corto plazo.
2. Contracción ATR: mide compresión de volatilidad, complementa al VCP
   que ya tenés.
3. Distribution Days: NO es una señal por ticker, es una señal de
   CONTEXTO GLOBAL del mercado (se calcula una sola vez por corrida,
   usando SPY o el índice que uses de referencia) — resta puntos al
   score de todos los tickers cuando el mercado está bajo presión de
   venta institucional.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# 1. STAGE 2 — tendencia alcista confirmada
# ---------------------------------------------------------------------------

def evaluar_stage2(row: pd.Series) -> bool:
    """
    True si el precio está en Stage 2: Precio > SMA50 > SMA200, con
    ambas medias en pendiente positiva. Usa las columnas SMA50 y SMA200
    que ya calculás en el pipeline actual.

    Requiere que el DataFrame tenga también SMA50_prev y SMA200_prev
    (el valor de la media 5 ruedas atrás) para chequear la pendiente,
    calculado antes de llamar a esta función — ver nota más abajo.
    """
    sma50 = row.get("SMA50")
    sma200 = row.get("SMA200")
    sma50_prev = row.get("SMA50_prev")
    sma200_prev = row.get("SMA200_prev")
    close = row.get("Close")

    if pd.isna(sma50) or pd.isna(sma200) or pd.isna(close):
        return False

    alineadas = close > sma50 > sma200

    # Pendiente positiva: si no tenemos los valores previos, solo
    # chequeamos la alineación (degrada con gracia, no rompe nada)
    if pd.notna(sma50_prev) and pd.notna(sma200_prev):
        pendientes_ok = (sma50 > sma50_prev) and (sma200 > sma200_prev)
    else:
        pendientes_ok = True

    return bool(alineadas and pendientes_ok)


def agregar_columnas_pendiente(df: pd.DataFrame, ventana: int = 5) -> pd.DataFrame:
    """
    Agrega SMA50_prev y SMA200_prev al DataFrame, el valor de esas
    medias `ventana` ruedas atrás (default 5, o sea "una semana atrás"
    aprox). Llamar a esto ANTES de evaluar_stage2 fila por fila.
    """
    df = df.copy()
    if "SMA50" in df.columns:
        df["SMA50_prev"] = df["SMA50"].shift(ventana)
    if "SMA200" in df.columns:
        df["SMA200_prev"] = df["SMA200"].shift(ventana)
    return df


# ---------------------------------------------------------------------------
# 2. CONTRACCIÓN ATR — compresión de volatilidad
# ---------------------------------------------------------------------------

def calcular_atr(df: pd.DataFrame, periodo: int) -> pd.Series:
    """
    ATR (Average True Range) vectorizado, sin loops. True Range es el
    mayor entre: High-Low, |High-Close_previo|, |Low-Close_previo|.
    """
    high_low = df["High"] - df["Low"]
    high_close_prev = (df["High"] - df["Close"].shift(1)).abs()
    low_close_prev = (df["Low"] - df["Close"].shift(1)).abs()

    true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    return true_range.rolling(window=periodo).mean()


def agregar_atr_contraction(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega ATR10, ATR50 y ATR_Ratio (ATR10/ATR50) al DataFrame.
    Ratio bajo = volatilidad comprimida respecto a su propio promedio
    reciente = "resorte apretado", posible preparación de ruptura.
    """
    df = df.copy()
    df["ATR10"] = calcular_atr(df, 10)
    df["ATR50"] = calcular_atr(df, 50)
    df["ATR_Ratio"] = df["ATR10"] / df["ATR50"]
    return df


def evaluar_atr_contraction(row: pd.Series, umbral: float = 0.75) -> bool:
    """
    True si ATR_Ratio < umbral (default 0.75) — volatilidad de las
    últimas 10 ruedas notablemente por debajo del promedio de 50.
    """
    ratio = row.get("ATR_Ratio")
    if pd.isna(ratio):
        return False
    return bool(ratio < umbral)


# ---------------------------------------------------------------------------
# 3. DISTRIBUTION DAYS — contexto de mercado (NO es por ticker)
# ---------------------------------------------------------------------------

def calcular_distribution_days(df_indice: pd.DataFrame, ventana: int = 25) -> int:
    """
    Cuenta los "días de distribución" del índice de referencia (SPY,
    o el que uses como proxy del mercado general) en los últimos
    `ventana` días hábiles (default 25, ~5 semanas).

    Un día de distribución es: el índice CERRÓ a la baja (>=0.2%)
    CON volumen mayor al día anterior. Es la métrica clásica de IBD
    para detectar venta institucional silenciosa, incluso cuando el
    precio todavía no lo refleja con fuerza.

    df_indice: DataFrame diario del índice de referencia (mismo
    formato yfinance: Close, Volume), ordenado ascendente.

    Devuelve un entero: cantidad de distribution days en la ventana.
    Llamar a esto UNA SOLA VEZ por corrida (no por ticker) y pasar
    el resultado como parte del contexto global.
    """
    sub = df_indice.iloc[-ventana:] if len(df_indice) >= ventana else df_indice

    var_pct = sub["Close"].pct_change()
    vol_mayor = sub["Volume"] > sub["Volume"].shift(1)

    es_distribution_day = (var_pct <= -0.002) & vol_mayor

    return int(es_distribution_day.sum())


def evaluar_penalizacion_distribution(distribution_days: int) -> int:
    """
    Traduce la cantidad de distribution days del contexto global a
    puntos de PENALIZACIÓN para el score de TODOS los tickers de esa
    corrida (se resta al final, no es una señal por ticker).

    0-3 días  -> 0  (mercado sano, sin penalización)
    4-5 días  -> -1 (empieza a haber presión de venta)
    6+ días   -> -2 (mercado bajo distribución fuerte -- cautela)
    """
    if distribution_days <= 3:
        return 0
    elif distribution_days <= 5:
        return -1
    else:
        return -2


# ---------------------------------------------------------------------------
# EJEMPLO DE USO EN EL LOOP EXISTENTE
# ---------------------------------------------------------------------------
#
#   # Una vez por corrida, no por ticker:
#   df_spy = descargar_datos_yfinance("SPY")
#   dist_days = calcular_distribution_days(df_spy)
#   penalizacion_mercado = evaluar_penalizacion_distribution(dist_days)
#
#   for ticker in universo:
#       df = descargar_datos_yfinance(ticker)
#       df = agregar_avwaps(df)                    # de avwap.py
#       df = agregar_columnas_pendiente(df)         # nuevo
#       df = agregar_atr_contraction(df)            # nuevo
#
#       fila_hoy = df.iloc[-1]
#
#       stage2 = evaluar_stage2(fila_hoy)
#       atr_ok = evaluar_atr_contraction(fila_hoy)
#
#       # ... el resto de las señales existentes + AVWAP ...
#
#       score = calcular_radar_score(fila_hoy, df) + penalizacion_mercado
#
# ---------------------------------------------------------------------------
