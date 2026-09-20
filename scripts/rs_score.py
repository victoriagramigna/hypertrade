"""
Cálculo de RS Score (Relative Strength) vs benchmark, agrupable por sector.
Además, expone RSI, volumen relativo, y SMA50/SMA200 (valor real y % de
distancia) para TODOS los tickers del universo -- antes estos datos solo
se calculaban puertas adentro para los tickers con alerta activa; ahora
quedan disponibles para cualquier ticker, tenga o no un evento hoy.
"""
import pandas as pd
from vcp import detectar_vcp


def _rsi(serie, periodo=14):
    delta = serie.diff()
    ganancia = delta.clip(lower=0).rolling(periodo).mean()
    perdida = (-delta.clip(upper=0)).rolling(periodo).mean()
    rs = ganancia / perdida
    return 100 - (100 / (1 + rs))


def calcular_rs_score(precios: dict, tickers_sector: dict, benchmark: str, volumenes: dict = None):
    resultados = []
    if benchmark not in precios:
        raise ValueError(f"Benchmark '{benchmark}' no disponible en los datos traídos")
    bench = precios[benchmark].dropna()
    volumenes = volumenes or {}

    def rendimiento(serie, dias):
        if len(serie) <= dias:
            return None
        return (serie.iloc[-1] / serie.iloc[-dias]) - 1

    for ticker, sector in tickers_sector.items():
        if ticker not in precios:
            continue  # ya quedó logueado como fallido en datos.py
        close = precios[ticker].dropna()
        if len(close) < 126:
            continue

        precio_actual = close.iloc[-1]
        ret_1m, ret_3m, ret_6m = rendimiento(close, 21), rendimiento(close, 63), rendimiento(close, 126)
        b_1m, b_3m, b_6m = rendimiento(bench, 21), rendimiento(bench, 63), rendimiento(bench, 126)
        if None in (ret_1m, ret_3m, ret_6m, b_1m, b_3m, b_6m):
            continue

        rs_raw = ((ret_1m - b_1m) * 0.4) + ((ret_3m - b_3m) * 0.3) + ((ret_6m - b_6m) * 0.3)

        sma50_serie = close.rolling(50).mean()
        sma50 = sma50_serie.iloc[-1]
        max_52w = close.max()

        fila = {
            "Ticker": ticker, "Sector": sector, "Precio": round(precio_actual, 2),
            "RS_raw": rs_raw,
            "Ret_1m_%": round(ret_1m * 100, 1), "Ret_3m_%": round(ret_3m * 100, 1),
            "Ret_6m_%": round(ret_6m * 100, 1),
            "Sobre_SMA50": bool(precio_actual > sma50),
            "Dist_Max52w_%": round((precio_actual / max_52w - 1) * 100, 1),
            "SMA50": round(float(sma50), 2) if pd.notna(sma50) else None,
            "Dist_SMA50_%": round((precio_actual / sma50 - 1) * 100, 2) if pd.notna(sma50) else None,
        }

        # SMA200 y RSI necesitan más historia -- si no alcanza, quedan en None
        if len(close) >= 200:
            sma200 = close.rolling(200).mean().iloc[-1]
            fila["SMA200"] = round(float(sma200), 2) if pd.notna(sma200) else None
            fila["Dist_SMA200_%"] = round((precio_actual / sma200 - 1) * 100, 2) if pd.notna(sma200) else None
        else:
            fila["SMA200"] = None
            fila["Dist_SMA200_%"] = None

        rsi_serie = _rsi(close, 14)
        rsi_hoy = rsi_serie.iloc[-1] if len(rsi_serie.dropna()) > 0 else None
        fila["RSI"] = round(float(rsi_hoy), 1) if rsi_hoy is not None and pd.notna(rsi_hoy) else None

        if ticker in volumenes:
            vol = volumenes[ticker].dropna()
            vol_prom20 = vol.rolling(20).mean()
            if len(vol_prom20.dropna()) > 0 and vol_prom20.iloc[-1] > 0:
                fila["Vol_rel"] = round(float(vol.iloc[-1] / vol_prom20.iloc[-1]), 2)
            else:
                fila["Vol_rel"] = None

            # VCP para TODO el universo (antes solo se calculaba puertas
            # adentro del flujo de alertas, para tickers con alerta activa
            # -- el Radar Score lo necesita para cualquier ticker, tenga o
            # no una señal disparada hoy).
            vcp_resultado = detectar_vcp(close, vol)
            fila["VCP_valido"] = bool(vcp_resultado["valido"])
        else:
            fila["Vol_rel"] = None
            fila["VCP_valido"] = False

        resultados.append(fila)

    df = pd.DataFrame(resultados)
    if df.empty:
        return df
    df["RS_Score"] = (df["RS_raw"].rank(pct=True) * 100).round(1)
    return df.drop(columns=["RS_raw"]).sort_values("RS_Score", ascending=False).reset_index(drop=True)
