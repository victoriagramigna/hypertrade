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
from config import SUBCATEGORIAS

UMBRAL_FUERTE = 70   # RS Score (de cualquiera de los dos) a partir de acá se considera "fuerte"
UMBRAL_DEBIL = 50    # por debajo de acá se considera "débil"

# Bollinger Bands -- banda de SMA20 +/- 2 desvíos estándar del precio.
# BB_Bandwidth_% (ancho de la banda, como % de la SMA20) es lo que se usa
# para detectar "squeeze" (compresión): cuando el ancho de HOY está entre
# los más chicos de los últimos VENTANA_SQUEEZE_PERCENTIL días, el precio
# está comprimido -- históricamente suele preceder a un movimiento fuerte
# (para cualquiera de los dos lados, el squeeze por sí solo no dice la
# dirección -- ver bollinger_squeeze.py para la señal de "liberación" que
# sí la define).
VENTANA_BOLLINGER = 20
DESVIOS_BOLLINGER = 2
# Ventana para juzgar si el ancho de HOY es "chico" en términos históricos
# -- ~6 meses de ruedas, para no comparar contra un régimen de volatilidad
# demasiado viejo.
VENTANA_SQUEEZE_PERCENTIL = 120
PERCENTIL_SQUEEZE = 20   # ancho de hoy entre el 20% más chico de la ventana = squeeze

# Beta vs. benchmark (SPY) -- NO es una señal de compra/venta, es un dato de
# contexto (qué tan "exagerado" se mueve el ticker respecto al mercado). Por
# eso no tiene demora de confirmación ni bitácora propia (ver charla con
# Victoria sobre Beta/Golden-Cross/Squeeze): no hace una predicción que
# después haya que auditar, solo describe volatilidad relativa histórica.
# Ventana de ~6 meses de rendimientos diarios (mismo horizonte que Ret_6m_%)
# -- suficiente para que no lo mueva un solo día raro, sin ser tan largo
# que mezcle un régimen de volatilidad viejo con el actual.
VENTANA_BETA = 126


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


def calcular_rs_score(precios: dict, tickers_sector: dict, benchmark: str, volumenes: dict = None,
                       precios_ohlc: dict = None):
    resultados = []
    if benchmark not in precios:
        raise ValueError(f"Benchmark '{benchmark}' no disponible en los datos traídos")
    bench = precios[benchmark].dropna()
    volumenes = volumenes or {}
    precios_ohlc = precios_ohlc or {}

    # Rendimientos diarios del benchmark -- se calculan una sola vez acá
    # afuera del loop (no por ticker) porque son siempre los mismos.
    ret_bench_diario = bench.pct_change().dropna()

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
        # FIX 30/9: antes "max_52w" se calculaba con close.max() -- el cierre
        # más alto del año, no el precio más alto que de verdad tocó. Un pico
        # intradiario que cerró más abajo quedaba invisible, así que la app
        # mostraba a cualquier ticker MÁS CERCA de su máximo de 52 semanas de
        # lo que en realidad estaba (ver charla del 30/9, comparación con un
        # gráfico de TradingView de SNOW). El dato del precio máximo diario
        # real (High) ya se descarga en datos.py, simplemente no se usaba
        # acá -- ahora sí, con fallback a close.max() si por algún motivo no
        # está disponible para ese ticker puntual.
        ohlc_ticker = precios_ohlc.get(ticker)
        if ohlc_ticker is not None and "High" in ohlc_ticker and not ohlc_ticker["High"].dropna().empty:
            max_52w = ohlc_ticker["High"].dropna().max()
        else:
            max_52w = close.max()

        fila = {
            "Ticker": ticker, "Sector": sector,
            # Subcategoría -- PURAMENTE informativa (ver config.py), no
            # entra en ningún cálculo. None si el ticker no tiene una
            # asignada (sectores que ya eran lo bastante específicos).
            "Subcategoria": SUBCATEGORIAS.get(ticker),
            "Precio": round(precio_actual, 2),
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

        # Beta vs. benchmark -- cov(retorno ticker, retorno benchmark) /
        # var(retorno benchmark), sobre los últimos VENTANA_BETA días en los
        # que AMBOS tienen dato (intersección de fechas, por si alguno tiene
        # algún hueco puntual). Sin esa cantidad de datos en común, mejor no
        # medir que medir mal -- queda en None, no en un número con poca base.
        ret_ticker_diario = close.pct_change().dropna()
        fechas_comunes = ret_ticker_diario.index.intersection(ret_bench_diario.index)
        if len(fechas_comunes) >= VENTANA_BETA:
            fechas_ventana = fechas_comunes[-VENTANA_BETA:]
            r_ticker = ret_ticker_diario.loc[fechas_ventana]
            r_bench = ret_bench_diario.loc[fechas_ventana]
            varianza_bench = r_bench.var()
            if pd.notna(varianza_bench) and varianza_bench > 0:
                beta = r_ticker.cov(r_bench) / varianza_bench
                fila["Beta"] = round(float(beta), 2) if pd.notna(beta) else None
            else:
                fila["Beta"] = None
        else:
            fila["Beta"] = None

        # Bollinger Bands + detección de squeeze (ver constantes arriba).
        sma20_serie = close.rolling(VENTANA_BOLLINGER).mean()
        std20_serie = close.rolling(VENTANA_BOLLINGER).std()
        sma20_hoy, std20_hoy = sma20_serie.iloc[-1], std20_serie.iloc[-1]
        if pd.notna(sma20_hoy) and pd.notna(std20_hoy) and sma20_hoy > 0:
            bb_upper = sma20_hoy + DESVIOS_BOLLINGER * std20_hoy
            bb_lower = sma20_hoy - DESVIOS_BOLLINGER * std20_hoy
            bb_bandwidth = (bb_upper - bb_lower) / sma20_hoy * 100
            fila["BB_SMA20"] = round(float(sma20_hoy), 2)
            fila["BB_Upper"] = round(float(bb_upper), 2)
            fila["BB_Lower"] = round(float(bb_lower), 2)
            fila["BB_Bandwidth_%"] = round(float(bb_bandwidth), 2)

            # Squeeze: el ancho de HOY, comparado contra los últimos
            # VENTANA_SQUEEZE_PERCENTIL días de ancho -- ¿está entre el
            # PERCENTIL_SQUEEZE% más chico de ese tramo? Hace falta la
            # ventana completa de historial para que la comparación tenga
            # sentido; si no alcanza, queda en None (ni squeeze ni no-squeeze,
            # directamente "no medido todavía").
            bandwidth_serie = ((sma20_serie + DESVIOS_BOLLINGER * std20_serie)
                                - (sma20_serie - DESVIOS_BOLLINGER * std20_serie)) / sma20_serie * 100
            bandwidth_historico = bandwidth_serie.dropna().iloc[-VENTANA_SQUEEZE_PERCENTIL:]
            if len(bandwidth_historico) >= VENTANA_SQUEEZE_PERCENTIL:
                umbral_squeeze = bandwidth_historico.quantile(PERCENTIL_SQUEEZE / 100)
                fila["Squeeze_Comprimido"] = bool(bb_bandwidth <= umbral_squeeze)
            else:
                fila["Squeeze_Comprimido"] = None
        else:
            fila["BB_SMA20"] = None
            fila["BB_Upper"] = None
            fila["BB_Lower"] = None
            fila["BB_Bandwidth_%"] = None
            fila["Squeeze_Comprimido"] = None

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
