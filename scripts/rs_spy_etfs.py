"""
Cuadrante de ETFs "contra el SPY" (estilo Warren Bife, pedido de Victoria 9/10/2026).

A diferencia del cuadrante por ranking (que ubica a cada activo entre TODO el universo, de 0 a 100),
este mide cada ETF directamente contra el SPY, como un grafico de rotacion relativa (RRG):

  RS        = precio del ETF / precio del SPY                    (semanal, cierre de la semana)
  Fuerza    = 100 * RS / promedio de RS de las ultimas N semanas  - 100   [en %, 0 = igual que su promedio contra el SPY]
  Aceleracion = 100 * Ratio_hoy / Ratio_hace K semanas - 100              [en %, positivo = mejorando]

Cuadrantes: Fuerza>0 y Aceleracion>0 = Lider; Fuerza>0 y Aceleracion<0 = Debilitandose;
            Fuerza<0 y Aceleracion<0 = Rezagado; Fuerza<0 y Aceleracion>0 = Mejorando.

Es 100% aditivo: lee data/ultimo.json (solo para saber cuales son los ETFs) y escribe
data/rs_spy_etfs.json. No toca ningun calculo, alerta, ranking ni log existente.
"""
import json
import logging
import os
from datetime import datetime, timezone

import pandas as pd

log = logging.getLogger("radar.rs_spy_etfs")

N_SEMANAS = 10      # ventana del promedio de RS  (version "Largo")
K_SEMANAS = 4       # ventana de la aceleracion    (version "Largo")
N_CORTO = 5         # version "Corto" (se parece mas a la de Warren, 10/10): promedio de 5 semanas
K_CORTO = 2         # y aceleracion de 2 semanas
PUNTOS = 16         # semanas de recorrido que se guardan
RUTA_SALIDA = "data/rs_spy_etfs.json"


def etfs_del_universo(ruta="data/ultimo.json"):
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)
    return sorted({x["Ticker"] for x in d.get("ranking", []) if x.get("Sector") == "ETF" and x["Ticker"] != "SPY"})


def semanal(df):
    """Cierre semanal usando el ultimo dia real de cada semana (la ultima semana puede estar a medias)."""
    df = df.dropna(how="all").sort_index()
    idx = pd.Series(df.index, index=df.index)
    ultimos = idx.groupby(df.index.to_period("W-FRI")).last()
    return df.loc[ultimos.values]


def calcular(precios, etfs, n=None, k=None):
    """precios: dict ticker -> Series de cierres. Devuelve dict listo para guardar."""
    n = n or N_SEMANAS
    k = k or K_SEMANAS
    if "SPY" not in precios:
        raise ValueError("falta SPY")
    cols = {t: precios[t] for t in ["SPY"] + [e for e in etfs if e in precios]}
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index).tz_localize(None) if getattr(df.index, "tz", None) is not None else pd.to_datetime(df.index)
    w = semanal(df.ffill())
    out = {}
    for t in w.columns:
        if t == "SPY":
            continue
        rs = (w[t] / w["SPY"]).dropna()
        ratio = 100 * rs / rs.rolling(n).mean()
        mom = 100 * ratio / ratio.shift(k)
        pts = pd.DataFrame({"x": ratio - 100, "y": mom - 100}).dropna().tail(PUNTOS)
        if len(pts) < 2:
            continue
        out[t] = [{"fecha": str(i)[:10], "x": round(float(r.x), 2), "y": round(float(r.y), 2)} for i, r in pts.iterrows()]
    return {"generado_utc": datetime.now(timezone.utc).isoformat(),
            "fecha_ultimo_cierre": str(w.index[-1])[:10],
            "params": {"semanas_promedio": n, "semanas_aceleracion": k},
            "etfs": out}


def correr():
    from top30_retorno import bajar_precios
    etfs = etfs_del_universo()
    precios = bajar_precios(etfs + ["SPY"], periodo="2y")
    res = calcular(precios, etfs)
    c = calcular(precios, etfs, N_CORTO, K_CORTO)
    res["corto"] = {"params": c["params"], "etfs": c["etfs"]}
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    log.info(f"ETFs medidos contra el SPY: {len(res['etfs'])} de {len(etfs)}")
    return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
