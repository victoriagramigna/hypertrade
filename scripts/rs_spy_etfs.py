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
N_CORTO = 6         # version "Corto" (10/10: la combinacion 6-2 fue la que coincidio con los 11 cuadrantes de la captura de Warren; antes 5-2)
K_CORTO = 2         # y aceleracion de 2 semanas
PUNTOS = 16         # semanas de recorrido que se guardan
RUTA_SALIDA = "data/rs_spy_etfs.json"
RUTA_LOG = "data/log_rs_spy_etfs.jsonl"          # bitacora (solo se agrega, nunca se reescribe)
RUTA_EVAL = "data/rs_spy_etfs_eval.json"
RUTA_VENTANAS = "data/rs_spy_etfs_ventanas.json"   # prueba de ventanas (solo para ajustar; no lo usa la app)
HORIZONTES = (1, 2, 4)                            # semanas hacia adelante para medir


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
    cierre = {"fecha": str(w.index[-1])[:10], "SPY": round(float(w["SPY"].iloc[-1]), 4)}
    for t in out:
        cierre[t] = round(float(w[t].iloc[-1]), 4)
    return {"cierre_semana": cierre, "generado_utc": datetime.now(timezone.utc).isoformat(),
            "fecha_ultimo_cierre": str(w.index[-1])[:10],
            "params": {"semanas_promedio": n, "semanas_aceleracion": k},
            "etfs": out}


def cuadrante(x, y):
    return "Líder" if x >= 0 and y >= 0 else "Debilitándose" if x >= 0 else "Mejorando" if y >= 0 else "Rezagado"


def leer_log(ruta=RUTA_LOG):
    if not os.path.exists(ruta):
        return []
    out = []
    with open(ruta, encoding="utf-8") as f:
        for l in f:
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


def registrar_semana(largo, corto, ruta=RUTA_LOG):
    """Anota (solo agrega) el cuadrante de cada ETF en las dos versiones, al cierre de una semana COMPLETA
    (se anota cuando el ultimo cierre es viernes; un viernes feriado se saltea). No se pisa nada."""
    cs = largo.get("cierre_semana") or {}
    fecha = cs.get("fecha")
    if not fecha or datetime.strptime(fecha, "%Y-%m-%d").weekday() != 4:
        return 0
    ya = {e.get("id") for e in leer_log(ruta)}
    nuevos = []
    for t, pl in largo["etfs"].items():
        pc = (corto["etfs"] or {}).get(t)
        if not pc or pl[-1]["fecha"] != fecha or pc[-1]["fecha"] != fecha:
            continue
        i = f"RSE-{t}-{fecha}" if (N_CORTO, K_CORTO) == (5, 2) else f"RSE-{t}-{fecha}-c{N_CORTO}{K_CORTO}"
        if i in ya:
            continue
        a, b = pl[-1], pc[-1]
        nuevos.append({"evento": "semana", "id": i, "fecha": fecha, "ticker": t,
                       "largo": {"x": a["x"], "y": a["y"], "cuadrante": cuadrante(a["x"], a["y"])},
                       "corto": {"x": b["x"], "y": b["y"], "cuadrante": cuadrante(b["x"], b["y"])},
                       "precio_etf": cs.get(t), "precio_spy": cs.get("SPY"),
                       "ventana_corto": f"{N_CORTO}-{K_CORTO}",
                       "registrado": datetime.now(timezone.utc).isoformat()})
    if nuevos:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            for e in nuevos:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(nuevos)


