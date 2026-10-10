"""
Cierres diarios de todos los tickers del universo -- registro append-only.

Guarda UNA linea por rueda en data/cierres_diarios.jsonl:
    {"fecha": "2026-10-09", "c": {"AAPL": 254.12, "SPY": 671.3, ...}}
Es solo para consulta/auditoria/backtests propios: la app NO lo lee, no toca
ultimo.json ni ningun registro de la Auditoria. Precios ajustados (auto_adjust),
igual que el resto del radar.

Reglas:
  * Una sola linea por fecha (si ya existe, no se escribe de nuevo).
  * Solo se guarda un dia ya CERRADO: la fecha del dato (la del SPY) debe ser
    anterior a hoy (UTC), o la corrida debe ser posterior a las 21:10 UTC.
  * Corrida degradada (>= umbral de fallidos) -> no se guarda.
  * Cada ticker entra solo si su ultimo dato es de esa misma fecha.

Modo carga inicial (a mano, desde Actions):
    python scripts/cierres_diarios.py --backfill
Baja ~1 anio con yfinance y agrega SOLO las fechas que faltan (no modifica
lineas ya existentes; reescribe el archivo ordenado por fecha).
"""
import json, logging, os, sys
from datetime import datetime, timezone

log = logging.getLogger("radar.cierres_diarios")
RUTA = "data/cierres_diarios.jsonl"
HORA_CIERRE_UTC = (21, 10)
RUEDAS_BACKFILL = 260


def _leer():
    out = {}
    if not os.path.exists(RUTA):
        return out
    with open(RUTA, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                d = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if d.get("fecha"):
                out.setdefault(d["fecha"], linea)
    return out


def registrar(precios: dict, tickers, benchmark: str, ahora=None, degradada=False):
    """Agrega la linea del ultimo dia cerrado si falta. Nunca rompe la corrida."""
    try:
        if degradada:
            return None
        ahora = ahora or datetime.now(timezone.utc)
        spy = precios.get(benchmark)
        if spy is None or spy.dropna().empty:
            return None
        fecha = str(spy.dropna().index[-1])[:10]
        hoy = ahora.strftime("%Y-%m-%d")
        cerrado = fecha < hoy or (ahora.hour, ahora.minute) >= HORA_CIERRE_UTC
        if not cerrado or fecha in _leer():
            return None
        c = {}
        for t in list(tickers) + [benchmark]:
            s = precios.get(t)
            if s is None:
                continue
            s = s.dropna()
            if s.empty or str(s.index[-1])[:10] != fecha:
                continue
            c[t] = round(float(s.iloc[-1]), 2)
        if len(c) < 50:
            return None
        with open(RUTA, "a", encoding="utf-8") as f:
            f.write(json.dumps({"fecha": fecha, "c": c}, ensure_ascii=False, separators=(",", ":")) + "\n")
        log.info(f"Cierres de {fecha} guardados ({len(c)} tickers) en {RUTA}")
        return fecha
    except Exception as e:
        log.error(f"Cierres diarios fallo, no afecta al resto de la corrida: {e}")
        return None


def backfill():
    import pandas as pd
    import yfinance as yf
    sys.path.insert(0, "scripts")
    from config import TICKERS, BENCHMARK
    simbolos = list(dict.fromkeys(list(TICKERS) + [BENCHMARK]))
    series = {}
    for i in range(0, len(simbolos), 40):
        lote = simbolos[i:i + 40]
        try:
            df = yf.download(lote, period="2y", auto_adjust=True, progress=False, group_by="column", threads=True)["Close"]
        except Exception as e:
            log.error(f"lote {i} fallo: {e}"); continue
        if isinstance(df, pd.Series):
            df = df.to_frame(lote[0])
        for t in df.columns:
            s = df[t].dropna()
            if len(s):
                s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
                series[t] = s[~s.index.duplicated(keep="last")]
    if BENCHMARK not in series or len(series) < 100:
        log.error("Pocos datos -- se aborta"); sys.exit(1)
    spy_idx = series[BENCHMARK].index[-RUEDAS_BACKFILL:]
    ahora = datetime.now(timezone.utc)
    if spy_idx[-1].strftime("%Y-%m-%d") >= ahora.strftime("%Y-%m-%d") and (ahora.hour, ahora.minute) < HORA_CIERRE_UTC:
        spy_idx = spy_idx[:-1]
    existentes = _leer()
    nuevas = 0
    for fecha in spy_idx:
        k = fecha.strftime("%Y-%m-%d")
        if k in existentes:
            continue
        c = {t: round(float(s.loc[fecha]), 2) for t, s in series.items() if fecha in s.index}
        if len(c) >= 50:
            existentes[k] = json.dumps({"fecha": k, "c": c}, ensure_ascii=False, separators=(",", ":"))
            nuevas += 1
    with open(RUTA, "w", encoding="utf-8") as f:
        for k in sorted(existentes):
            f.write(existentes[k] + "\n")
    log.info(f"Listo: {nuevas} fechas nuevas, {len(existentes)} en total -> {RUTA}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if "--backfill" in sys.argv:
        backfill()
    else:
        print(__doc__)
