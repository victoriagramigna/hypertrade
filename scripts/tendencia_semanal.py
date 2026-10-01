"""
Tendencia Semanal (RSI + MACD) -- capa de CONTEXTO informativo sobre las
alertas que ya existen. NO es una señal nueva: no crea alertas propias, no
toca el Radar Score, ni el Estado, ni la Recomendación de ninguna alerta.

Por qué así (ver charla con Victoria, sept. 2026): RSI y MACD son
indicadores derivados del precio -- no anticipan nada, solo describen lo
que el precio ya hizo. Por eso ya se sacaron del score de cripto y se
dejan como aviso, no como gatillo (ver cripto_radar.py). Esta es la misma
filosofía aplicada acá: un dato más para mirar, nunca algo que decida por
vos.

Comprime las velas diarias que ya se descargan a semanales (mismo resample
que ya usa `rsi_semanal_cruzando` en alertas.py) y calcula:
  - RSI(14) semanal: >50 = momentum alcista, <=50 = bajista
  - MACD(12,26,9) semanal: línea MACD por encima de su señal = alcista

Se combinan en una lectura de 3 valores:
  - "favor":  los dos alcistas
  - "contra": los dos bajistas
  - "mixta":  uno alcista y el otro no

None (sin lectura) si todavía no hay suficiente historial semanal --
mejor no mostrar nada que mostrar un dato poco confiable.

Se calcula para TODO el universo (no solo tickers con alerta activa),
mismo criterio que los chips de Confluencia Alcista en radar_score.py --
así se puede auditar después sin importar si ese ticker tuvo o no una
alerta técnica ese día en particular.
"""
import pandas as pd

MIN_SEMANAS = 30  # mismo umbral que ya usa rsi_semanal_cruzando en alertas.py


def _rsi(serie: pd.Series, periodo: int = 14) -> pd.Series:
    delta = serie.diff()
    ganancia = delta.clip(lower=0).rolling(periodo).mean()
    perdida = (-delta.clip(upper=0)).rolling(periodo).mean()
    rs = ganancia / perdida
    return 100 - (100 / (1 + rs))


def _macd(serie: pd.Series, rapida: int = 12, lenta: int = 26, señal: int = 9):
    ema_rapida = serie.ewm(span=rapida, adjust=False).mean()
    ema_lenta = serie.ewm(span=lenta, adjust=False).mean()
    linea_macd = ema_rapida - ema_lenta
    linea_señal = linea_macd.ewm(span=señal, adjust=False).mean()
    return linea_macd, linea_señal


def calcular_tendencia_semanal(close_diario: pd.Series) -> dict:
    """
    close_diario: Serie de cierres DIARIOS de un solo ticker (mismo insumo
    que ya recibe rsi_semanal_cruzando en alertas.py).

    Devuelve:
      {"lectura": "favor"|"contra"|"mixta"|None,
       "rsi_semanal": float|None,
       "macd_semanal": float|None,
       "macd_señal_semanal": float|None}
    """
    vacio = {"lectura": None, "rsi_semanal": None, "macd_semanal": None, "macd_señal_semanal": None}
    if close_diario is None or close_diario.empty:
        return vacio

    semanal = close_diario.resample("W").last().dropna()
    if len(semanal) < MIN_SEMANAS:
        return vacio

    rsi_sem = _rsi(semanal, 14)
    linea_macd, linea_señal = _macd(semanal)

    if rsi_sem.empty or pd.isna(rsi_sem.iloc[-1]):
        return vacio
    if linea_macd.empty or pd.isna(linea_macd.iloc[-1]) or pd.isna(linea_señal.iloc[-1]):
        return vacio

    rsi_valor = round(float(rsi_sem.iloc[-1]), 1)
    macd_valor = round(float(linea_macd.iloc[-1]), 3)
    macd_señal_valor = round(float(linea_señal.iloc[-1]), 3)

    rsi_alcista = rsi_valor > 50
    macd_alcista = macd_valor > macd_señal_valor

    if rsi_alcista and macd_alcista:
        lectura = "favor"
    elif not rsi_alcista and not macd_alcista:
        lectura = "contra"
    else:
        lectura = "mixta"

    return {
        "lectura": lectura,
        "rsi_semanal": rsi_valor,
        "macd_semanal": macd_valor,
        "macd_señal_semanal": macd_señal_valor,
    }


SEMANAS_PROMEDIO_VOL = 12  # ~3 meses de semanas completas para el promedio


def calcular_vol_rel_semanal(volumen_diario: pd.Series):
    """
    Mismo concepto que Vol_rel (diario, en rs_score.py) pero en semanas:
    volumen de la semana en curso contra el promedio de las
    SEMANAS_PROMEDIO_VOL semanas COMPLETAS anteriores (se excluye la semana
    en curso del promedio para no comparar una semana contra sí misma).

    Ojo: la "semana en curso" puede estar a mitad de camino (ej. si hoy es
    martes), así que su volumen todavía no es comparable 1 a 1 contra una
    semana ya cerrada -- es la misma limitación que tiene cualquier lectura
    de "volumen semanal" antes de que termine la semana. Por eso es un dato
    más a mirar, no algo que dispare ni cambie ninguna alerta.

    None si no hay suficiente historial semanal (recién arranca el ticker,
    o viene con huecos).
    """
    if volumen_diario is None or volumen_diario.empty:
        return None

    semanal = volumen_diario.resample("W").sum()
    semanal = semanal[semanal > 0]  # semanas sin ruedas (feriados largos, etc.) no cuentan
    if len(semanal) < SEMANAS_PROMEDIO_VOL + 2:
        return None

    vol_semana_actual = semanal.iloc[-1]
    promedio_previas = semanal.iloc[-(SEMANAS_PROMEDIO_VOL + 1):-1].mean()
    if not promedio_previas or pd.isna(promedio_previas) or promedio_previas <= 0:
        return None

    return round(float(vol_semana_actual / promedio_previas), 2)
