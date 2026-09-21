"""
Radar Score (v2.1): puntaje compuesto 0-100 para "¿esto es una buena
OPORTUNIDAD DE COMPRA ahora?".

CAMBIO v2.2: NI Distribution Days NI el regimen VIX multiplican ya el
score. Los dos siguen calculandose y mostrandose como badges de
contexto en el dashboard, pero no penalizan el puntaje de ningun
ticker -- son informacion de contexto GLOBAL del mercado, no una
señal del activo en si, y el VIX ya tiene su propio freno en otro
lado del pipeline (main.py baja cualquier COMPRA a MANTENER si el
regimen no es sano) -- aplicarlo tambien acá era penalizar dos veces
lo mismo. El Radar Score ahora mide PURA calidad tecnica del ticker,
sin ningun multiplicador de contexto.

Componentes (0-100):
  - RS Score:                        25 pts  (RS_Score/100 * 25)
  - Contraccion (VCP + ATR):         25 pts  (20 si VCP_valido, +5 si además
                                               ATR10/ATR50 < 0.75)
  - Volumen de confirmacion (RVOL):  15 pts  (escala con Vol_rel, tope en 1.5x)
  - Tendencia (5 sub-condiciones):   15 pts  (3 c/u -- incluye pendiente
                                               positiva de SMA50/200)
  - Apoyo en AVWAP/SMA50:            10 pts  (precio en zona de costo
                                               institucional, ±2%)
  - Posicion en 52 semanas:          10 pts

Fuera de los 100:
  - Bono por cruce de AVWAP_52W_High: +5 pts, aparte

El VIX y Distribution Days siguen viajando en el JSON de salida como
datos de contexto (badges), y el VIX además sigue bajando cualquier
COMPRA a MANTENER en la Recomendación final cuando el regimen no es
sano -- pero ninguno de los dos toca ya el numero del Radar Score.

IMPORTANTE: esta distribucion de pesos es un punto de partida
razonable, a ajustar con el backtest sobre la bitacora de eventos.
"""
import pandas as pd

from avwap import agregar_avwaps, evaluar_apoyo_avwap, detectar_cruce_avwap_52w
from senales_nuevas import agregar_atr_ratio, evaluar_atr_contraction, evaluar_pendiente_positiva

TOPE_VOL_REL = 1.5
TOPE_DIST_52W_PCT = -30
MULTIPLICADOR_VIX_VOLATIL = 0.7


def _componente_volumen(vol_rel):
    if vol_rel is None or pd.isna(vol_rel):
        return 0
    return round(min(15, max(0, vol_rel / TOPE_VOL_REL * 15)), 2)


def _componente_52_semanas(dist_max52w_pct):
    if dist_max52w_pct is None or pd.isna(dist_max52w_pct):
        return 0
    return round(min(10, max(0, (dist_max52w_pct - TOPE_DIST_52W_PCT) / (-TOPE_DIST_52W_PCT) * 10)), 2)


def _componente_tendencia(sobre_sma50, dist_sma200_pct, rs_sector, spy_sobre_sma50, pendiente_ok):
    sub_puntos = 15 / 5
    total = 0
    if sobre_sma50:
        total += sub_puntos
    if dist_sma200_pct is not None and not pd.isna(dist_sma200_pct) and dist_sma200_pct > 0:
        total += sub_puntos
    if rs_sector is not None and rs_sector > 50:
        total += sub_puntos
    if spy_sobre_sma50:
        total += sub_puntos
    if pendiente_ok:
        total += sub_puntos
    return round(total, 2)


def _procesar_indicadores_ticker(df_ohlc: pd.DataFrame):
    if df_ohlc is None or df_ohlc.empty or len(df_ohlc) < 60:
        return None

    df = agregar_avwaps(df_ohlc)
    df = agregar_atr_ratio(df)
    df["SMA50"] = df["Close"].rolling(50).mean()

    fila_hoy = df.iloc[-1]

    return {
        "avwap_ytd": fila_hoy.get("AVWAP_YTD"),
        "avwap_52w_high": fila_hoy.get("AVWAP_52W_High"),
        "avwap_ultimo_gap": fila_hoy.get("AVWAP_Ultimo_Gap"),
        "apoyo_avwap": evaluar_apoyo_avwap(fila_hoy),
        "atr_ratio": fila_hoy.get("ATR_Ratio"),
        "atr_contraction": evaluar_atr_contraction(fila_hoy),
        "pendiente_ok": evaluar_pendiente_positiva(df["Close"]),
        "cruce_avwap_52w": detectar_cruce_avwap_52w(df),
    }


