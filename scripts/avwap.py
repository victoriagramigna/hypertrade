"""
Módulo AVWAP (Anchored VWAP) — Metodología Brian Shannon
==========================================================

Pensado para integrarse al pipeline existente del radar (yfinance + Pandas +
GitHub Actions -> data/ultimo.json), sin agregar llamadas extra a la API:
Open, High, Low, Close y Volume ya vienen en el DataFrame estándar de yfinance.

Este módulo asume que las funciones se llaman POR TICKER, sobre el DataFrame
diario ya descargado de ese ticker (que es como ya está armado el pipeline,
iterando el universo). Por eso "vectorizado" acá significa: nada de loops
fila por fila dentro de un mismo ticker — todo se resuelve con cumsum /
idxmax de Pandas, que son operaciones vectorizadas en C.

Requisitos del DataFrame de entrada:
    - Índice: DatetimeIndex, ordenado ascendente (esto ya lo da yfinance).
    - Columnas: 'Open', 'High', 'Low', 'Close', 'Volume'.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# 1. CÁLCULO BASE: AVWAP genérico a partir de un ancla
# ---------------------------------------------------------------------------

def calcular_avwap_anclado(df: pd.DataFrame, idx_ancla: int) -> pd.Series:
    """
    Calcula el AVWAP (Anchored VWAP) usando precio típico OHLC4, arrancando
    el conteo acumulativo exclusivamente desde idx_ancla (posición entera,
    no fecha).

    Fórmula: cumsum(OHLC4 * Volume) / cumsum(Volume), desde el ancla.

    Devuelve una Serie alineada al índice del DataFrame, con NaN en las
    filas anteriores al ancla (todavía no hay AVWAP definido ahí).
    """
    if idx_ancla is None or idx_ancla >= len(df):
        return pd.Series(np.nan, index=df.index)

    ohlc4 = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4.0
    pv = ohlc4 * df["Volume"]

    avwap = pd.Series(np.nan, index=df.index)

    pv_desde_ancla = pv.iloc[idx_ancla:]
    vol_desde_ancla = df["Volume"].iloc[idx_ancla:]

    # cumsum vectorizado, sin loop
    avwap.iloc[idx_ancla:] = pv_desde_ancla.cumsum() / vol_desde_ancla.cumsum()

    return avwap


# ---------------------------------------------------------------------------
# 2. LOCALIZADORES DE ANCLA (devuelven una POSICIÓN entera, no una fecha)
# ---------------------------------------------------------------------------

def ancla_ytd(df: pd.DataFrame) -> int | None:
    """
    Ancla de TIEMPO: primer día hábil del año en curso (según la última
    fecha disponible en el DataFrame, para que funcione aunque el ticker
    tenga huecos).
    """
    anio_actual = df.index[-1].year
    mascara = df.index.year == anio_actual
    if not mascara.any():
        return None
    return df.index.get_loc(df.index[mascara][0])


def ancla_max_52w(df: pd.DataFrame, ventana: int = 252) -> int | None:
    """
    Ancla de PRECIO: día exacto del máximo de las últimas 52 semanas
    (~252 ruedas). Reutiliza el mismo criterio de ventana que ya usás
    para Dist_Max52w_%, así ambos números quedan consistentes.
    """
    if df.empty:
        return None
    sub = df["High"].iloc[-ventana:] if len(df) >= ventana else df["High"]
    fecha_max = sub.idxmax()
    return df.index.get_loc(fecha_max)


def ancla_ultimo_gap(df: pd.DataFrame, meses: int = 6, umbral: float = 0.05) -> int | None:
    """
    Ancla de EVENTO: último salto o caída diaria >= umbral (default 5%)
    dentro de los últimos `meses` (default 6, ~126 ruedas). Misma lógica
    que ya alimenta el panel de "Movimientos del día", solo que acá
    buscamos la fecha del más reciente en vez de listarlos todos.
    """
    dias = meses * 21  # aprox. ruedas hábiles por mes
    sub = df.iloc[-dias:] if len(df) >= dias else df

    var_pct = sub["Close"].pct_change()
    gaps = var_pct[var_pct.abs() >= umbral]

    if gaps.empty:
        return None

    fecha_ultimo_gap = gaps.index[-1]
    return df.index.get_loc(fecha_ultimo_gap)


# ---------------------------------------------------------------------------
# 3. FUNCIÓN PRINCIPAL: agrega los 3 AVWAPs al DataFrame de un ticker
# ---------------------------------------------------------------------------

def agregar_avwaps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega las columnas AVWAP_YTD, AVWAP_52W_High y AVWAP_Ultimo_Gap al
    DataFrame diario de un ticker. No modifica nada más — no toca
    data/ultimo.json directamente, eso lo sigue armando tu main.py como
    hasta ahora, leyendo estas columnas nuevas del DataFrame.
    """
    df = df.copy()

    df["AVWAP_YTD"] = calcular_avwap_anclado(df, ancla_ytd(df))
    df["AVWAP_52W_High"] = calcular_avwap_anclado(df, ancla_max_52w(df))
    df["AVWAP_Ultimo_Gap"] = calcular_avwap_anclado(df, ancla_ultimo_gap(df))

    return df


# ---------------------------------------------------------------------------
# 4. SEÑAL EXISTENTE MODIFICADA: "Líder apoyando en soporte"
# ---------------------------------------------------------------------------

