"""
Reconstruye la Fuerza Relativa (RS_Score) de las ultimas ~18 semanas con precios
historicos, usando la MISMA cuenta que rs_score.py (40% 1m + 30% 3m + 30% 6m contra
el SPY, puesta en percentil entre todos los tickers). Sirve para que el cuadrante de
rotacion tenga recorrido largo desde el primer dia, sin esperar a juntarlo dia a dia.

Aparte y aditivo: escribe data/rs_score_historial_largo.jsonl (no toca
rs_score_historial.jsonl ni ningun registro de la Auditoria). Es un archivo
reconstruido, se reemplaza entero cada vez que se corre. Se corre a mano.
"""
import json, logging, sys
import pandas as pd

sys.path.insert(0, "scripts")
from config import TICKERS, BENCHMARK

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("rs_backfill")
DIAS_SALIDA = 95        # ruedas hacia atras que se guardan (~19 semanas)
SALIDA = "data/rs_score_historial_largo.jsonl"


def _bajar(simbolo):
    import yfinance as yf
    h = yf.Ticker(simbolo).history(period="2y", auto_adjust=True)
    if h is None or len(h) < 200:
        return None
    s = h["Close"].copy()
    s.index = (s.index.tz_localize(None) if getattr(s.index, "tz", None) is not None else s.index).normalize()
    return s[~s.index.duplicated(keep="last")]


def calcular(cierres: pd.DataFrame, benchmark: str) -> pd.DataFrame:
    """cierres: columnas = tickers (incluye benchmark), indice = fechas. Devuelve RS por fecha/ticker."""
    def r(d):  # misma definicion que rs_score.rendimiento: close[-1]/close[-d] - 1
        return cierres / cierres.shift(d - 1) - 1
    r1, r3, r6 = r(21), r(63), r(126)
    b1, b3, b6 = r1[benchmark], r3[benchmark], r6[benchmark]
    raw = (r1.sub(b1, axis=0) * 0.4) + (r3.sub(b3, axis=0) * 0.3) + (r6.sub(b6, axis=0) * 0.3)
    raw = raw.drop(columns=[benchmark])
    return (raw.rank(axis=1, pct=True) * 100).round(1)


def main():
    spy = _bajar(BENCHMARK)
    if spy is None:
        log.error("No se pudo bajar SPY -- se aborta"); sys.exit(1)
    series, fallo = {}, 0
    for t in TICKERS:
        try:
            s = _bajar(t)
        except Exception as e:
            s = None
        if s is None:
            fallo += 1; continue
        series[t] = s
    log.info(f"{len(series)} tickers con datos, {fallo} sin datos")
    if len(series) < 100:
        log.error("Muy pocos tickers -- se aborta"); sys.exit(1)
    cierres = pd.DataFrame(series).reindex(spy.index).ffill(limit=3)
    cierres[BENCHMARK] = spy
    rs = calcular(cierres, BENCHMARK)
    rs = rs.iloc[-DIAS_SALIDA:]
    with open(SALIDA, "w", encoding="utf-8") as f:
        for fecha, fila in rs.iterrows():
            d = {k: float(v) for k, v in fila.dropna().items()}
            f.write(json.dumps({"fecha": fecha.strftime("%Y-%m-%d"), "rs": d, "reconstruido": True}, ensure_ascii=False) + "\n")
    log.info(f"Listo: {len(rs)} fechas -> {SALIDA}")


if __name__ == "__main__":
    main()