def calcular_radar_score(
    df_rs: pd.DataFrame,
    rs_por_sector: dict,
    spy_sobre_sma50: bool,
    regimen: dict,
    precios_ohlc: dict,
) -> pd.DataFrame:
    """
    Agrega Radar_Score y las columnas nuevas a df_rs. No modifica ninguna
    columna existente.

    precios_ohlc: {ticker: DataFrame OHLCV}, de traer_datos() en datos.py v3.

    NOTA v2.1: ya no recibe dist_days -- Distribution Days dejo de influir
    en el calculo del score (ver docstring del modulo). Si tu main.py
    todavia llama a esta funcion pasando dist_days como quinto argumento,
    hay que sacar ese argumento de la llamada (ver INTEGRACION).
    """
    columnas_nuevas = [
        "AVWAP_YTD", "AVWAP_52W_High", "AVWAP_Ultimo_Gap",
        "Apoyo_AVWAP", "ATR_Ratio", "ATR_Contraction",
        "Pendiente_OK", "Cruce_AVWAP_52w", "Radar_Score",
    ]
    if df_rs.empty:
        for c in columnas_nuevas:
            df_rs[c] = []
        return df_rs

    # v2.2: ni VIX ni Distribution Days multiplican el score -- ambos
    # quedan como badges informativos, calculados aparte en main.py.
    # regimen se sigue recibiendo como parámetro por compatibilidad con
    # la firma existente, pero ya no se usa acá.

    filas_nuevas = []
    scores = []

    for _, fila in df_rs.iterrows():
        ticker = fila.get("Ticker")
        ind = _procesar_indicadores_ticker(precios_ohlc.get(ticker)) if precios_ohlc else None

        comp_rs = round((fila.get("RS_Score") or 0) / 100 * 25, 2)

        vcp_valido = bool(fila.get("VCP_valido"))
        atr_contraction = bool(ind and ind["atr_contraction"])
        comp_contraccion = (20 if vcp_valido else 0) + (5 if atr_contraction else 0)

        comp_vol = _componente_volumen(fila.get("Vol_rel"))

        pendiente_ok = bool(ind and ind["pendiente_ok"])
        comp_tendencia = _componente_tendencia(
            fila.get("Sobre_SMA50"), fila.get("Dist_SMA200_%"),
            rs_por_sector.get(fila.get("Sector")), spy_sobre_sma50, pendiente_ok,
        )

        apoyo_avwap = bool(ind and ind["apoyo_avwap"])
        comp_avwap = 10 if apoyo_avwap else 0

        comp_52w = _componente_52_semanas(fila.get("Dist_Max52w_%"))

        bruto = comp_rs + comp_contraccion + comp_vol + comp_tendencia + comp_avwap + comp_52w
        cruce_52w = bool(ind and ind["cruce_avwap_52w"])
        bono_cruce = 5 if cruce_52w else 0

        score_final = round(min(100, bruto) + bono_cruce, 1)
        score_final = min(100.0, score_final)
        scores.append(score_final)

        filas_nuevas.append({
            "AVWAP_YTD": ind["avwap_ytd"] if ind else None,
            "AVWAP_52W_High": ind["avwap_52w_high"] if ind else None,
            "AVWAP_Ultimo_Gap": ind["avwap_ultimo_gap"] if ind else None,
            "Apoyo_AVWAP": apoyo_avwap,
            "ATR_Ratio": ind["atr_ratio"] if ind else None,
            "ATR_Contraction": atr_contraction,
            "Pendiente_OK": pendiente_ok,
            "Cruce_AVWAP_52w": cruce_52w,
        })

    df_rs = df_rs.copy()
    df_nuevas = pd.DataFrame(filas_nuevas, index=df_rs.index)
    for c in df_nuevas.columns:
        df_rs[c] = df_nuevas[c]
    df_rs["Radar_Score"] = scores

    return df_rs