def evaluar_lider_soporte(row: pd.Series, tolerancia: float = 0.02) -> bool:
    """
    Versión ampliada de la señal actual. Antes exigía precio entre 0% y 2%
    por encima de la SMA50. Ahora también es válido apoyar sobre el
    AVWAP_YTD o el AVWAP_Ultimo_Gap, que en activos volátiles suelen ser
    soporte más confiable que una media móvil simple (perfora la SMA50
    para sacudir posiciones, pero rara vez pierde el costo promedio
    institucional).

    Requiere RS_Score > 80 (igual que antes) + apoyo en AL MENOS UNO de
    los tres niveles.
    """
    if row.get("RS_Score", 0) <= 80:
        return False

    condiciones = []

    # SMA50: mantiene la lógica original (0% a +2% por encima)
    sma50 = row.get("SMA50")
    if pd.notna(sma50) and sma50 != 0:
        dist_sma50 = (row["Close"] - sma50) / sma50
        condiciones.append(0 <= dist_sma50 <= tolerancia)

    # AVWAP_YTD: tolerancia simétrica (±) porque es zona de liquidez,
    # no un piso exacto
    avwap_ytd = row.get("AVWAP_YTD")
    if pd.notna(avwap_ytd) and avwap_ytd != 0:
        dist_ytd = abs(row["Close"] - avwap_ytd) / avwap_ytd
        condiciones.append(dist_ytd <= tolerancia)

    # AVWAP_Ultimo_Gap: mismo criterio
    avwap_gap = row.get("AVWAP_Ultimo_Gap")
    if pd.notna(avwap_gap) and avwap_gap != 0:
        dist_gap = abs(row["Close"] - avwap_gap) / avwap_gap
        condiciones.append(dist_gap <= tolerancia)

    return any(condiciones)


# ---------------------------------------------------------------------------
# 5. SEÑAL NUEVA: cruce alcista del AVWAP_52W_High ("vendedores atrapados")
# ---------------------------------------------------------------------------

def detectar_cruce_avwap_52w(df: pd.DataFrame, tolerancia: float = 0.01) -> bool:
    """
    Detecta si el CIERRE de la rueda más reciente cruzó al alza el
    AVWAP_52W_High, viniendo desde abajo en la rueda anterior. Esto
    confirma que la presión vendedora de quienes compraron cerca del
    máximo de 52 semanas ya fue absorbida por compradores nuevos.

    Requiere al menos 2 filas de datos y AVWAP_52W_High definido en
    ambas (o sea, el ancla del máximo de 52w ya ocurrió y hay historia
    suficiente desde entonces).
    """
    if len(df) < 2:
        return False

    hoy = df.iloc[-1]
    ayer = df.iloc[-2]

    avwap_hoy = hoy.get("AVWAP_52W_High")
    avwap_ayer = ayer.get("AVWAP_52W_High")

    if pd.isna(avwap_hoy) or pd.isna(avwap_ayer):
        return False

    cruzo_hoy = hoy["Close"] > avwap_hoy * (1 - tolerancia)
    estaba_abajo_ayer = ayer["Close"] <= avwap_ayer * (1 + tolerancia)
    subio = hoy["Close"] > ayer["Close"]

    return bool(cruzo_hoy and estaba_abajo_ayer and subio)


# ---------------------------------------------------------------------------
# 6. INTEGRACIÓN SUGERIDA AL RADAR SCORE (0 a 7)
# ---------------------------------------------------------------------------
#
# Tu score actual suma puntos por señales técnicas distintas (RS, volumen,
# contracción, etc.) hasta un máximo de 7. Para sumar esta nueva señal sin
# romper la escala, dos caminos posibles:
#
#   OPCIÓN A (recomendada): elevar el máximo a 8 y sumar +1 punto cuando
#   detectar_cruce_avwap_52w(df) sea True. Es la más simple y no le resta
#   peso a ninguna señal existente.
#
#   OPCIÓN B: si preferís mantener el techo en 7, restarle medio punto a
#   dos señales redundantes con esta (por ejemplo, si ya sumás puntos por
#   "RS > 80" y por "cruce de SMA200", el cruce de AVWAP_52W_High se
#   solapa parcialmente con ambas) y darle 1 punto entero a la nueva señal.
#   Es más prolijo pero te obliga a retocar el peso de señales ya
#   validadas en vivo.
#
# Ejemplo de cómo quedaría sumado (Opción A) dentro de tu función de score:
#
#   def calcular_radar_score(row, df_ticker):
#       score = 0
#       # ... tus condiciones existentes ...
#       if detectar_cruce_avwap_52w(df_ticker):
#           score += 1
#       return score  # ahora de 0 a 8
#
# Sugerencia de texto para la tarjeta de alerta cuando dispara:
#   "Vendedores atrapados absorbidos: {ticker} cruzó al alza su AVWAP
#    anclado al máximo de 52 semanas ($X.XX). La oferta de quienes
#    compraron cerca del techo ya fue absorbida."
#
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 7. EJEMPLO DE USO EN TU LOOP EXISTENTE
# ---------------------------------------------------------------------------
#
#   for ticker in universo:
#       df = descargar_datos_yfinance(ticker)   # tu función actual
#       df = agregar_avwaps(df)                 # nuevo
#
#       fila_hoy = df.iloc[-1]
#
#       lider_soporte = evaluar_lider_soporte(fila_hoy)
#       cruce_52w = detectar_cruce_avwap_52w(df)
#
#       score = calcular_radar_score(fila_hoy, df)  # tu función, ampliada
#
#       # ... el resto de tu lógica de armado de data/ultimo.json sigue
#       # igual, solo que ahora podés incluir AVWAP_YTD, AVWAP_52W_High
#       # y AVWAP_Ultimo_Gap como campos nuevos en el JSON si querés
#       # graficarlos en el dashboard más adelante.
#
# ---------------------------------------------------------------------------
