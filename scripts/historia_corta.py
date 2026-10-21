"""
Tickers con HISTORIA CORTA (cotizan hace poco, ej. SPCX, SKHY).

El radar exige 200 ruedas (datos.py) porque casi todo -- Fuerza Relativa, Radar
Score, SMA200, Screener, alertas -- depende de eso. Un ticker nuevo con menos
queda en tickers_fallidos. Este módulo NO cambia eso: toma a esos tickers y, solo
para mostrarlos en la solapa Mercado, calcula lo que sí se puede con poca historia
(precio, variación del día / 5 ruedas / 1 mes, RSI, distancia a SMA20 y SMA50 si
alcanzan las ruedas). No entra en ranking, Radar Score, Screener ni alertas.
Cuando el ticker junta 200 ruedas, pasa solo al radar normal y sale de acá.

Es informativo y a prueba de fallos: cualquier error devuelve lista vacía y no
afecta al resto de la corrida. Pedido de Victoria (21/10) para poder seguir SPCX.
"""
import logging
import re

log = logging.getLogger("radar.historia_corta")

MIN_RUEDAS = 5          # menos que esto no hay nada útil para mostrar
RUEDAS_RADAR = 200      # las que exige el radar normal (datos.py)


def _a_float(x, nd=2):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if x == x and abs(x) != float("inf") else None


def metricas(close, ticker: str, sector: str) -> dict | None:
    """Calcula las métricas livianas a partir de la serie de cierres. Pura: no baja nada."""
    close = close.dropna()
    n = len(close)
    if n < MIN_RUEDAS:
        return None
    px = float(close.iloc[-1])

    def ret(k):
        return _a_float((px / float(close.iloc[-1 - k]) - 1) * 100) if n > k and float(close.iloc[-1 - k]) > 0 else None

    def dist(k):
        return _a_float((px / float(close.iloc[-k:].mean()) - 1) * 100) if n >= k else None

    rsi = None
    if n > 15:
        # mismo RSI (promedio simple de 14) que usa el radar en rs_score._rsi
        d = close.diff()
        g, p_ = d.clip(lower=0).rolling(14).mean(), (-d.clip(upper=0)).rolling(14).mean()
        rsi = _a_float(100 - 100 / (1 + g.iloc[-1] / p_.iloc[-1]), 1) if float(p_.iloc[-1]) > 0 else (100.0 if float(g.iloc[-1]) > 0 else None)
    idx = close.index
    fecha = lambda i: str(idx[i])[:10]
    return {
        "Ticker": ticker,
        "Sector": sector,
        "Precio": _a_float(px),
        "Var_dia_%": ret(1),
        "Ret_5d_%": ret(5),
        "Ret_1m_%": ret(21),
        "RSI": rsi,
        "Dist_SMA20_%": dist(20),
        "Dist_SMA50_%": dist(50),
        "Ruedas": n,
        "Ruedas_faltantes": max(0, RUEDAS_RADAR - n),
        "Desde": fecha(0),
        "Ultimo_dato": fecha(-1),
    }


def calcular(fallidos_universo: list, tickers: dict, periodo: str = "1y") -> list:
    """fallidos_universo: lista [{'ticker', 'motivo'}] de datos.py. Devuelve lista de dicts de métricas."""
    salida = []
    try:
        candidatos = []
        for f in fallidos_universo or []:
            m = re.search(r"\((\d+) filas", f.get("motivo", ""))
            if m and MIN_RUEDAS <= int(m.group(1)) < RUEDAS_RADAR and f.get("ticker") in tickers:
                candidatos.append(f["ticker"])
        if not candidatos:
            return []
        import yfinance as yf
        for t in candidatos:
            try:
                hist = yf.Ticker(t).history(period=periodo, auto_adjust=True)
                fila = metricas(hist["Close"], t, tickers[t]) if not hist.empty else None
                if fila:
                    salida.append(fila)
            except Exception as e:
                log.warning(f"historia corta: {t} falló ({e})")
    except Exception as e:
        log.warning(f"historia corta: error general ({e}) -- se omite")
        return []
    return salida
