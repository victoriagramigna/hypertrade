"""
Señal de "CEDEAR caro/barato": compara el precio real del CEDEAR en pesos
(BYMA, vía data912.com) contra su valor teórico (precio de la acción real
en USD x CCL / ratio de conversión).

Esto NO es una señal de "buena empresa" -- es una señal de "buen momento de
ejecución hoy en pesos", útil sobre todo en feriados de EEUU (el precio en
USD queda congelado, pero el CEDEAR y el CCL siguen moviéndose en Argentina).

data912.com es una API pública/educativa, sin auth, con caché de ~2hs.
Si falla o cambia de formato, esta función se degrada sin romper el resto
de la corrida (mismo patrón que macro_local.py).
"""
import logging
import requests

from config import RATIOS_CEDEAR, BRECHA_CEDEAR_ALERTA_PCT, ALIAS_CEDEAR_DATA912

log = logging.getLogger("radar.cedear_pricing")

BASE = "https://data912.com"
TIMEOUT = 20   # data912 es gratis/hobby -- a veces tarda; 10s daba falsos timeouts
REINTENTOS = 2  # un reintento extra si el primero da timeout/error de red

# Nombres de campo candidatos -- no pudimos confirmar el schema exacto de
# data912 sin poder probarlo en vivo desde este entorno de desarrollo, así
# que probamos varias claves típicas. Si ninguna aparece, se loguea la
# respuesta cruda para poder ajustar esto con el primer dato real.
CAMPOS_PRECIO_CANDIDATOS = ["c", "close", "last", "px", "precio", "ultimo"]
CAMPOS_SYMBOL_CANDIDATOS = ["symbol", "ticker", "simbolo", "ticker_symbol"]


def _extraer_campo(item: dict, candidatos: list, default=None):
    for campo in candidatos:
        if campo in item and item[campo] not in (None, ""):
            return item[campo]
    return default


def _get_con_reintento(url: str):
    """GET con un reintento simple si el primero da timeout/error de red.
    data912 es gratis/hobby, a veces tarda -- un segundo intento suele alcanzar."""
    ultimo_error = None
    for intento in range(REINTENTOS + 1):
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except Exception as e:
            ultimo_error = e
            if intento < REINTENTOS:
                log.info(f"  reintentando {url} (intento {intento + 2}/{REINTENTOS + 1})...")
    raise ultimo_error


def traer_ccl():
    """Devuelve el CCL representativo del mercado, o None si falla.

    IMPORTANTE: /live/ccl de data912 no da un único valor -- da una FILA
    POR TICKER, cada una con su propio CCL implícito (varía según qué ADR/
    CEDEAR se use para calcularlo). Se toma la mediana de "CCL_close" de
    todas las filas, más estable que agarrar cualquiera al azar.
    Campos confirmados en producción (16/9/2026): CCL_bid, CCL_ask,
    CCL_close, CCL_mark, ticker_usa, ticker_ar, ars_volume, volume_rank,
    arg_panel, usa_panel.
    """
    try:
        resp = _get_con_reintento(f"{BASE}/live/ccl")
        data = resp.json()
        filas = data if isinstance(data, list) else [data]

        valores = []
        for fila in filas:
            valor = _extraer_campo(fila, ["CCL_close", "CCL_mark", "CCL_ask", "CCL_bid"]
                                    + ["venta", "ask", "sell"] + CAMPOS_PRECIO_CANDIDATOS)
            if valor is not None:
                try:
                    valores.append(float(valor))
                except (TypeError, ValueError):
                    continue

        if not valores:
            log.warning(f"CCL: ninguna fila trajo un valor utilizable. Ejemplo de fila cruda: {filas[0] if filas else None}")
            return None

        valores.sort()
        return valores[len(valores) // 2]  # mediana
    except Exception as e:
        log.warning(f"No se pudo traer CCL: {e}")
        return None


def traer_precios_cedears(tickers: list):
    """Devuelve {ticker: precio_ars} para los tickers pedidos, o {} si falla todo."""
    try:
        resp = _get_con_reintento(f"{BASE}/live/arg_cedears")
        data = resp.json()
    except Exception as e:
        log.warning(f"No se pudo traer el panel de CEDEARs: {e}")
        return {}

    precios = {}
    tickers_set = set(tickers)
    # data912 -> símbolo interno del radar, para los casos donde difieren (ver config.py)
    alias_inversa = {v: k for k, v in ALIAS_CEDEAR_DATA912.items()}

    for item in data:
        symbol = _extraer_campo(item, CAMPOS_SYMBOL_CANDIDATOS)
        if symbol is None:
            continue
        symbol = str(symbol).upper().replace(".BA", "").strip()
        symbol_interno = alias_inversa.get(symbol, symbol)
        if symbol_interno not in tickers_set:
            continue
        precio = _extraer_campo(item, CAMPOS_PRECIO_CANDIDATOS)
        if precio is not None:
            precios[symbol_interno] = float(precio)

    faltantes = tickers_set - set(precios.keys())
    if faltantes:
        log.warning(f"No se encontró precio de CEDEAR para: {sorted(faltantes)} "
                     f"(puede ser un problema de nombre de campo -- revisar schema real)")
    return precios


def calcular_brechas_cedear(precios_usd: dict):
    """
    precios_usd: {ticker: precio_actual_en_usd} (ya lo tenemos calculado en rs_score.py)
    Devuelve una lista de dicts, uno por CEDEAR con ratio conocido, con el
    precio real, el teórico, y el % de brecha entre ambos.
    """
    ccl = traer_ccl()
    if ccl is None:
        return {"ccl": None, "sin_datos": True, "cedears": []}

    tickers_con_ratio = [t for t in RATIOS_CEDEAR if t in precios_usd]
    precios_ars = traer_precios_cedears(tickers_con_ratio)

    resultados = []
    for ticker in tickers_con_ratio:
        precio_usd = precios_usd[ticker]
        ratio = RATIOS_CEDEAR[ticker]
        precio_ars_real = precios_ars.get(ticker)

        teorico = round((precio_usd * ccl) / ratio, 2)

        if precio_ars_real is None:
            resultados.append({
                "Ticker": ticker, "sin_datos": True,
                "Precio_teorico_ARS": teorico,
                "Ratio": ratio,
            })
            continue

        brecha_pct = round((precio_ars_real / teorico - 1) * 100, 2)
        distorsion = abs(brecha_pct) >= BRECHA_CEDEAR_ALERTA_PCT

        resultados.append({
            "Ticker": ticker,
            "sin_datos": False,
            "Precio_real_ARS": precio_ars_real,
            "Precio_teorico_ARS": teorico,
            "Brecha_%": brecha_pct,
            "Estado": ("Caro respecto al teórico" if brecha_pct > 0 else "Barato respecto al teórico"),
            "Distorsion_relevante": distorsion,
            "Ratio": ratio,  # cuántos CEDEARs equivalen a 1 acción subyacente -- lo usa
            # "Mi Cartera" para convertir un precio de compra en pesos a su
            # equivalente en dólares (que es contra lo que se compara el stop-loss)
        })

    return {"ccl": ccl, "sin_datos": False, "cedears": resultados}
