"""
Estudio 2 -- ANTICIPAR el Gap alcista (pedido de Victoria, 8/10): ver el gap
ANTES de que se dé, sin importar si después sigue subiendo.

Aparte del radar (ADITIVO): no toca señales ni Auditoría. Crea solo
data/estudio_gap_previa.json y data/estudio_gap_previa_resumen.md.

Objetivo medido: "mañana (la rueda siguiente) este papel hace un Gap alcista"
(regla del radar, ver estudio_gap.py), entre los días en que ya está en macrotendencia.

Qué prueba, todo con datos disponibles ANTES del gap:
  1. BALANCES: ¿cuántos gaps ocurren justo después de presentar balance? (fechas de
     Yahoo; si no se consiguen para un papel, queda "sin dato" y se informa la cobertura).
  2. SECTOR: ¿el gap de hoy/ayer en otros papeles del mismo sector anticipa gaps?
  3. Las características técnicas del estudio 1 (compresión, volumen seco, distancia al
     máximo, etc.).
  4. PUNTAJE combinado y LISTA DIARIA: cada día se ordenan los papeles de volatilidad
     baja/media por puntaje y se mira cuántos de los 5 primeros hicieron gap al día
     siguiente, contra la tasa normal. El puntaje se arma con la primera parte de la
     historia y se prueba SOLO en la última (no se mira hacia atrás para acomodarlo).
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
import estudio_gap as eg  # reutiliza la regla, las características y la descarga

log = logging.getLogger("estudio.gap.previa")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

TOP_K = 5
FEATS_TECNICAS = list(eg.FEATURES.keys())
RUTA_SALIDA = "data/estudio_gap_previa.json"
RUTA_RESUMEN = "data/estudio_gap_previa_resumen.md"


def _earnings(simbolo: str, desde: pd.Timestamp):
    """Lista ordenada de fechas de balance (sin hora) o None si Yahoo no las da."""
    import yfinance as yf
    try:
        d = yf.Ticker(simbolo).get_earnings_dates(limit=40)
    except Exception:
        return None
    if d is None or len(d) == 0:
        return None
    idx = pd.DatetimeIndex(d.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    idx = idx.normalize().unique().sort_values()
    return idx[idx >= desde - pd.Timedelta(days=10)]


def construir_panel(series: dict, spy_close: pd.Series, sectores: dict, earn: dict) -> pd.DataFrame:
    filas = []
    for t, df in series.items():
        r = eg.calcular_ticker(df, spy_close)
        r["ticker"] = t
        r["sector"] = sectores.get(t, "otro")
        v = float(r["vol60_anual"].median()) if r["vol60_anual"].notna().any() else None
        r["grupo_vol"] = eg.grupo_vol(v)
        # Objetivo: gap MAÑANA, solo si hoy ya hay macrotendencia (condición del radar)
        r["gap_manana"] = r["gap"].shift(-1).astype(float)
        r.loc[r.index[-1:], "gap_manana"] = np.nan
        # el gap de mañana exige que HOY el cierre esté sobre su SMA200
        r.loc[~(r["dist_sma200_pct"] > 0), "gap_manana"] = np.nan
        # Balance: ¿hay balance hoy (después del cierre) o mañana (antes de la apertura)?
        e = earn.get(t)
        if e is None or len(e) == 0:
            r["balance_cerca"] = np.nan
        else:
            hoy = pd.DatetimeIndex(r.index).normalize()
            pos = e.searchsorted(hoy, side="left")
            hay = pos < len(e)
            prox = e[np.minimum(pos, len(e) - 1)]
            dias = np.asarray((prox - hoy).days, dtype=float)
            r["balance_cerca"] = (hay & (dias <= 1)).astype(float)
        filas.append(r)
    panel = pd.concat(filas)
    panel.index.name = "fecha"
    # Sector: cuántos OTROS papeles del sector hicieron gap hoy / en los últimos 3 días
    g = panel.reset_index().pivot_table(index="fecha", columns="ticker", values="gap", aggfunc="max").fillna(0)
    sec = pd.Series({t: sectores.get(t, "otro") for t in g.columns})
    gh, g3 = {}, {}
    for s in sec.unique():
        cols = sec[sec == s].index
        tot = g[cols].sum(axis=1)
        tot3 = tot.rolling(3, min_periods=1).sum()
        gh[s], g3[s] = tot, tot3
    panel = panel.reset_index()
    panel["pares_gap_hoy"] = [gh[s].get(f, 0) - gp for s, f, gp in zip(panel["sector"], panel["fecha"], panel["gap"].astype(float))]
    panel["pares_gap_3d"] = [g3[s].get(f, 0) - gp for s, f, gp in zip(panel["sector"], panel["fecha"], panel["gap"].astype(float))]
    return panel.set_index("fecha")


def _cortes(x: pd.Series):
    x = x.dropna()
    return np.unique(np.nanquantile(x, [0.2, 0.4, 0.6, 0.8])) if len(x) > 500 else None


def entrenar_puntaje(ent: pd.DataFrame, feats_num: list, flags: list):
    base = ent["gap_manana"].mean()
    modelo = {"base": float(base), "num": {}, "flags": {}}
    for f in feats_num:
        c = _cortes(ent[f])
        if c is None:
            continue
        bins = np.digitize(ent[f].values, c)
        logs = []
        for q in range(len(c) + 1):
            m = (bins == q) & ent[f].notna().values
            n = int(m.sum())
            tasa = (ent["gap_manana"].values[m].sum() + base * 50) / (n + 50)  # suavizado
            logs.append(float(np.log(tasa / base)))
        modelo["num"][f] = {"cortes": [float(x) for x in c], "log_lift": logs}
    for f in flags:
        v = ent[f]
        ok = v.notna()
        if ok.sum() < 500:
            continue
        d = {}
        for val in (0.0, 1.0):
            m = (v == val).values
            n = int(m.sum())
            tasa = (ent["gap_manana"].values[m].sum() + base * 50) / (n + 50)
            d[str(int(val))] = float(np.log(tasa / base))
        modelo["flags"][f] = d
    return modelo


def puntuar(d: pd.DataFrame, modelo: dict) -> pd.Series:
    s = np.zeros(len(d))
    for f, m in modelo["num"].items():
        bins = np.digitize(d[f].values, m["cortes"])
        s += np.where(d[f].isna().values, 0.0, np.asarray(m["log_lift"])[bins])
    for f, m in modelo["flags"].items():
        v = d[f].values
        s += np.where(np.isnan(v), 0.0, np.where(v == 1, m["1"], m["0"]))
    return pd.Series(s, index=d.index)


def lista_diaria(d: pd.DataFrame, score: pd.Series, k: int = TOP_K) -> dict:
    d = d.assign(score=score)
    d = d[d["gap_manana"].notna() & d["grupo_vol"].isin(["baja", "media"])]
    elegidos = d.sort_values("score", ascending=False).groupby(level=0).head(k)
    base = d["gap_manana"].mean() * 100
    hit = elegidos["gap_manana"].mean() * 100
    return {"k_por_dia": k, "dias": int(d.index.nunique()), "elegidos": int(len(elegidos)),
            "acierto_lista_pct": round(float(hit), 2), "tasa_normal_pct": round(float(base), 2),
            "lift": round(float(hit / base), 2) if base > 0 else None,
            "gaps_atrapados_pct": round(float(elegidos["gap_manana"].sum() / d["gap_manana"].sum() * 100), 1) if d["gap_manana"].sum() > 0 else None}


def correr(series, spy_close, sectores, earn) -> dict:
    panel = construir_panel(series, spy_close, sectores, earn)
    panel = panel[panel["close"].notna()]
    fechas = np.sort(panel.index.unique())
    corte = pd.Timestamp(fechas[int(len(fechas) * eg.FRACCION_ENTRENAMIENTO)])
    obj = panel[panel["gap_manana"].notna()]
    ent, pru = obj[obj.index < corte], obj[obj.index >= corte]
    out = {"generado_utc": datetime.now(timezone.utc).isoformat(), "objetivo": "gap alcista (regla del radar) en la rueda siguiente, entre días con macrotendencia",
           "corte_entrenamiento_prueba": str(corte.date()), "tickers": int(panel["ticker"].nunique()),
           "tasa_base_prueba_pct": round(float(pru["gap_manana"].mean() * 100), 2)}
    # 1) Balances
    cob = panel.groupby("ticker")["balance_cerca"].apply(lambda s: s.notna().any())
    out["balances_cobertura"] = {"papeles_con_fechas": int(cob.sum()), "papeles_sin_fechas": int((~cob).sum())}
    # % de gaps que ocurrieron en la rueda siguiente a una marca de balance (hoy después del cierre o mañana antes de abrir)
    prev = panel.groupby("ticker")["balance_cerca"].shift(1)
    ok = panel.assign(prev_balance=prev)
    for g, sel in (("baja_o_media", ["baja", "media"]), ("alta", ["alta"])):
        e = ok[(ok["gap"]) & ok["prev_balance"].notna() & ok["grupo_vol"].isin(sel)]
        base_b = ok[ok["prev_balance"].notna() & ok["macro_ok"] & ok["grupo_vol"].isin(sel)]["prev_balance"].mean()
        out.setdefault("balances", {})[g] = {"gaps": int(len(e)),
            "pct_de_gaps_con_balance_cerca": round(float(e["prev_balance"].mean() * 100), 1) if len(e) else None,
            "pct_de_dias_normales_con_balance_cerca": round(float(base_b * 100), 1) if pd.notna(base_b) else None}
    # 2) Tabla de lift de cada característica (como en el estudio 1, pero objetivo = mañana)
    feats_num = FEATS_TECNICAS + ["pares_gap_hoy", "pares_gap_3d"]
    flags = ["balance_cerca"]
    bm = obj[obj["grupo_vol"].isin(["baja", "media"])]
    bent, bpru = bm[bm.index < corte], bm[bm.index >= corte]
    modelo = entrenar_puntaje(bent, feats_num, flags)
    out["lift_por_caracteristica"] = {}
    for f in feats_num + flags:
        filas = []
        for nombre, d in (("entrenamiento", bent), ("prueba", bpru)):
            base = d["gap_manana"].mean() * 100
            if f in flags:
                for val in (1.0,):
                    m = (d[f] == val).values
                    if m.sum() >= 30:
                        t = d["gap_manana"].values[m].mean() * 100
                        filas.append({"muestra": nombre, "grupo": "con balance hoy o mañana", "n_dias": int(m.sum()), "tasa_pct": round(float(t), 2), "base_pct": round(float(base), 2), "lift": round(float(t / base), 2) if base else None})
            elif f in modelo["num"]:
                bins = np.digitize(d[f].values, modelo["num"][f]["cortes"])
                for q in range(len(modelo["num"][f]["cortes"]) + 1):
                    m = (bins == q) & d[f].notna().values
                    if m.sum() >= 200:
                        t = d["gap_manana"].values[m].mean() * 100
                        filas.append({"muestra": nombre, "quintil": q + 1, "n_dias": int(m.sum()), "tasa_pct": round(float(t), 2), "base_pct": round(float(base), 2), "lift": round(float(t / base), 2) if base else None})
        out["lift_por_caracteristica"][f] = filas
    # 3) Lista diaria con puntaje (entrenado en la primera parte, probado en la última)
    sc = puntuar(bpru, modelo)
    out["lista_diaria_prueba"] = {f"top{k}": lista_diaria(bpru, sc, k) for k in (3, 5, 10)}
    sc_ent = puntuar(bent, modelo)
    out["lista_diaria_entrenamiento"] = {"top5": lista_diaria(bent, sc_ent, 5)}
    # Lista de HOY (último día): informativa
    ult = panel.index.max()
    hoy = panel.loc[[ult]]
    hoy = hoy[(hoy["dist_sma200_pct"] > 0) & hoy["grupo_vol"].isin(["baja", "media"])]
    if len(hoy):
        sh = puntuar(hoy, modelo)
        top = hoy.assign(score=sh).sort_values("score", ascending=False).head(15)
        out["lista_hoy"] = {"fecha": str(pd.Timestamp(ult).date()),
                            "aviso": "Lista informativa para ver cómo se comportaría el sistema; la tasa de acierto histórica está arriba.",
                            "papeles": [{"ticker": r["ticker"], "sector": r["sector"], "grupo_vol": r["grupo_vol"], "puntaje": round(float(r["score"]), 2),
                                         "balance_cerca": None if pd.isna(r["balance_cerca"]) else bool(r["balance_cerca"])} for _, r in top.iterrows()]}
    return out


def resumen_md(res: dict) -> str:
    L = ["# Estudio 2 -- anticipar el Gap alcista", "", f"Generado: {res['generado_utc'][:16]} UTC. Objetivo: {res['objetivo']}.",
         f"Entrenamiento hasta {res['corte_entrenamiento_prueba']}; prueba después. Tasa normal en la prueba: {res['tasa_base_prueba_pct']}% por papel y día.", ""]
    L.append("## Balances")
    L.append(f"Cobertura de fechas de balance: {res['balances_cobertura']}")
    for g, d in res.get("balances", {}).items():
        L.append(f"- {g}: {d['gaps']} gaps; {d['pct_de_gaps_con_balance_cerca']}% ocurrieron justo después de un balance, contra {d['pct_de_dias_normales_con_balance_cerca']}% de los días normales.")
    L.append("")
    L.append("## Lista diaria con puntaje (parte de PRUEBA, volatilidad baja/media)")
    for k, d in res["lista_diaria_prueba"].items():
        L.append(f"- {k}: acierto {d['acierto_lista_pct']}% contra {d['tasa_normal_pct']}% normal (lift {d['lift']}); atrapa {d['gaps_atrapados_pct']}% de todos los gaps.")
    L.append("")
    L.append("## Lista de hoy")
    for p in res.get("lista_hoy", {}).get("papeles", [])[:10]:
        L.append(f"- {p['ticker']} ({p['sector']}, vol {p['grupo_vol']}) puntaje {p['puntaje']} balance cerca: {p['balance_cerca']}")
    return "\n".join(L)


def main():
    try:
        import config
        sectores = dict(config.TICKERS)
    except Exception as e:
        log.warning(f"No se pudo leer config.TICKERS ({e}): sin dato de sector")
        sectores = {}
    tickers = eg._universo()
    if not tickers:
        log.error("No hay lista de CEDEARs -- se aborta")
        sys.exit(1)
    spy = eg._bajar(eg.BENCHMARK)
    if spy is None:
        log.error("No se pudo bajar SPY -- se aborta")
        sys.exit(1)
    series, earn = {}, {}
    for t in tickers:
        if t == eg.BENCHMARK:
            continue
        try:
            d = eg._bajar(t)
        except Exception as e:
            log.warning(f"{t}: {e}")
            d = None
        if d is None:
            continue
        series[t] = d
        earn[t] = _earnings(t, d.index[0])
        time.sleep(0.3)
    log.info(f"{len(series)} papeles; con fechas de balance: {sum(1 for v in earn.values() if v is not None and len(v))}")
    res = correr(series, spy["Close"], sectores, earn)
    os.makedirs("data", exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(RUTA_RESUMEN, "w", encoding="utf-8") as f:
        f.write(resumen_md(res))
    log.info(f"Guardado {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
