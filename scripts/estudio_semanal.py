"""
Estudio semanal -- ¿que umbrales tienen sustento en los datos? (se corre a mano, solo de lectura)

Motivo (22/10, Victoria): los umbrales de las listas semanales (RSI 30/70, 3% de la EMA200, RSI < 50)
se eligieron a criterio, sin probarlos. Este estudio mide, sobre 10 años de velas semanales, que paso
DESPUES con cada tramo de RSI y de distancia a la SMA14 / EMA200, para que los cortes salgan de los datos.

NO toca el radar, ni la Auditoria, ni las listas vigentes. Escribe:
  data/estudio_semanal.json
  data/estudio_semanal_resumen.md

Metodo:
  * Panel: cada ticker x cada semana con EMA200 semanal disponible. Con 10 años salen ~320 semanas utiles.
  * Retornos adelante a 1, 4 y 8 semanas, y exceso contra SPY (misma fecha).
  * Tramos: RSI (<30, 30-40, 40-50, 50-60, 60-70, >=70), distancia a SMA14 y a EMA200. Se mira todo el
    universo y, aparte, solo los que cierran SOBRE su EMA200 (tendencia alcista de fondo).
  * Linea base: el promedio de TODAS las observaciones del grupo. Un tramo vale si se separa de la base.
  * Significancia: se promedia por semana (para no contar 300 acciones de la misma semana como 300
    pruebas independientes) y se calcula un t-stat con correccion Newey-West por el solapamiento.
    |t| < 2 = indistinguible de ruido.
  * Consistencia: se parte el historial en dos mitades por fecha; un tramo "consistente" tiene el mismo
    signo de exceso en las dos.
  * Tramos con menos de MIN_OBS observaciones o menos de MIN_SEMANAS semanas se marcan "insuficiente".
Limites que el estudio NO resuelve: sesgo de supervivencia (solo estan los tickers que hoy estan en el
universo), cambios de regimen, y que el pasado no garantiza nada. Informativo.

Uso:   python scripts/estudio_semanal.py
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import TICKERS, BENCHMARK  # noqa: E402
import semanal  # noqa: E402  (reusa indicadores y limpieza de la semana incompleta)

log = logging.getLogger("radar.estudio_semanal")

RUTA_JSON = "data/estudio_semanal.json"
RUTA_MD = "data/estudio_semanal_resumen.md"
HORIZONTES = (1, 4, 8)
H_PRINCIPAL = 4
MIN_OBS = 200
MIN_SEMANAS = 40
MIN_OBS_CRUCES, MIN_SEMANAS_CRUCES = 400, 100   # para destacar un cruce hace falta mas muestra que para mostrarlo
T_MIN_CRUCES = 3.0   # se prueban ~42 cruces a la vez: con |t|>=2 se espera que unos 2 pasen solo por azar
RSI_BINS = [(-1, 30, "RSI <30"), (30, 40, "RSI 30-40"), (40, 50, "RSI 40-50"), (50, 60, "RSI 50-60"),
            (60, 70, "RSI 60-70"), (70, 101, "RSI >=70")]
SMA_BINS = [(-1e9, -10, "<-10%"), (-10, -5, "-10 a -5%"), (-5, -2, "-5 a -2%"), (-2, 0, "-2 a 0%"),
            (0, 5, "0 a 5%"), (5, 10, "5 a 10%"), (10, 1e9, ">10%")]
EMA_BINS = [(-1e9, -10, "<-10%"), (-10, -3, "-10 a -3%"), (-3, 3, "-3 a 3%"), (3, 10, "3 a 10%"),
            (10, 25, "10 a 25%"), (25, 1e9, ">25%")]


def bajar_10y(simbolo: str) -> pd.Series:
    import yfinance as yf
    h = yf.Ticker(simbolo).history(period="10y", interval="1wk", auto_adjust=True)
    if h.empty:
        raise ValueError("sin datos")
    s = h["Close"].dropna()
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")]


def newey_west_t(x: np.ndarray, lag: int = 4):
    """t-stat de la media de una serie semanal con correccion Newey-West (maneja el solapamiento)."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 20:
        return None
    m = x.mean()
    e = x - m
    s = (e * e).sum() / n
    for k in range(1, min(lag, n - 1) + 1):
        w = 1 - k / (lag + 1)
        s += 2 * w * (e[k:] * e[:-k]).sum() / n
    if s <= 0:
        return None
    return float(m / np.sqrt(s / n))


