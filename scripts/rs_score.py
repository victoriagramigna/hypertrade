"""
Cálculo de RS Score (Relative Strength) vs benchmark, agrupable por sector.
Además, expone RSI, volumen relativo, y SMA50/SMA200 (valor real y % de
distancia) para TODOS los tickers del universo -- antes estos datos solo
se calculaban puertas adentro para los tickers con alerta activa; ahora
quedan disponibles para cualquier ticker, tenga o no un evento hoy.

CAMBIO: además del RS Score de siempre (contra el SPY), ahora también se
calcula RS_Score_Sector -- la MISMA cuenta, pero contra el promedio de los
demás tickers del propio sector en vez de contra el mercado. Caso que lo
motiva (dossier "Warren Bife" que trajo Victoria): si TODO el sector
Energía sube fuerte porque subió el petróleo, un ticker puede verse
"líder" contra el SPY sin ser en realidad el más fuerte DENTRO de su
propio sector -- solo viene arrastrado. Con un solo número (RS vs. SPY)
eso no se distingue; con los dos, sí.
"""
import pandas as pd
from vcp import detectar_vcp

UMBRAL_FUERTE = 70   # RS Score (de cualquiera de los dos) a partir de acá se considera "fuerte"
UMBRAL_DEBIL = 50    # por debajo de acá se considera "débil"


def _rsi(serie, periodo=14):
    delta = serie.diff()
    ganancia = delta.clip(lower=0).rolling(periodo).mean()
    perdida = (-delta.clip(upper=0)).rolling(periodo).mean()
    rs = ganancia / perdida
    return 100 - (100 / (1 + rs))


def _perfil_fuerza(row) -> str | None:
    """Cruza RS_Score (vs. mercado) con RS_Score_Sector (vs. pares del
    sector) en 4 lecturas posibles. None si el sector no tiene al menos
    otro ticker para comparar (la cuenta no tendría sentido con 1 solo)."""
    if row.get("_n_sector", 0) < 2:
        return None
    rs_m, rs_s = row.get("RS_Score"), row.get("RS_Score_Sector")
    if rs_m is None or rs_s is None or pd.isna(rs_m) or pd.isna(rs_s):
        return None

    fuerte_m, debil_m = rs_m >= UMBRAL_FUERTE, rs_m < UMBRAL_DEBIL
    fuerte_s, debil_s = rs_s >= UMBRAL_FUERTE, rs_s < UMBRAL_DEBIL

    if fuerte_m and fuerte_s:
        return "Líder real: le gana al mercado Y a sus pares del sector"
    if fuerte_m and debil_s:
        return "Arrastrado por el sector: le gana al mercado, pero no a sus propios pares"
    if debil_m and fuerte_s:
        return "El mejor de un sector débil: le gana a sus pares, pero no al mercado"
    if debil_m and debil_s:
        return "Débil en las dos comparaciones"
    return "Mixto, sin lectura clara"


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
            # Retornos crudos (sin redondear) -- se necesitan para el promedio
            # sectorial de RS_Score_Sector más abajo; se descartan al final.
            "_ret_1m": ret_1m, "_ret_3m": ret_3m, "_ret_6m": ret_6m,
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

    # --- RS Score CONTRA EL SECTOR (ver docstring del módulo) ---
    # Misma cuenta que RS_raw (mezcla de retorno 1m/3m/6m, pesos 40/30/30),
    # pero el "benchmark" de cada ticker pasa a ser el promedio de sus
    # propios pares de sector en vez del SPY. Se rankea igual que el RS
    # Score de siempre (percentil 0-100 sobre TODO el universo), para que
    # los dos números queden en la misma escala y se puedan cruzar.
    df["_n_sector"] = df.groupby("Sector")["Ticker"].transform("count")
    prom_sector = df.groupby("Sector")[["_ret_1m", "_ret_3m", "_ret_6m"]].transform("mean")
    df["RS_raw_Sector"] = (
        (df["_ret_1m"] - prom_sector["_ret_1m"]) * 0.4
        + (df["_ret_3m"] - prom_sector["_ret_3m"]) * 0.3
        + (df["_ret_6m"] - prom_sector["_ret_6m"]) * 0.3
    )
    # Sin al menos otro ticker en el sector, "compararse contra el propio
    # sector" no significa nada -- queda en None, no en un número inventado.
    df.loc[df["_n_sector"] < 2, "RS_raw_Sector"] = float("nan")
    df["RS_Score_Sector"] = (df["RS_raw_Sector"].rank(pct=True) * 100).round(1)
    df["Perfil_Fuerza"] = df.apply(_perfil_fuerza, axis=1)

    columnas_auxiliares = ["RS_raw", "RS_raw_Sector", "_ret_1m", "_ret_3m", "_ret_6m", "_n_sector"]
    return df.drop(columns=columnas_auxiliares).sort_values("RS_Score", ascending=False).reset_index(drop=True)
