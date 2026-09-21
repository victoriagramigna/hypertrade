"""
AVWAP (Anchored VWAP) -- metodología Brian Shannon.

Trabaja sobre un DataFrame OHLCV por ticker (Open/High/Low/Close/Volume,
DatetimeIndex ascendente) -- exactamente lo que devuelve precios_ohlc[ticker]
en datos.py (v3).
"""
import pandas as pd
import numpy as np


def calcular_avwap_anclado(df: pd.DataFrame, idx_ancla) -> pd.Series:
    if idx_ancla is None or idx_ancla >= len(df):
        return pd.Series(np.nan, index=df.index)
    ohlc4 = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4.0
    pv = ohlc4 * df["Volume"]
    avwap = pd.Series(np.nan, index=df.index)
    avwap.iloc[idx_ancla:] = pv.iloc[idx_ancla:].cumsum() / df["Volume"].iloc[idx_ancla:].cumsum()
    return avwap


def ancla_ytd(df: pd.DataFrame):
    anio_actual = df.index[-1].year
    mascara = df.index.year == anio_actual
    if not mascara.any():
        return None
    return df.index.get_loc(df.index[mascara][0])


def ancla_max_52w(df: pd.DataFrame, ventana: int = 252):
    if df.empty:
        return None
    sub = df["High"].iloc[-ventana:] if len(df) >= ventana else df["High"]
    return df.index.get_loc(sub.idxmax())


def ancla_ultimo_gap(df: pd.DataFrame, meses: int = 6, umbral: float = 0.05):
    dias = meses * 21
    sub = df.iloc[-dias:] if len(df) >= dias else df
    var_pct = sub["Close"].pct_change()
    gaps = var_pct[var_pct.abs() >= umbral]
    if gaps.empty:
        return None
    return df.index.get_loc(gaps.index[-1])


def agregar_avwaps(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["AVWAP_YTD"] = calcular_avwap_anclado(df, ancla_ytd(df))
    df["AVWAP_52W_High"] = calcular_avwap_anclado(df, ancla_max_52w(df))
    df["AVWAP_Ultimo_Gap"] = calcular_avwap_anclado(df, ancla_ultimo_gap(df))
    return df


def evaluar_apoyo_avwap(row: pd.Series, tolerancia: float = 0.02) -> bool:
    """
    True si el precio de cierre está dentro de `tolerancia` (default 2%)
    de su SMA50, su AVWAP_YTD o su AVWAP_Ultimo_Gap. Sin gate de RS --
    en el nuevo score, RS ya se puntúa aparte.
    """
    close = row.get("Close")
    if pd.isna(close):
        return False
    for nivel in (row.get("SMA50"), row.get("AVWAP_YTD"), row.get("AVWAP_Ultimo_Gap")):
        if pd.notna(nivel) and nivel != 0 and abs(close - nivel) / nivel <= tolerancia:
            return True
    return False


def detectar_cruce_avwap_52w(df: pd.DataFrame, tolerancia: float = 0.01) -> bool:
    if len(df) < 2:
        return False
    hoy, ayer = df.iloc[-1], df.iloc[-2]
    avwap_hoy, avwap_ayer = hoy.get("AVWAP_52W_High"), ayer.get("AVWAP_52W_High")
    if pd.isna(avwap_hoy) or pd.isna(avwap_ayer):
        return False
    cruzo_hoy = hoy["Close"] > avwap_hoy * (1 - tolerancia)
    estaba_abajo_ayer = ayer["Close"] <= avwap_ayer * (1 + tolerancia)
    return bool(cruzo_hoy and estaba_abajo_ayer and hoy["Close"] > ayer["Close"])