def armar_panel(cierres: dict) -> pd.DataFrame:
    bench = cierres[BENCHMARK]
    filas = []
    for t, c in cierres.items():
        if t == BENCHMARK or len(c) < semanal.MIN_SEMANAS_EMA200 + 10:
            continue
        df = semanal.indicadores(c)
        b = bench.reindex(c.index)
        out = df.copy()
        out["ticker"] = t
        for h in HORIZONTES:
            r = (c.shift(-h) / c - 1) * 100
            rb = (b.shift(-h) / b - 1) * 100
            out[f"r{h}"] = r
            out[f"x{h}"] = r - rb
        out["fecha"] = c.index
        filas.append(out.iloc[semanal.MIN_SEMANAS_EMA200:])
    p = pd.concat(filas, ignore_index=True)
    return p.dropna(subset=["rsi", "dist_sma14", "dist_ema200", "x4"])


def _stats(sub: pd.DataFrame, grp: pd.DataFrame, m1) -> dict:
    """Estadisticas de un tramo (sub) contra la base de su grupo (grp). m1 = fecha de corte de las dos mitades."""
    n = len(sub)
    semanas = sub["fecha"].nunique()
    out = {"n": int(n), "semanas": int(semanas)}
    if n < MIN_OBS or semanas < MIN_SEMANAS:
        out["estado"] = "insuficiente"
        return out
    base_mean = float(grp[f"x{H_PRINCIPAL}"].mean())
    d = {}
    for h in HORIZONTES:
        d[f"exceso_{h}s_%"] = round(float(sub[f"x{h}"].dropna().mean()), 2)
        d[f"mediana_{h}s_%"] = round(float(sub[f"r{h}"].dropna().median()), 2)
        d[f"positivos_{h}s_%"] = round(float((sub[f"r{h}"].dropna() > 0).mean() * 100), 1)
    # t-stat de la DIFERENCIA contra la base de cada semana (no contra cero): promedia por semana el tramo,
    # le resta el promedio de todo el grupo esa misma semana, y corrige el solapamiento (Newey-West)
    col = f"x{H_PRINCIPAL}"
    serie = sub.groupby("fecha")[col].mean() - grp.groupby("fecha")[col].mean().reindex(sub["fecha"].unique())
    t = newey_west_t(serie.dropna().values, lag=H_PRINCIPAL)
    d["t_4s"] = None if t is None else round(t, 2)
    d["vs_base_4s_%"] = round(d[f"exceso_{H_PRINCIPAL}s_%"] - base_mean, 2)
    # consistencia: la diferencia contra la base de CADA mitad tiene el mismo signo
    difs = []
    for mask_s, mask_g in ((sub["fecha"] < m1, grp["fecha"] < m1), (sub["fecha"] >= m1, grp["fecha"] >= m1)):
        a, b = sub.loc[mask_s, col].mean(), grp.loc[mask_g, col].mean()
        difs.append(None if pd.isna(a) or pd.isna(b) else float(a - b))
    d["mitad1_vs_base_%"] = None if difs[0] is None else round(difs[0], 2)
    d["mitad2_vs_base_%"] = None if difs[1] is None else round(difs[1], 2)
    d["consistente"] = bool(None not in difs and np.sign(difs[0]) == np.sign(difs[1]) and difs[0] != 0)
    d["estado"] = "ok"
    out.update(d)
    return out


def tabla_1d(p, col, bins, m1):
    res = {}
    for lo, hi, nombre in bins:
        sub = p[(p[col] >= lo) & (p[col] < hi)]
        res[nombre] = _stats(sub, p, m1)
    return res


def tabla_2d(p, m1):
    res = {}
    for rlo, rhi, rn in RSI_BINS:
        for slo, shi, sn in SMA_BINS:
            sub = p[(p["rsi"] >= rlo) & (p["rsi"] < rhi) & (p["dist_sma14"] >= slo) & (p["dist_sma14"] < shi)]
            res[f"{rn} | SMA14 {sn}"] = _stats(sub, p, m1)
    return res


