"""
Estudio 3 -- CÓMO ENTRAR después de un Gap alcista y DÓNDE PONER EL STOP
(pedido de Victoria, 8/10: ella busca entradas con retroceso, y quiere entender la
lógica del stop).

Aparte del radar (ADITIVO): no toca señales ni Auditoría. Crea solo
data/estudio_entradas.json y data/estudio_entradas_resumen.md.

Simula, para cada Gap alcista histórico de los CEDEARs (misma regla del radar):
  ENTRADAS
    A. mismo día       : entra al cierre del día del gap.
    B. retroceso SMA20 : espera hasta 10 ruedas a que el precio toque su SMA20.
    C. retroceso nivel : espera hasta 10 ruedas a volver al cierre previo al gap.
    D. retroceso -3%   : espera hasta 10 ruedas a caer 3% desde el cierre del gap.
    (B, C y D son órdenes límite: si el precio no vuelve, NO hay operación; se informa
    cuántas se ejecutan.)
  STOPS (desde la entrada)
    -5%, -8%, 2 x ATR(14), mínimo de las 10 ruedas previas (estructural), SMA50 -2%
    (este último tiene tope: si queda a más de 15% de distancia se usa -15%).
  SALIDAS
    stop, o al cabo de 20 ruedas (corto) / 60 ruedas (largo). En el largo también se
    prueba la "protección de ganancia" de Mi Cartera (si llegó a +30%, el stop sube
    a la mitad de la ganancia máxima) contra no usarla.
  MEDIDAS
    % de operaciones ganadoras, resultado promedio y mediano, "R" (resultado dividido
    por el riesgo inicial: 1R = lo que se arriesgó), % que terminó en stop, y
    cuántas órdenes de retroceso se ejecutan.

Limitaciones: el universo son los CEDEARs de HOY (sesgo de supervivencia: no incluye los que
dejaron de existir); velas diarias (si el mismo día toca stop y objetivo no se sabe el orden;
se asume el stop); si abre por debajo del stop, se sale en la apertura; sin comisiones
ni impuestos ni diferencias del CEDEAR en pesos. Mide cuánto sirve cada regla en el
pasado, no promete nada.
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

log = logging.getLogger("estudio.entradas")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ESPERA = 10
ENTRADAS = {"A_mismo_dia": "Mismo día del gap", "B_retroceso_SMA20": "Retroceso a la SMA20",
            "C_retroceso_nivel": "Vuelve al cierre previo al gap", "D_retroceso_3pct": "Retroceso -3% desde el cierre del gap"}
STOPS = {"fijo_5": "-5%", "fijo_8": "-8%", "atr_2x": "2 x ATR", "estructural": "Mínimo de 10 ruedas previas", "sma50": "SMA50 -2% (tope -15%)"}
HORIZONTES = {"corto_20": 20, "largo_60": 60}
RUTA_SALIDA = "data/estudio_entradas.json"
RUTA_RESUMEN = "data/estudio_entradas_resumen.md"
LOCK_DESDE, LOCK_FRACCION = 30.0, 0.5


def simular(o, h, l, c, i0, entrada, stop, horizonte, lock=False):
    """Operación abierta en la rueda i0 al precio 'entrada'. Devuelve (retorno %, R, terminó_en_stop, ruedas)."""
    riesgo = entrada - stop
    if riesgo <= 0 or entrada <= 0:
        return None
    s = stop
    maxp = entrada
    n = len(c)
    # rueda de entrada: solo se sale si CIERRA bajo el stop
    if c[i0] <= s:
        return ((s / entrada - 1) * 100, (s - entrada) / riesgo, True, 0)
    maxp = max(maxp, h[i0])
    for k in range(1, horizonte + 1):
        j = i0 + k
        if j >= n:
            return None  # no hay datos suficientes para cerrar la operación
        if lock:
            gmax = (maxp / entrada - 1) * 100
            if gmax >= LOCK_DESDE:
                s = max(s, entrada * (1 + gmax / 100 * LOCK_FRACCION))
        if o[j] <= s:
            px = o[j]
            return ((px / entrada - 1) * 100, (px - entrada) / riesgo, True, k)
        if l[j] <= s:
            return ((s / entrada - 1) * 100, (s - entrada) / riesgo, True, k)
        maxp = max(maxp, h[j])
    px = c[i0 + horizonte]
    return ((px / entrada - 1) * 100, (px - entrada) / riesgo, False, horizonte)


def encontrar_entrada(tipo, o, h, l, c, sma20, i):
    """Devuelve (índice de rueda de entrada, precio de entrada) o None si no se ejecuta."""
    if tipo == "A_mismo_dia":
        return i, c[i]
    if tipo == "B_retroceso_SMA20":
        for k in range(1, ESPERA + 1):
            j = i + k
            if j >= len(c):
                return None
            if not np.isnan(sma20[j]) and l[j] <= sma20[j]:
                return j, min(o[j], sma20[j])
        return None
    nivel = c[i - 1] if tipo == "C_retroceso_nivel" else c[i] * 0.97
    for k in range(1, ESPERA + 1):
        j = i + k
        if j >= len(c):
            return None
        if l[j] <= nivel:
            return j, min(o[j], nivel)
    return None


def calcular_stops(h, l, c, sma50, atr, i_ent, entrada):
    out = {}
    out["fijo_5"] = entrada * 0.95
    out["fijo_8"] = entrada * 0.92
    a = atr[i_ent]
    out["atr_2x"] = entrada - 2 * a if np.isfinite(a) else np.nan
    ini = max(0, i_ent - 10)
    out["estructural"] = float(np.min(l[ini:i_ent + 1])) * 0.99
    s50 = sma50[i_ent]
    out["sma50"] = max(s50 * 0.98, entrada * 0.85) if np.isfinite(s50) else np.nan
    return out


def evaluar_ticker(df: pd.DataFrame, spy_close: pd.Series):
    r = eg.calcular_ticker(df, spy_close)
    o, h, l, c = (df[k].values.astype(float) for k in ("Open", "High", "Low", "Close"))
    sma20 = pd.Series(c, index=df.index).rolling(20).mean().values
    sma50 = pd.Series(c, index=df.index).rolling(50).mean().values
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - df["Close"].shift()).abs(), (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().values
    filas = []
    idx = np.where(r["gap"].values)[0]
    vol_t = float(r["vol60_anual"].median()) if r["vol60_anual"].notna().any() else None
    grupo = eg.grupo_vol(vol_t)
    for i in idx:
        if i < 15:
            continue
        for et in ENTRADAS:
            ent = encontrar_entrada(et, o, h, l, c, sma20, i)
            if ent is None:
                filas.append({"entrada": et, "ejecutada": False, "grupo": grupo, "anio": int(df.index[i].year)})
                continue
            j, px = ent
            stops = calcular_stops(h, l, c, sma50, atr, j, px)
            for st, sv in stops.items():
                if not np.isfinite(sv) or sv >= px:
                    continue
                for hn, hz in HORIZONTES.items():
                    for lock in ((False, True) if hn == "largo_60" else (False,)):
                        res = simular(o, h, l, c, j, px, sv, hz, lock)
                        if res is None:
                            continue
                        filas.append({"entrada": et, "ejecutada": True, "stop": st, "horizonte": hn, "lock": lock, "grupo": grupo,
                                      "anio": int(df.index[i].year), "ret": res[0], "R": res[1], "stop_hit": res[2], "ruedas": res[3],
                                      "dist_stop_pct": (px - sv) / px * 100})
    return filas


def resumir(df: pd.DataFrame) -> list:
    out = []
    ej = df[df["ejecutada"]]
    for (g, et, st, hn, lk), d in ej.groupby(["grupo_sel", "entrada", "stop", "horizonte", "lock"]):
        out.append({"grupo": g, "entrada": et, "stop": st, "horizonte": hn, "proteccion_ganancia": bool(lk), "n": int(len(d)),
                    "pct_ganadoras": round(float((d["ret"] > 0).mean() * 100), 1), "ret_medio_pct": round(float(d["ret"].mean()), 2),
                    "ret_mediano_pct": round(float(d["ret"].median()), 2), "R_medio": round(float(d["R"].mean()), 2),
                    "pct_en_stop": round(float(d["stop_hit"].mean() * 100), 1), "distancia_stop_mediana_pct": round(float(d["dist_stop_pct"].median()), 1),
                    "peor_operacion_pct": round(float(d["ret"].min()), 1)})
    return out


def correr(series: dict, spy_close: pd.Series) -> dict:
    filas = []
    for t, d in series.items():
        try:
            for f in evaluar_ticker(d, spy_close):
                f["ticker"] = t
                filas.append(f)
        except Exception as e:
            log.warning(f"{t}: {e}")
    if not filas:
        raise RuntimeError("Sin datos")
    df = pd.DataFrame(filas)
    df["lock"] = df["lock"].fillna(False).astype(bool)
    # grupos de análisis: baja_o_media y alta (+ baja sola)
    partes = []
    for nombre, sel in (("baja_o_media", ["baja", "media"]), ("baja", ["baja"]), ("alta", ["alta"])):
        p = df[df["grupo"].isin(sel)].copy()
        p["grupo_sel"] = nombre
        partes.append(p)
    todo = pd.concat(partes)
    res = {"generado_utc": datetime.now(timezone.utc).isoformat(), "entradas": ENTRADAS, "stops": STOPS,
           "horizontes": {k: f"{v} ruedas" for k, v in HORIZONTES.items()}, "espera_max_ruedas": ESPERA,
           "proteccion_ganancia_regla": f"si la ganancia máxima llega a +{LOCK_DESDE:.0f}%, el stop sube a {LOCK_FRACCION:.0%} de esa ganancia",
           "tickers": len(series), "resultados": resumir(todo)}
    # Tasa de ejecución de cada tipo de entrada (sobre todos los gaps)
    ejec = {}
    for g, x in todo.groupby("grupo_sel"):
        # un registro por (gap, entrada): las no ejecutadas ya vienen como una fila; las ejecutadas se repiten por stop/horizonte
        ne = x[~x["ejecutada"]].groupby("entrada").size()
        # eventos ejecutados únicos aproximados: filas ejecutadas con stop fijo_8, horizonte corto, sin lock (siempre existe)
        ee = x[x["ejecutada"] & (x["stop"] == "fijo_8") & (x["horizonte"] == "corto_20") & (~x["lock"])].groupby("entrada").size()
        ejec[g] = {e: {"ejecutadas": int(ee.get(e, 0)), "no_ejecutadas": int(ne.get(e, 0)),
                       "pct_ejecutadas": round(float(ee.get(e, 0) / max(1, ee.get(e, 0) + ne.get(e, 0)) * 100), 1)} for e in ENTRADAS}
    res["ejecucion"] = ejec
    # Por año del mejor combo corto (según R medio, baja_o_media, n>=200)
    r = [x for x in res["resultados"] if x["grupo"] == "baja_o_media" and x["horizonte"] == "corto_20" and not x["proteccion_ganancia"] and x["n"] >= 200]
    if r:
        mejor = max(r, key=lambda x: x["R_medio"])
        res["mejor_corto_baja_o_media"] = mejor
        sel = todo[(todo["grupo_sel"] == "baja_o_media") & todo["ejecutada"] & (todo["entrada"] == mejor["entrada"]) & (todo["stop"] == mejor["stop"]) & (todo["horizonte"] == "corto_20") & (~todo["lock"])]
        res["mejor_por_anio"] = {str(a): {"n": int(len(d)), "ret_medio_pct": round(float(d["ret"].mean()), 2), "R_medio": round(float(d["R"].mean()), 2), "pct_ganadoras": round(float((d["ret"] > 0).mean() * 100), 1)} for a, d in sel.groupby("anio")}
    return res


def resumen_md(res: dict) -> str:
    L = ["# Estudio 3 -- entradas y stops después de un Gap alcista", "", f"Generado: {res['generado_utc'][:16]} UTC. Papeles: {res['tickers']}.", ""]
    for g in ("baja_o_media",):
        L.append(f"## Volatilidad {g.replace('_', ' ')} -- horizonte 20 ruedas (R medio: resultado / riesgo inicial)")
        L.append("| entrada | stop | n | ganadoras % | ret medio % | R medio | en stop % | dist. stop % |")
        L.append("|---|---|---|---|---|---|---|---|")
        for x in sorted([x for x in res["resultados"] if x["grupo"] == g and x["horizonte"] == "corto_20"], key=lambda x: -x["R_medio"])[:20]:
            L.append(f"| {x['entrada']} | {x['stop']} | {x['n']} | {x['pct_ganadoras']} | {x['ret_medio_pct']} | {x['R_medio']} | {x['pct_en_stop']} | {x['distancia_stop_mediana_pct']} |")
        L.append("")
        L.append("## Protección de ganancia (largo, 60 ruedas) -- con y sin")
        for et in ("A_mismo_dia", "B_retroceso_SMA20"):
            for st in ("fijo_8", "sma50"):
                a = [x for x in res["resultados"] if x["grupo"] == g and x["horizonte"] == "largo_60" and x["entrada"] == et and x["stop"] == st]
                for x in sorted(a, key=lambda x: x["proteccion_ganancia"]):
                    L.append(f"- {et} / {st} / protección {'SÍ' if x['proteccion_ganancia'] else 'NO'}: n={x['n']}, ret medio {x['ret_medio_pct']}%, R {x['R_medio']}, en stop {x['pct_en_stop']}%")
    L.append("")
    L.append("## Cuántas órdenes de retroceso se ejecutan")
    for g, d in res["ejecucion"].items():
        L.append(f"- {g}: " + "; ".join(f"{e}: {v['pct_ejecutadas']}%" for e, v in d.items()))
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
