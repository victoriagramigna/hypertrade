"""
Traída de datos de precios/volumen. Si un ticker falla, se reintenta una vez
más antes de darlo por perdido -- yfinance tiene fallos aleatorios y
transitorios conocidos (le pasa hasta a tickers gigantes como AAPL a veces,
según reportes de otros usuarios de la librería), no siempre significa que
el ticker esté mal escrito o delistado de verdad.

CAMBIO (HyperTrade): además de precios (Close) y volumenes (Volume), ahora
también se guarda el DataFrame OHLCV completo por ticker en un tercer
diccionario, precios_ohlc. Esto no cambia en nada lo que ya usan
rs_score.py, alertas.py, movimientos.py, etc. -- siguen recibiendo
exactamente las mismas Series que antes. El OHLCV completo es SOLO para
los indicadores nuevos que lo necesitan (AVWAP, ATR), que antes no tenían
con qué calcularse porque se descartaban Open/High/Low.

CAMBIO (frescura por ticker, 29/9): además de "falló la descarga", ahora se
detecta el caso más sutil de "la descarga funcionó pero el último dato
sigue siendo el del día hábil anterior" -- le pasó a varios tickers (no
todos) puntualmente en corridas de lunes a la noche, cuando Yahoo Finance
todavía no había terminado de publicar el cierre del día tras el fin de
semana. Sin este chequeo, ese precio viejo se usaba como si fuera "el
precio de hoy" y podía disparar una señal (ej. Gap alcista) que en
realidad era falsa.

La referencia para decidir "cuál es el último día hábil real" es el propio
benchmark (SPY): no hace falta mantener un calendario de feriados de EEUU,
alcanza con comparar la fecha del último dato de cada ticker contra la
fecha del último dato de SPY en la MISMA corrida. Si coinciden, está
al día. Si el ticker quedó atrás, está desactualizado -- se reintenta una
vez y, si sigue atrás (o falla), se lo excluye de esta corrida (no se
calcula ninguna señal para él) en vez de usar el dato viejo.
"""
import logging
import time
import yfinance as yf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("radar.datos")

# Pausa antes de reintentar los tickers que quedaron desactualizados,
# dándole tiempo a Yahoo Finance de terminar de publicar el cierre.
ESPERA_REINTENTO_FRESCURA_SEG = 90


def _traer_uno(simbolo: str, periodo: str):
    """
    Un solo intento de traer un ticker. Lanza excepción si falla.
    Devuelve (Close, Volume, ohlcv) -- ohlcv es el DataFrame completo
    con solo las columnas Open/High/Low/Close/Volume (se descartan
    Dividends y Stock Splits, que no se usan en ningún cálculo).
    """
    hist = yf.Ticker(simbolo).history(period=periodo, auto_adjust=True)
    if hist.empty or len(hist) < 200:
        raise ValueError(f"datos insuficientes ({len(hist)} filas, se necesitan >=200)")
    ohlcv = hist[["Open", "High", "Low", "Close", "Volume"]]
    return hist["Close"], hist["Volume"], ohlcv


def _ultima_fecha(serie):
    """Fecha (sin hora ni zona) del último dato disponible de una Serie."""
    s = serie.dropna()
    if s.empty:
        return None
    idx = s.index[-1]
    return idx.tz_localize(None) if getattr(idx, "tzinfo", None) is not None else idx


