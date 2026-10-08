"""
Estudio 4 -- ¿"EXTENDIDO" o "CERCA DE ZONA"? Probar con la historia los criterios que se usan
en las revisiones diarias (pedido de Victoria, 8/10: "otros estudios que ayuden").

Aparte del radar (ADITIVO): no toca señales ni Auditoría. Crea solo
data/estudio_extension.json y data/estudio_extension_resumen.md.

Para TODOS los días de TODOS los CEDEARs (con macrotendencia: cierre sobre su SMA200) se
mide qué pasó después (5, 10 y 20 ruedas; contra SPY; y la peor caída de las 10 ruedas
siguientes) según cómo estaba el papel ese día:
  * Etiqueta de la revisión diaria:
      'extendido'     : más de 15% sobre la SMA50  o  RSI semanal > 75
      'cerca de zona' : a 3% o menos de la SMA20  y  menos de 10% sobre la SMA50
      'neutral'       : el resto
  * Por tramos: distancia a la SMA50, a la SMA20, RSI diario, RSI semanal.
  * Por tipo de mercado: SPY sobre o bajo su SMA200.
Se informa por volatilidad (baja o media / alta) y por mitad de la historia
(primera y segunda) para ver si el resultado se sostiene.

Limitaciones: universo de CEDEARs de hoy (sesgo de supervivencia); los días se superponen
(un mismo movimiento aparece en varias ruedas seguidas), así que los porcentajes son
orientativos; solo daily. No promete nada.
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
import estudio_gap as eg

log = logging.getLogger("estudio.extension")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
RUTA_SALIDA = "data/estudio_extension.json"
RUTA_RESUMEN = "data/estudio_extension_resumen.md"
HORIZ = (5, 10, 20)


def _rsi_semanal(c: pd.Series) -> pd.Series:
    w = c.resample("W-FRI").last().dropna()
    rs = eg._rsi(w)
    return rs.reindex(c.index, method="ffill")  # valor de la última semana cerrada o en curso


def panel_ticker(df: pd.DataFrame, spy_close: pd.Series) -> pd.DataFrame:
    r = eg.calcular_ticker(df, spy_close)
    c = df["Close"]
    p = pd.DataFrame(index=df.index)
    p["dist_sma50"] = r["dist_sma50_pct"]
    sma20 = c.rolling(20).mean()
    p["dist_sma20"] = (c / sma20 - 1) * 100
    p["rsi_d"] = r["rsi14"]
    p["rsi_w"] = _rsi_semanal(c)
    p["macro"] = r["dist_sma200_pct"] > 0
    p["spy_ok"] = r["spy_sobre_sma200"]
    for n in HORIZ:
        p[f"fwd{n}"] = r[f"fwd{n}"]
        p[f"alpha{n}"] = r[f"alpha{n}"]
    p["peor10"] = r["peor_caida10"]
    p["vol"] = float(r["vol60_anual"].median()) if r["vol60_anual"].notna().any() else np.nan
    p["grupo"] = eg.grupo_vol(p["vol"].iloc[0] if len(p) else None)
    ext = (p["dist_sma50"] > 15) | (p["rsi_w"] > 75)
    cerca = (p["dist_sma20"].abs() <= 3) & (p["dist_sma50"] < 10)
    p["etiqueta"] = np.where(ext, "extendido", np.where(cerca, "cerca de zona", "neutral"))
    return p


def tramo(s: pd.Series, cortes: list, nombres: list) -> pd.Series:
    return pd.cut(s, bins=[-np.inf] + cortes + [np.inf], labels=nombres)


def stats(d: pd.DataFrame) -> dict:
    out = {"n": int(len(d))}
    for n in HORIZ:
        x = d[f"fwd{n}"].dropna()
        a = d[f"alpha{n}"].dropna()
        if len(x) >= 30:
            out[f"fwd{n}"] = {"mediana": round(float(x.median()), 2), "media": round(float(x.mean()), 2), "pct_positivos": round(float((x > 0).mean() * 100), 1),
                              "p10": round(float(x.quantile(0.10)), 2), "alpha_mediana": round(float(a.median()), 2) if len(a) else None}
    pk = d["peor10"].dropna()
    if len(pk) >= 30:
        out["peor_caida10_mediana"] = round(float(pk.median()), 2)
    return out


def correr(series: dict, spy_close: pd.Series) -> dict:
    ps = []
    for t, d in series.items():
        try:
            p = panel_ticker(d, spy_close)
            p["ticker"] = t
            ps.append(p)
        except Exception as e:
            log.warning(f"{t}: {e}")
    if not ps:
        raise RuntimeError("Sin datos")
    P = pd.concat(ps)
    P = P[P["macro"] & P["dist_sma50"].notna() & P["rsi_w"].notna() & P["fwd10"].notna()]
    fechas = np.sort(P.index.unique())
    corte = pd.Timestamp(fechas[int(len(fechas) * 0.5)])
    P["mitad"] = np.where(P.index < corte, "primera", "segunda")
    P["tr_sma50"] = tramo(P["dist_sma50"], [0, 5, 10, 15, 25], ["bajo la SMA50", "0 a 5%", "5 a 10%", "10 a 15%", "15 a 25%", "más de 25%"])
    P["tr_sma20"] = tramo(P["dist_sma20"], [-5, -2, 2, 5, 10], ["más de 5% abajo", "-5 a -2%", "-2 a +2%", "+2 a +5%", "+5 a +10%", "más de 10% arriba"])
    P["tr_rsid"] = tramo(P["rsi_d"], [40, 50, 60, 70, 80], ["<40", "40-50", "50-60", "60-70", "70-80", ">80"])
    P["tr_rsiw"] = tramo(P["rsi_w"], [40, 50, 60, 70, 75], ["<40", "40-50", "50-60", "60-70", "70-75", ">75"])
    grupos = {"baja_o_media": ["baja", "media"], "alta": ["alta"]}
    res = {"generado_utc": datetime.now(timezone.utc).isoformat(), "dias_papel": int(len(P)), "tickers": int(P["ticker"].nunique()),
           "corte_mitades": str(corte.date()), "por_grupo": {}}
    for g, sel in grupos.items():
        d = P[P["grupo"].isin(sel)]
        R = {"base": stats(d), "etiqueta": {}, "etiqueta_por_mitad": {}, "tramos": {}, "mercado": {}}
        for e, x in d.groupby("etiqueta"):
            R["etiqueta"][e] = stats(x)
            R["etiqueta_por_mitad"][e] = {m: stats(y) for m, y in x.groupby("mitad")}
        for nombre, col in (("dist_sma50", "tr_sma50"), ("dist_sma20", "tr_sma20"), ("rsi_diario", "tr_rsid"), ("rsi_semanal", "tr_rsiw")):
            R["tramos"][nombre] = {str(k): stats(x) for k, x in d.groupby(col, observed=True)}
        for k, x in d.groupby("spy_ok"):
            R["mercado"]["SPY sobre su SMA200" if k else "SPY bajo su SMA200"] = {e: stats(y) for e, y in x.groupby("etiqueta")}
        res["por_grupo"][g] = R
    return res


def resumen_md(res: dict) -> str:
    L = ["# Estudio 4 -- extendido vs. cerca de zona", "", f"Generado: {res['generado_utc'][:16]} UTC. Días-papel: {res['dias_papel']}, papeles: {res['tickers']}.", ""]
    R = res["por_grupo"]["baja_o_media"]
    L.append("## Etiqueta de la revisión diaria (volatilidad baja o media)")
    L.append(f"- Base (todos los días): {R['base'].get('fwd10')}")
    for e, d in R["etiqueta"].items():
        L.append(f"- {e}: n={d['n']}, +10 ruedas {d.get('fwd10')}, peor caída 10 ruedas {d.get('peor_caida10_mediana')}")
    L.append("")
    L.append("## ¿Se sostiene en ambas mitades? (+10 ruedas, mediana)")
    for e, m in R["etiqueta_por_mitad"].items():
        L.append(f"- {e}: " + "; ".join(f"{k}: {v.get('fwd10', {}).get('mediana')}%" for k, v in m.items()))
    return "\n".join(L)


def main():
    tickers = eg._universo()
    if not tickers:
        log.error("No hay lista de CEDEARs -- se aborta")
        sys.exit(1)
    spy = eg._bajar(eg.BENCHMARK)
    if spy is None:
        log.error("No se pudo bajar SPY -- se aborta")
        sys.exit(1)
    series = {}
    for t in tickers:
        if t == eg.BENCHMARK:
            continue
        try:
            d = eg._bajar(t)
        except Exception as e:
            log.warning(f"{t}: {e}")
            d = None
        if d is not None:
            series[t] = d
        time.sleep(0.2)
    log.info(f"{len(series)} papeles bajados")
    res = correr(series, spy["Close"])
    os.makedirs("data", exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(RUTA_RESUMEN, "w", encoding="utf-8") as f:
        f.write(resumen_md(res))
    log.info(f"Guardado {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