def resumen_md(est: dict) -> str:
    L = [f"# Estudio semanal ({est['generado_utc'][:10]})", "",
         f"Panel: {est['observaciones']} observaciones, {est['tickers']} tickers, {est['semanas']} semanas "
         f"({est['desde']} a {est['hasta']}). Metrica principal: exceso contra SPY a {H_PRINCIPAL} semanas.", "",
         est["aviso"], ""]
    for grupo in ("todo", "sobre_ema200"):
        g = est["grupos"][grupo]
        L += [f"## Grupo: {'todo el universo' if grupo == 'todo' else 'cierra SOBRE su EMA200 semanal'}",
              f"Base (promedio del grupo): exceso {g['base_exceso_4s_%']:+.2f}% a 4 semanas, n={g['n']}.", ""]
        for nombre, tabla in (("RSI semanal", g["rsi"]), ("Distancia a la SMA14", g["dist_sma14"]),
                              ("Distancia a la EMA200", g["dist_ema200"])):
            L += [f"### {nombre}", "| Tramo | n | semanas | exceso 4s | vs base | t vs base (NW) | mitad 1 vs base | mitad 2 vs base | consistente |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for k, v in tabla.items():
                if v.get("estado") != "ok":
                    L.append(f"| {k} | {v['n']} | {v['semanas']} | insuficiente | | | | | |")
                else:
                    L.append(f"| {k} | {v['n']} | {v['semanas']} | {v['exceso_4s_%']:+.2f}% | {v['vs_base_4s_%']:+.2f} | "
                             f"{v['t_4s']} | {v['mitad1_vs_base_%']} | {v['mitad2_vs_base_%']} | {'si' if v['consistente'] else 'no'} |")
            L.append("")
    s = est["grupos"]["sobre_ema200"].get("rsi_x_sma14", {})
    top = sorted([(k, v) for k, v in s.items() if v.get("estado") == "ok" and v.get("consistente") and abs(v.get("t_4s") or 0) >= T_MIN_CRUCES
                  and v["n"] >= MIN_OBS_CRUCES and v["semanas"] >= MIN_SEMANAS_CRUCES],
                 key=lambda kv: -abs(kv[1]["vs_base_4s_%"]))[:10]
    ncel = len(s)
    L += [f"## Cruces RSI x SMA14 (sobre EMA200) que se separan de la base con |t| >= {T_MIN_CRUCES:g} y signo consistente",
          f"Se probaron {ncel} cruces a la vez: con |t| >= 2 se espera que unos {max(1, round(ncel * 0.05))} pasen solo por azar, por eso se exige |t| >= {T_MIN_CRUCES:g}.", ""]
    L += [f"- {k}: exceso {v['exceso_4s_%']:+.2f}% (vs base {v['vs_base_4s_%']:+.2f}), t={v['t_4s']}, n={v['n']}" for k, v in top] or \
         ["- Ninguno: con este panel no hay un cruce que se distinga del ruido de forma consistente."]
    L += ["", "Lectura: un tramo es solo un CANDIDATO a umbral si se separa de la base, tiene |t| alto y es consistente en las "
              "dos mitades. Con datos de puro azar este mismo filtro deja pasar un falso positivo cada varias corridas, asi que un "
              "candidato se confirma midiendolo hacia adelante en vivo (log_semanal) antes de usarlo. Si ninguno aparece, la "
              "conclusion honesta es que ese corte no tiene sustento."]
    return "\n".join(L)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    hoy = datetime.now(timezone.utc)
    simbolos = list(dict.fromkeys(list(TICKERS.keys()) + [BENCHMARK]))
    cierres, fallidos = {}, 0
    for s in simbolos:
        for intento in (1, 2):
            try:
                cierres[s] = semanal.sacar_semana_incompleta(bajar_10y(s), hoy)
                break
            except Exception:  # noqa: BLE001
                if intento == 2:
                    fallidos += 1
                else:
                    time.sleep(2)
        time.sleep(0.15)
    if BENCHMARK not in cierres or fallidos > 0.3 * len(simbolos):
        log.error("Descarga insuficiente: no se escribe nada.")
        sys.exit(1)
    p = armar_panel(cierres)
    log.info(f"Panel: {len(p)} observaciones, {p['ticker'].nunique()} tickers, {p['fecha'].nunique()} semanas")
    fechas = sorted(p["fecha"].unique())
    mitad = fechas[len(fechas) // 2]
    grupos = {}
    for nombre, sub in (("todo", p), ("sobre_ema200", p[p["dist_ema200"] > 0])):
        base = float(sub["x4"].mean())
        grupos[nombre] = {"n": int(len(sub)), "base_exceso_4s_%": round(base, 2),
                          "rsi": tabla_1d(sub, "rsi", RSI_BINS, mitad),
                          "dist_sma14": tabla_1d(sub, "dist_sma14", SMA_BINS, mitad),
                          "dist_ema200": tabla_1d(sub, "dist_ema200", EMA_BINS, mitad)}
        if nombre == "sobre_ema200":
            grupos[nombre]["rsi_x_sma14"] = tabla_2d(sub, mitad)
    est = {"generado_utc": hoy.isoformat(timespec="seconds"), "observaciones": int(len(p)), "tickers": int(p["ticker"].nunique()),
           "semanas": int(len(fechas)), "desde": str(pd.Timestamp(fechas[0]).date()), "hasta": str(pd.Timestamp(fechas[-1]).date()),
           "mitad": str(pd.Timestamp(mitad).date()), "grupos": grupos,
           "aviso": "Sesgo de supervivencia (universo de hoy), solapamiento de retornos y cambios de regimen: es evidencia "
                    "parcial, no una promesa. Informativo."}
    with open(RUTA_JSON, "w", encoding="utf-8") as f:
        json.dump(est, f, ensure_ascii=False, indent=1)
    with open(RUTA_MD, "w", encoding="utf-8") as f:
        f.write(resumen_md(est))
    log.info("Listo.")


if __name__ == "__main__":
    main()