def traer_datos(tickers: dict, benchmark: str, periodo: str = "1y", reintentos: int = 1):
    """
    tickers: dict {ticker: sector}
    Devuelve (precios, volumenes, precios_ohlc, tickers_fallidos, tickers_desactualizados)
    precios/volumenes: dict {ticker: pd.Series}  (sin cambios respecto a v2)
    precios_ohlc: dict {ticker: pd.DataFrame}  (Open/High/Low/Close/Volume)
    tickers_fallidos: lista de tickers que no se pudieron traer (tras los
    reintentos), con el motivo del último intento
    tickers_desactualizados: lista de tickers cuya descarga funcionó pero
    cuyo último dato quedó atrás respecto al del benchmark (ver docstring
    del módulo) -- se excluyen de precios/volumenes/precios_ohlc igual que
    un fallido, para que ninguna señal se calcule con un precio viejo.
    """
    simbolos = list(tickers.keys()) + [benchmark]
    precios, volumenes, precios_ohlc = {}, {}, {}
    fallidos_primera_pasada = {}

    log.info(f"Descargando {len(simbolos)} símbolos (período={periodo})...")

    for simbolo in simbolos:
        try:
            precios[simbolo], volumenes[simbolo], precios_ohlc[simbolo] = _traer_uno(simbolo, periodo)
        except Exception as e:
            fallidos_primera_pasada[simbolo] = str(e)

    # --- Reintento: solo para los que fallaron en la primera pasada ---
    if fallidos_primera_pasada and reintentos > 0:
        log.info(f"Reintentando {len(fallidos_primera_pasada)} símbolo(s) que fallaron: "
                 f"{sorted(fallidos_primera_pasada.keys())}")
        time.sleep(2)  # pequeña pausa, por si el fallo fue por límite de tasa momentáneo
        for simbolo in list(fallidos_primera_pasada.keys()):
            try:
                precios[simbolo], volumenes[simbolo], precios_ohlc[simbolo] = _traer_uno(simbolo, periodo)
                del fallidos_primera_pasada[simbolo]  # se recuperó en el reintento
                log.info(f"  ✓ {simbolo}: se recuperó en el reintento")
            except Exception as e:
                fallidos_primera_pasada[simbolo] = str(e)  # actualiza el motivo por si cambió

    fallidos = [{"ticker": s, "motivo": m} for s, m in fallidos_primera_pasada.items()]
    for f in fallidos:
        log.warning(f"  ⚠ {f['ticker']}: falló tras reintento ({f['motivo']}) -- se omite de esta corrida")

    # --- Frescura: ¿el último dato de cada ticker coincide con el del benchmark? ---
    desactualizados = []
    if benchmark in precios:
        fecha_benchmark = _ultima_fecha(precios[benchmark])
        candidatos = []
        for simbolo in list(precios.keys()):
            if simbolo == benchmark:
                continue
            fecha_ticker = _ultima_fecha(precios[simbolo])
            if fecha_ticker is None or (fecha_benchmark is not None and fecha_ticker < fecha_benchmark):
                candidatos.append(simbolo)

        if candidatos and fecha_benchmark is not None:
            log.warning(f"{len(candidatos)} símbolo(s) con dato desactualizado respecto a {benchmark} "
                        f"({fecha_benchmark.date()}): {sorted(candidatos)} -- reintentando en "
                        f"{ESPERA_REINTENTO_FRESCURA_SEG}s")
            time.sleep(ESPERA_REINTENTO_FRESCURA_SEG)
            for simbolo in candidatos:
                fecha_previa = _ultima_fecha(precios[simbolo])
                try:
                    nuevo_close, nuevo_vol, nuevo_ohlc = _traer_uno(simbolo, periodo)
                except Exception as e:
                    log.warning(f"  ⚠ {simbolo}: sigue desactualizado, el reintento también falló ({e}) "
                                f"-- se omite de esta corrida")
                    desactualizados.append({
                        "ticker": simbolo,
                        "fecha_dato": fecha_previa.date().isoformat() if fecha_previa is not None else None,
                        "fecha_esperada": fecha_benchmark.date().isoformat(),
                    })
                    del precios[simbolo], volumenes[simbolo], precios_ohlc[simbolo]
                    continue

                fecha_nueva = _ultima_fecha(nuevo_close)
                if fecha_nueva is not None and fecha_nueva >= fecha_benchmark:
                    precios[simbolo], volumenes[simbolo], precios_ohlc[simbolo] = nuevo_close, nuevo_vol, nuevo_ohlc
                    log.info(f"  ✓ {simbolo}: se actualizó en el reintento ({fecha_nueva.date()})")
                else:
                    log.warning(f"  ⚠ {simbolo}: sigue con dato del {fecha_nueva.date() if fecha_nueva else '?'} "
                                f"tras el reintento -- se omite de esta corrida")
                    desactualizados.append({
                        "ticker": simbolo,
                        "fecha_dato": fecha_nueva.date().isoformat() if fecha_nueva is not None else None,
                        "fecha_esperada": fecha_benchmark.date().isoformat(),
                    })
                    del precios[simbolo], volumenes[simbolo], precios_ohlc[simbolo]

    log.info(f"OK: {len(precios)} símbolos. Fallidos: {len(fallidos)}. Desactualizados: {len(desactualizados)}")
    return precios, volumenes, precios_ohlc, fallidos, desactualizados


if __name__ == "__main__":
    # Prueba rápida (requiere red habilitada al host de Yahoo Finance --
    # en este sandbox de desarrollo está bloqueado a propósito; correr
    # este archivo directamente en GitHub Actions o en tu máquina local).
    from config import TICKERS, BENCHMARK
    precios, volumenes, precios_ohlc, fallidos, desactualizados = traer_datos(TICKERS, BENCHMARK)
    print(f"Precios OK: {list(precios.keys())}")
    print(f"Fallidos: {fallidos}")
    print(f"Desactualizados: {desactualizados}")
