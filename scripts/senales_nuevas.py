"""
Señales nuevas para el Radar Score v2 -- HyperTrade.
"""
import pandas as pd


def calcular_atr(df: pd.DataFrame, periodo: int) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close_prev = (df["High"] - df["Close"].shift(1)).abs()
    low_close_prev = (df["Low"] - df["Close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    return true_range.rolling(window=periodo).mean()


def agregar_atr_ratio(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ATR10"] = calcular_atr(df, 10)
    df["ATR50"] = calcular_atr(df, 50)
    df["ATR_Ratio"] = df["ATR10"] / df["ATR50"]
    return df


def evaluar_atr_contraction(row: pd.Series, umbral: float = 0.75) -> bool:
    ratio = row.get("ATR_Ratio")
    return bool(pd.notna(ratio) and ratio < umbral)


def evaluar_pendiente_positiva(close: pd.Series, ventana: int = 5) -> bool:
    """
    True si la SMA50 y la SMA200 (calculadas acá mismo sobre `close`)
    están hoy por encima de su propio valor de hace `ventana` ruedas --
    o sea, ambas medias con pendiente ascendente, no solo el precio por
    encima de ellas (eso ya lo mide el componente de Tendencia existente).
    """
    if len(close) < 200 + ventana:
        return False
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()
    return bool(sma50.iloc[-1] > sma50.iloc[-1 - ventana] and sma200.iloc[-1] > sma200.iloc[-1 - ventana])


def calcular_distribution_days(close: pd.Series, volume: pd.Series, ventana: int = 25) -> int:
    """
    Cuenta días de distribución del benchmark (SPY) en los últimos
    `ventana` días hábiles: cierre a la baja >=0.2% CON volumen mayor
    al día anterior. Se calcula UNA sola vez por corrida, sobre
    precios[BENCHMARK] y volumenes[BENCHMARK] -- no por ticker.
    """
    close_sub = close.iloc[-ventana:] if len(close) >= ventana else close
    volume_sub = volume.iloc[-ventana:] if len(volume) >= ventana else volume
    var_pct = close_sub.pct_change()
    vol_mayor = volume_sub > volume_sub.shift(1)
    es_distribution_day = (var_pct <= -0.002) & vol_mayor
    return int(es_distribution_day.sum())


def multiplicador_distribution(dist_days: int) -> float:
    """Mismo espíritu que el multiplicador de régimen VIX existente."""
    if dist_days <= 3:
        return 1.0
    elif dist_days <= 5:
        return 0.9
    else:
        return 0.75