def evaluar(eventos):
    """Exceso (%) del ETF contra el SPY 1/2/4 semanas DESPUES de cada anotacion, agrupado por cuadrante de cada version
    y por si las dos versiones coincidian o no. Solo usa la propia bitacora (sin bajar nada)."""
    # una sola anotacion por (ETF, semana): la mas reciente. El Largo no cambia entre anotaciones; el Corto solo
    # se cuenta con la ventana vigente (las anotaciones viejas sin campo "ventana_corto" son 5-2).
    unicos = {}
    for e in sorted((x for x in eventos if x.get("evento") == "semana"), key=lambda x: x.get("registrado", "")):
        unicos[(e["ticker"], e["fecha"])] = e
    por_t = {}
    for e in unicos.values():
        if e.get("precio_etf") and e.get("precio_spy"):
            por_t.setdefault(e["ticker"], []).append(e)
    vigente = f"{N_CORTO}-{K_CORTO}"
    filas = []
    for t, ev in por_t.items():
        ev.sort(key=lambda e: e["fecha"])
        for e in ev:
            d0 = datetime.strptime(e["fecha"], "%Y-%m-%d")
            ex = {}
            for h in HORIZONTES:
                for f in ev:
                    dd = (datetime.strptime(f["fecha"], "%Y-%m-%d") - d0).days
                    if abs(dd - 7 * h) <= 3:
                        ex[h] = 100 * ((f["precio_etf"] / e["precio_etf"]) / (f["precio_spy"] / e["precio_spy"]) - 1)
                        break
            filas.append((e, ex))
    def resumen(sel):
        r = {"n": len(sel)}
        for h in HORIZONTES:
            v = [ex[h] for _, ex in sel if h in ex]
            v_s = sorted(v)
            r[f"h{h}"] = ({"n": len(v), "exceso_medio": round(sum(v) / len(v), 2),
                           "exceso_mediano": round(v_s[len(v_s) // 2], 2),
                           "pct_le_gana": round(100 * sum(1 for x in v if x > 0) / len(v))} if v else None)
        return r
    grupos = {}
    vig = [(e, ex) for e, ex in filas if e.get("ventana_corto", "5-2") == vigente]
    for ver in ("largo", "corto"):
        base = filas if ver == "largo" else vig
        for q in ("Líder", "Mejorando", "Debilitándose", "Rezagado"):
            grupos[f"{ver}:{q}"] = resumen([(e, ex) for e, ex in base if e[ver]["cuadrante"] == q])
    grupos["acuerdo:coinciden"] = resumen([(e, ex) for e, ex in vig if e["largo"]["cuadrante"] == e["corto"]["cuadrante"]])
    grupos["acuerdo:difieren"] = resumen([(e, ex) for e, ex in vig if e["largo"]["cuadrante"] != e["corto"]["cuadrante"]])
    semanas = sorted({e["fecha"] for e, _ in filas})
    return {"generado_utc": datetime.now(timezone.utc).isoformat(), "semanas_registradas": len(semanas),
            "primera": semanas[0] if semanas else None, "ultima": semanas[-1] if semanas else None,
            "registros": len(filas), "grupos": grupos}


def probar_ventanas(precios, etfs, ns=(4, 5, 6, 7, 8, 10), ks=(1, 2, 3, 4)):
    """Ultimo punto (fuerza, aceleracion) de cada ETF para varias combinaciones de ventanas.
    Sirve para elegir la que mas se parece a una referencia externa; no se usa en la app."""
    out = {}
    for n in ns:
        for k in ks:
            r = calcular(precios, etfs, n, k)
            out[f"{n}-{k}"] = {t: [p[-1]["x"], p[-1]["y"]] for t, p in r["etfs"].items()}
    return {"fecha_ultimo_cierre": calcular(precios, etfs)["fecha_ultimo_cierre"], "combinaciones": out}


def correr():
    from top30_retorno import bajar_precios
    etfs = etfs_del_universo()
    precios = bajar_precios(etfs + ["SPY"], periodo="2y")
    res = calcular(precios, etfs)
    c = calcular(precios, etfs, N_CORTO, K_CORTO)
    res["corto"] = {"params": c["params"], "etfs": c["etfs"]}
    n_nuevos = registrar_semana(res, c)
    log.info(f"Bitacora: {n_nuevos} registros nuevos")
    with open(RUTA_EVAL, "w", encoding="utf-8") as f:
        json.dump(evaluar(leer_log()), f, ensure_ascii=False)
    try:
        with open(RUTA_VENTANAS, "w", encoding="utf-8") as f:
            json.dump(probar_ventanas(precios, etfs), f, ensure_ascii=False)
    except Exception as e:
        log.warning(f"Prueba de ventanas: {e}")
    res.pop("cierre_semana", None)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    log.info(f"ETFs medidos contra el SPY: {len(res['etfs'])} de {len(etfs)}")
    return res


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
