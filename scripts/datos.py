"""
Traída de datos de precios/volumen. Si un ticker falla, se reintenta una vez
más antes de darlo por perdido -- yfinance tiene fallos aleatorios y
transitorios conocidos (le pasa hasta a tickers gigantes como AAPL a veces,
según reportes de otros usuarios de la librería), no siempre significa que
el ticker esté mal escrito o delistado de verdad.
"""
import logging
import time
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("radar.datos")


def _traer_uno(simbolo: str, periodo: str):
    """Un solo intento de traer un ticker. Lanza excepción si falla."""
    hist = yf.Ticker(simbolo).history(period=periodo, auto_adjust=True)
    if hist.empty or len(hist) < 200:
        raise ValueError(f"datos insuficientes ({len(hist)} filas, se necesitan >=200)")
    return hist["Close"], hist["Volume"]


def traer_datos(tickers: dict, benchmark: str, periodo: str = "1y", reintentos: int = 1):
    """
    tickers: dict {ticker: sector}
    Devuelve (precios, volumenes, tickers_fallidos)
    precios/volumenes: dict {ticker: pd.Series}
    tickers_fallidos: lista de tickers que no se pudieron traer (tras los
    reintentos), con el motivo del último intento
    """
    simbolos = list(tickers.keys()) + [benchmark]
    precios, volumenes = {}, {}
    fallidos_primera_pasada = {}

    log.info(f"Descargando {len(simbolos)} símbolos (período={periodo})...")

    for simbolo in simbolos:
        try:
            precios[simbolo], volumenes[simbolo] = _traer_uno(simbolo, periodo)
        except Exception as e:
            fallidos_primera_pasada[simbolo] = str(e)

    # --- Reintento: solo para los que fallaron en la primera pasada ---
    if fallidos_primera_pasada and reintentos > 0:
        log.info(f"Reintentando {len(fallidos_primera_pasada)} símbolo(s) que fallaron: "
                 f"{sorted(fallidos_primera_pasada.keys())}")
        time.sleep(2)  # pequeña pausa, por si el fallo fue por límite de tasa momentáneo
        for simbolo in list(fallidos_primera_pasada.keys()):
            try:
                precios[simbolo], volumenes[simbolo] = _traer_uno(simbolo, periodo)
                del fallidos_primera_pasada[simbolo]  # se recuperó en el reintento
                log.info(f"  ✓ {simbolo}: se recuperó en el reintento")
            except Exception as e:
                fallidos_primera_pasada[simbolo] = str(e)  # actualiza el motivo por si cambió

    fallidos = [{"ticker": s, "motivo": m} for s, m in fallidos_primera_pasada.items()]
    for f in fallidos:
        log.warning(f"  ⚠ {f['ticker']}: falló tras reintento ({f['motivo']}) -- se omite de esta corrida")

    log.info(f"OK: {len(precios)} símbolos. Fallidos: {len(fallidos)}")
    return precios, volumenes, fallidos


if __name__ == "__main__":
    # Prueba rápida (requiere red habilitada al host de Yahoo Finance --
    # en este sandbox de desarrollo está bloqueado a propósito; correr
    # este archivo directamente en GitHub Actions o en tu máquina local).
    from config import TICKERS, BENCHMARK
    precios, volumenes, fallidos = traer_datos(TICKERS, BENCHMARK)
    print(f"Precios OK: {list(precios.keys())}")
    print(f"Fallidos: {fallidos}")
