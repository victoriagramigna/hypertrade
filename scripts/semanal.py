"""
Listas semanales (velas semanales REALES, 5 años) -- registro aparte, de solo agregado.

Pedido de Victoria (22/10): leer el semanal como lo lee Gusti (RSI semanal, SMA14 y EMA200 semanales).
Con el año de datos que baja el radar diario no alcanza para una EMA200 semanal (son ~4 años de
semanas), por eso este script corre aparte: baja 5 años con velas semanales, calcula y publica.

NO toca el radar, ni ultimo.json, ni la Auditoria existente. Escribe:
  data/semanal.json        (se recalcula entero en cada corrida: valores por ticker + las listas de la semana)
  data/log_semanal.jsonl   (append-only; una linea por semana CERRADA; id = fecha del viernes)
  data/semanal_eval.json   (se recalcula entero: como le fue a cada lista despues de 1 y 4 semanas)

Indicadores (sobre el cierre semanal ajustado):
  RSI(14) de Wilder (el mismo suavizado que usa TradingView), SMA(14), EMA(200).
  La EMA200 semanal solo se calcula si el ticker tiene >= MIN_SEMANAS_EMA200 semanas.

Listas (condiciones de hoy, sin recomendacion: ordenan, no dicen que hacer):
  ema200_apoyo           cierra a menos de CERCA_EMA200_PCT% de su EMA200 semanal, que viene subiendo
  retroceso_en_tendencia cierra sobre su EMA200 pero bajo su SMA14, con RSI semanal bajo 50
  sobrevendido           RSI semanal <= RSI_SOBREVENDIDO
  estirado               RSI semanal >= RSI_ESTIRADO
  muy_bajo_sma14         cierra mas de MUY_BAJO_SMA14_PCT% bajo su SMA14 semanal (CANDIDATA: salio del estudio de 10 años
                         como la unica tendencia positiva, pero sin llegar a ser concluyente; se mide en vivo)

Evaluacion: retorno a 1 y 4 semanas, y exceso contra SPY. "vivo" = solo semanas ya registradas en el
log (sin sesgo). "reconstruido" = lo que habrian dicho las mismas reglas en el pasado con el universo
de hoy: sirve de referencia, pero tiene sesgo de supervivencia y las observaciones se solapan.
Informativo: no cambia ninguna alerta ni recomendacion.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import TICKERS, BENCHMARK  # noqa: E402

log = logging.getLogger("radar.semanal")

RUTA_JSON = "data/semanal.json"
RUTA_LOG = "data/log_semanal.jsonl"
RUTA_EVAL = "data/semanal_eval.json"

MIN_SEMANAS_EMA200 = 200
MIN_SEMANAS_RSI = 30
CERCA_EMA200_PCT = 3.0
PENDIENTE_SEMANAS = 4
RSI_SOBREVENDIDO = 30
RSI_ESTIRADO = 70
MUY_BAJO_SMA14_PCT = 10.0
HORIZONTES = (1, 4)
LISTAS = ("ema200_apoyo", "retroceso_en_tendencia", "sobrevendido", "estirado", "muy_bajo_sma14")


# ------------------------------------------------------------------ descarga
def bajar(simbolo: str) -> pd.Series:
    """Cierres semanales ajustados de 5 años. Lanza excepcion si falla."""
    import yfinance as yf
    h = yf.Ticker(simbolo).history(period="5y", interval="1wk", auto_adjust=True)
    if h.empty:
        raise ValueError("sin datos")
    s = h["Close"].dropna()
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")]


def sacar_semana_incompleta(s: pd.Series, hoy: datetime) -> pd.Series:
    """Yahoo etiqueta la semana con su lunes. Si la ultima vela todavia no cerro (hoy <= su viernes), se descarta."""
    if s.empty:
        return s
    viernes = s.index[-1] + timedelta(days=4)
    if hoy.date() <= viernes.date():
        return s.iloc[:-1]
    return s


# --------------------------------------------------------------- indicadores
def _rsi_wilder(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    gan = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    per = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = gan / per.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    rsi[(per == 0) & (gan > 0)] = 100.0
    return rsi


def indicadores(c: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"close": c})
    df["rsi"] = _rsi_wilder(c) if len(c) >= MIN_SEMANAS_RSI else np.nan
    df["sma14"] = c.rolling(14).mean()
    if len(c) >= MIN_SEMANAS_EMA200:
        ema = c.ewm(span=200, adjust=False, min_periods=MIN_SEMANAS_EMA200).mean()
    else:
        ema = pd.Series(np.nan, index=c.index)
    df["ema200"] = ema
    df["dist_sma14"] = (c / df["sma14"] - 1) * 100
    df["dist_ema200"] = (c / ema - 1) * 100
    df["pend_ema200"] = (ema / ema.shift(PENDIENTE_SEMANAS) - 1) * 100
    return df


def listas_de(fila) -> list:
    """Listas a las que pertenece una fila de indicadores (una semana de un ticker)."""
    out = []
    rsi, de, ds, pe = fila["rsi"], fila["dist_ema200"], fila["dist_sma14"], fila["pend_ema200"]
    if pd.notna(de) and pd.notna(pe) and abs(de) <= CERCA_EMA200_PCT and pe > 0:
        out.append("ema200_apoyo")
    if pd.notna(de) and pd.notna(ds) and pd.notna(rsi) and de > 0 and ds < 0 and rsi < 50:
        out.append("retroceso_en_tendencia")
    if pd.notna(rsi) and rsi <= RSI_SOBREVENDIDO:
        out.append("sobrevendido")
    if pd.notna(rsi) and rsi >= RSI_ESTIRADO:
        out.append("estirado")
    if pd.notna(ds) and ds <= -MUY_BAJO_SMA14_PCT:
        out.append("muy_bajo_sma14")
    return out


# ---------------------------------------------------------------- evaluacion
def _resumen(obs: list) -> dict:
    if not obs:
        return {"n": 0}
    r = np.array([o[0] for o in obs], dtype=float)
    e = np.array([o[1] for o in obs], dtype=float)
    return {"n": int(len(r)), "media_%": round(float(r.mean()), 2), "exceso_vs_spy_%": round(float(e.mean()), 2),
            "positivos_%": round(float((r > 0).mean() * 100), 1)}


def _retornos_adelante(c: pd.Series, bench: pd.Series, i: int, h: int):
    """(retorno %, exceso vs SPY %) del ticker entre la semana i y la i+h; None si no hay datos."""
    if i + h >= len(c):
        return None
    f0, f1 = c.index[i], c.index[i + h]
    b0, b1 = bench.get(f0), bench.get(f1)
    if b0 is None or b1 is None or pd.isna(b0) or pd.isna(b1) or c.iloc[i] <= 0 or b0 <= 0:
        return None
    r = (c.iloc[i + h] / c.iloc[i] - 1) * 100
    rb = (b1 / b0 - 1) * 100
    return float(r), float(r - rb)


def evaluar(ind: dict, bench: pd.Series, fechas_log: dict) -> dict:
    """ind = {ticker: DataFrame}; fechas_log = {fecha_viernes(str): {lista: [tickers]}}."""
    rec = {l: {h: [] for h in HORIZONTES} for l in LISTAS}
    vivo = {l: {h: [] for h in HORIZONTES} for l in LISTAS}
    semanas_rec = set()
    for t, df in ind.items():
        c = df["close"]
        for i in range(MIN_SEMANAS_EMA200, len(df)):
            ls = listas_de(df.iloc[i])
            if not ls:
                continue
            semanas_rec.add(df.index[i])
            for h in HORIZONTES:
                x = _retornos_adelante(c, bench, i, h)
                if x is None:
                    continue
                for l in ls:
                    rec[l][h].append(x)
    for fviernes, listas in fechas_log.items():
        lunes = pd.Timestamp(fviernes) - timedelta(days=4)
        for l, tickers in listas.items():
            if l not in vivo:
                continue
            for t in tickers:
                df = ind.get(t)
                if df is None or lunes not in df.index:
                    continue
                i = df.index.get_loc(lunes)
                for h in HORIZONTES:
                    x = _retornos_adelante(df["close"], bench, i, h)
                    if x is not None:
                        vivo[l][h].append(x)
    fmt = lambda d: {l: {f"{h}s": _resumen(d[l][h]) for h in HORIZONTES} for l in LISTAS}
    return {
        "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vivo": fmt(vivo),
        "reconstruido": fmt(rec),
        "semanas_reconstruidas": len(semanas_rec),
        "aviso": "El reconstruido aplica las mismas reglas a semanas pasadas con el universo de hoy: tiene sesgo de "
                 "supervivencia y observaciones solapadas. Es una referencia, no una promesa. Informativo.",
    }


# --------------------------------------------------------------------- main
def _leer_log() -> dict:
    out = {}
    if os.path.exists(RUTA_LOG):
        with open(RUTA_LOG, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    d = json.loads(linea)
                    out[d["fecha"]] = {l: [x["t"] for x in v] for l, v in d.get("listas", {}).items()}
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    hoy = datetime.now(timezone.utc)
    simbolos = list(dict.fromkeys(list(TICKERS.keys()) + [BENCHMARK]))
    cierres, fallidos = {}, []
    for s in simbolos:
        for intento in (1, 2):
            try:
                cierres[s] = sacar_semana_incompleta(bajar(s), hoy)
                break
            except Exception as e:  # noqa: BLE001
                if intento == 2:
                    fallidos.append({"ticker": s, "motivo": str(e)[:80]})
                else:
                    time.sleep(2)
        time.sleep(0.15)
    if BENCHMARK not in cierres or len(cierres[BENCHMARK]) < 60:
        log.error("Sin benchmark: no se escribe nada.")
        sys.exit(1)
    if len(fallidos) > 0.3 * len(simbolos):
        log.error(f"Demasiados fallidos ({len(fallidos)}): no se escribe nada.")
        sys.exit(1)

    bench = cierres[BENCHMARK]
    ind = {t: indicadores(c) for t, c in cierres.items() if t != BENCHMARK and len(c) >= MIN_SEMANAS_RSI}
    ultimo_lunes = bench.index[-1]
    fecha = (ultimo_lunes + timedelta(days=4)).strftime("%Y-%m-%d")

    tickers_out, listas_hoy = {}, {l: [] for l in LISTAS}
    for t, df in ind.items():
        if df.index[-1] != ultimo_lunes:      # sin la ultima semana cerrada: no entra a las listas de hoy
            continue
        fila = df.iloc[-1]
        r = lambda x, n=2: None if pd.isna(x) else round(float(x), n)
        tickers_out[t] = {"close": r(fila["close"]), "rsi": r(fila["rsi"], 1), "sma14": r(fila["sma14"]),
                          "ema200": r(fila["ema200"]), "dist_sma14": r(fila["dist_sma14"]),
                          "dist_ema200": r(fila["dist_ema200"]), "pend_ema200": r(fila["pend_ema200"]),
                          "semanas": int(len(df))}
        for l in listas_de(fila):
            listas_hoy[l].append(t)
    for l in LISTAS:
        clave = {"ema200_apoyo": lambda t: abs(tickers_out[t]["dist_ema200"]),
                 "retroceso_en_tendencia": lambda t: tickers_out[t]["rsi"],
                 "sobrevendido": lambda t: tickers_out[t]["rsi"],
                 "estirado": lambda t: -tickers_out[t]["rsi"],
                 "muy_bajo_sma14": lambda t: tickers_out[t]["dist_sma14"]}[l]
        listas_hoy[l].sort(key=clave)

    # --- log append-only (una linea por semana cerrada)
    previo = _leer_log()
    if fecha not in previo:
        linea = {"fecha": fecha, "generado_utc": hoy.isoformat(timespec="seconds"),
                 "listas": {l: [{"t": t, "close": tickers_out[t]["close"], "rsi": tickers_out[t]["rsi"],
                                 "dist_ema200": tickers_out[t]["dist_ema200"], "dist_sma14": tickers_out[t]["dist_sma14"]}
                                for t in ts] for l, ts in listas_hoy.items()}}
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False) + "\n")
        previo[fecha] = {l: ts for l, ts in listas_hoy.items()}
        log.info(f"Log: semana {fecha} registrada.")
    else:
        log.info(f"Log: la semana {fecha} ya estaba registrada.")

    salida = {"generado_utc": hoy.isoformat(timespec="seconds"), "fecha_semana": fecha, "benchmark": BENCHMARK,
              "umbrales": {"cerca_ema200_%": CERCA_EMA200_PCT, "rsi_sobrevendido": RSI_SOBREVENDIDO,
                           "rsi_estirado": RSI_ESTIRADO, "muy_bajo_sma14_%": MUY_BAJO_SMA14_PCT, "min_semanas_ema200": MIN_SEMANAS_EMA200},
              "tickers": tickers_out, "listas": listas_hoy, "fallidos": fallidos}
    with open(RUTA_JSON, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, separators=(",", ":"))
    with open(RUTA_EVAL, "w", encoding="utf-8") as f:
        json.dump(evaluar(ind, bench, previo), f, ensure_ascii=False, indent=1)
    log.info(f"Listo: {len(tickers_out)} tickers, listas: { {l: len(v) for l, v in listas_hoy.items()} }, fallidos: {len(fallidos)}")


if __name__ == "__main__":
    main()
