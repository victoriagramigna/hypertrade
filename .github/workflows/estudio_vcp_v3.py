"""
Estudio VCP v3 -- las formas contra el mercado y contra una base.

Aparte y aditivo: NO toca el radar, la app, la Watchlist VCP ni la Auditoria. Se corre a mano
desde Actions ("Estudio VCP v3"). Baja ~2 anios de cierre y volumen de Yahoo y escribe
data/estudio_vcp_v3.json y data/estudio_vcp_v3_resumen.md.

Lo que corrige respecto de la v2 (que no comparaba contra nada):
  * Exceso contra SPY: cada operacion simulada se compara con SPY durante LA MISMA tenencia.
  * BASE: rupturas de 20 ruedas en tendencia (cerca del maximo anual, sobre la media de 50,
    FR >= 50) SIN la forma. Si una forma no le gana a la base, la forma no aporta.
  * Mercado: retorno a 20 ruedas de SPY y de todo el universo (cualquier activo, cualquier
    dia) por mitad y por trimestre, para saber si una caida es del mercado o de la forma.
  * Regimen: rupturas con SPY sobre o bajo su media de 50 ruedas.
  * Intervalos por REMUESTREO DE DIAS (no de casos): los casos de un mismo dia son un solo
    bloque, asi se toma en cuenta que se agrupan en los mismos dias de mercado.
Formas (ver estudio_vcp_v2.py): F0 actual, F0T + plantilla de tendencia, F1 rangos decrecientes,
F2 triangulo (rangos decrecientes + minimos que no bajan), F3 triangulo + plantilla.
Operacion simulada (solo para comparar, no es una recomendacion): entrada al cierre de la ruptura,
salida en el primer cierre bajo el stop (al precio de ese cierre) o a las 20 ruedas.
Stops: S20 / S10 = minimo cierre de las ultimas 20 / 10 ruedas; S8 = 8% bajo el pivote.
Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un solo regimen,
RS y plantilla con proxy propio (percentil de retorno a 126 ruedas), solo cierres, umbrales mios.
"""
import json, logging, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts")
import estudio_vcp_volumen as v1
import estudio_vcp_v2 as v2

log = logging.getLogger("radar.estudio_vcp_v3")
RUTA_JSON = "data/estudio_vcp_v3.json"
RUTA_MD = "data/estudio_vcp_v3_resumen.md"
STOPS = {"S20": 20, "S10": 10, "S8": None}
ENTRADAS = ["F0", "F0T", "F1", "F2", "F3", "BASE"]
HORIZONTE = 20
SEPARACION = 20
MIN_HIST = 252
UMBRALES_VOL = (1.0, 1.5, 2.0, 3.0)


def _eventos(C, S, spy, formas):
    piv = C.rolling(v2.TRAMO).max().shift(1)
    stp = {k: C.rolling(n).min().shift(1) for k, n in STOPS.items() if n}
    f0_prev = formas["F0"].shift(1).fillna(False).astype(bool)
    entradas = {k: formas[k].shift(1).fillna(False).astype(bool) & (C > piv) for k in formas}
    entradas["BASE"] = S["tendencia"].shift(1).fillna(False).astype(bool) & (C > piv) & ~f0_prev
    seca_prev = S["seca"].shift(1).fillna(False).astype(bool)
    idx = C.index
    spyv = spy.reindex(idx).values
    spy_sobre = (spy > spy.rolling(50).mean()).reindex(idx).fillna(False).values
    filas = []
    for ek, M in entradas.items():
        for t in C.columns:
            m, c = M[t].values, C[t].values
            ultimo = -10 ** 9
            for j in np.where(m)[0]:
                if j < MIN_HIST or j - ultimo < SEPARACION or j + HORIZONTE >= len(c):
                    continue
                ultimo = j
                entrada = c[j]
                vr = S["volrel"][t].values[j]
                f = idx[j]
                base = dict(forma=ek, ticker=t, fecha=f.strftime("%Y-%m-%d"), trimestre=f"{f.year}-T{(f.month - 1) // 3 + 1}",
                            volrel=float(vr) if pd.notna(vr) else None, seca=bool(seca_prev[t].values[j]),
                            spy_sobre50=bool(spy_sobre[j]))
                futuro = c[j + 1:j + HORIZONTE + 1]
                for sk in STOPS:
                    nivel = piv[t].values[j] * 0.92 if sk == "S8" else stp[sk][t].values[j]
                    if not np.isfinite(nivel) or nivel >= entrada:
                        continue
                    riesgo = (entrada - nivel) / entrada * 100
                    bajo = np.where(futuro < nivel)[0]
                    k = (bajo[0] + 1) if len(bajo) else HORIZONTE
                    salida = futuro[k - 1]
                    ret = (salida / entrada - 1) * 100
                    ret_spy = (spyv[j + k] / spyv[j] - 1) * 100
                    filas.append(dict(base, stop=sk, riesgo=riesgo, parado=bool(len(bajo)), ret=ret,
                                      exceso=ret - ret_spy, R=ret / riesgo))
    return pd.DataFrame(filas)


def _ic_dias(g, col, n=2000, seed=11):
    """IC95 del promedio remuestreando DIAS completos (los casos de un dia van juntos)."""
    if g.empty:
        return None
    uniq, inv = np.unique(g["fecha"].values, return_inverse=True)
    if len(uniq) < 10:
        return None
    sums = np.bincount(inv, weights=g[col].values)
    cnt = np.bincount(inv).astype(float)
    idx = np.random.default_rng(seed).integers(0, len(uniq), (n, len(uniq)))
    m = sums[idx].sum(axis=1) / cnt[idx].sum(axis=1)
    return [round(float(np.percentile(m, 2.5)), 2), round(float(np.percentile(m, 97.5)), 2)]


def _res(g, ic=False):
    if g.empty:
        return dict(n=0)
    d = dict(n=int(len(g)), dias=int(g["fecha"].nunique()), riesgo=round(float(g["riesgo"].mean()), 1),
             pct_parado=round(float(g["parado"].mean() * 100), 1), ret=round(float(g["ret"].mean()), 2),
             exceso=round(float(g["exceso"].mean()), 2), pct_gan=round(float((g["ret"] > 0).mean() * 100), 1),
             R=round(float(g["R"].mean()), 2))
    if ic:
        d["exceso_ic95"] = _ic_dias(g, "exceso")
    return d


def _mercado(C, spy, corte):
    """Retorno medio a 20 ruedas de SPY y del universo (cualquier activo, cualquier dia) por mitad y trimestre."""
    fw = (C.shift(-HORIZONTE) / C - 1) * 100
    fs = (spy.shift(-HORIZONTE) / spy - 1) * 100
    pos = np.arange(len(C))
    ok = (pos >= MIN_HIST) & (pos + HORIZONTE < len(C))
    idx = C.index[ok]
    uni = fw.loc[idx].mean(axis=1)
    sp = fs.loc[idx]
    out = {}
    def agrega(nombre, mask):
        out[nombre] = dict(dias=int(mask.sum()), spy_20r=round(float(sp[mask].mean()), 2), universo_20r=round(float(uni[mask].mean()), 2))
    f = pd.Series(idx.strftime("%Y-%m-%d"), index=idx)
    agrega("primera mitad", f < corte)
    agrega("segunda mitad", f >= corte)
    for q in sorted({f"{d.year}-T{(d.month - 1) // 3 + 1}" for d in idx}):
        agrega(q, pd.Series([f"{d.year}-T{(d.month - 1) // 3 + 1}" == q for d in idx], index=idx))
    return out


def analizar(df, C, spy):
    out = {"definiciones": {}, "mitades": {}, "regimen": {}, "trimestres": {}, "volumen": {}}
    if df.empty:
        return out, None
    pos = np.arange(len(C))
    ini, fin = MIN_HIST, len(C) - HORIZONTE - 1
    corte = C.index[(ini + fin) // 2].strftime("%Y-%m-%d")
    out["corte_mitades"] = corte
    out["mercado"] = _mercado(C, spy, corte)
    for (f, s), g in df.groupby(["forma", "stop"]):
        k = f"{f}+{s}"
        out["definiciones"][k] = _res(g, ic=True)
        out["mitades"][k] = {"primera": _res(g[g["fecha"] < corte]), "segunda": _res(g[g["fecha"] >= corte])}
        out["regimen"][k] = {"SPY sobre su media de 50": _res(g[g["spy_sobre50"]]), "SPY bajo su media de 50": _res(g[~g["spy_sobre50"]])}
        out["trimestres"][k] = {q: _res(h) for q, h in g.groupby("trimestre")}
    for f in ("F0", "F0T", "F2", "BASE"):
        g = df[(df["forma"] == f) & (df["stop"] == "S10")]
        out["volumen"][f"{f}+S10"] = {f"vol>={u}x": _res(g[g["volrel"].fillna(0) >= u]) for u in UMBRALES_VOL}
        out["volumen"][f"{f}+S10"]["vol>=1.5x y volumen previo seco"] = _res(g[(g["volrel"].fillna(0) >= 1.5) & g["seca"]])
    return out, corte


NOM = {"F0": "F0 forma actual", "F0T": "F0T actual + plantilla", "F1": "F1 rangos decrecientes", "F2": "F2 triangulo",
       "F3": "F3 triangulo + plantilla", "BASE": "BASE tendencia + ruptura, sin forma"}


def _nom(k):
    f, s = k.split("+")
    return f"{NOM[f]} · {s}"


def _md(res, nt, f0, f1):
    L = ["# Estudio VCP v3 -- las formas contra el mercado y contra una base", "",
         f"Universo: {nt} activos. Yahoo del {f0} al {f1}. Operacion simulada: entrada al cierre de la ruptura; salida en el primer cierre bajo el stop o a las 20 ruedas. "
         f"Exceso = retorno de la operacion menos el de SPY durante la misma tenencia. Los intervalos remuestrean DIAS completos.", "",
         "## 1. Contexto de mercado (retorno medio a 20 ruedas, cualquier dia)", "", "| Periodo | Dias | SPY % | Universo (cualquier activo) % |", "|---|---|---|---|"]
    for q, d in res["mercado"].items():
        L.append(f"| {q} | {d['dias']} | {d['spy_20r']} | {d['universo_20r']} |")
    L += ["", f"Corte de mitades: {res['corte_mitades']} (punto medio de la ventana evaluada).", "",
          "## 2. Formas y BASE: todo el periodo", "", "| Definicion | Casos | Dias | Riesgo % | % toco stop | Retorno % | Exceso vs SPY % [IC95 por dias] | % ganadoras | R |", "|---|---|---|---|---|---|---|---|---|"]
    for e in ENTRADAS:
        for s in STOPS:
            d = res["definiciones"].get(f"{e}+{s}")
            if d and d["n"]:
                L.append(f"| {_nom(e + '+' + s)} | {d['n']} | {d['dias']} | {d['riesgo']} | {d['pct_parado']} | {d['ret']} | {d['exceso']} {d.get('exceso_ic95') or ''} | {d['pct_gan']} | {d['R']} |")
    for titulo, clave, sub in (("3. Por mitad del periodo (exceso vs SPY %)", "mitades", ("primera", "segunda")),
                               ("4. Segun el regimen del mercado en el dia de la ruptura (exceso vs SPY %)", "regimen", ("SPY sobre su media de 50", "SPY bajo su media de 50"))):
        L += ["", f"## {titulo}", "", "| Definicion | " + " | ".join(f"{x} (casos)" for x in sub) + " |", "|---|" + "---|" * len(sub)]
        for e in ENTRADAS:
            for s in ("S10", "S20"):
                d = res[clave].get(f"{e}+{s}")
                if d:
                    cel = [f"{d[x]['exceso']} ({d[x]['n']})" if d[x]["n"] else "- (0)" for x in sub]
                    L.append(f"| {_nom(e + '+' + s)} | " + " | ".join(cel) + " |")
    qs = sorted({q for d in res["trimestres"].values() for q in d})
    L += ["", "## 5. Por trimestre de la ruptura, stop 10 (exceso vs SPY %, casos)", "", "| Definicion | " + " | ".join(qs) + " |", "|---|" + "---|" * len(qs)]
    for e in ENTRADAS:
        d = res["trimestres"].get(f"{e}+S10")
        if d:
            L.append(f"| {NOM[e]} | " + " | ".join(f"{d[q]['exceso']} ({d[q]['n']})" if q in d and d[q]["n"] else "-" for q in qs) + " |")
    L += ["", "## 6. Umbral de volumen de la ruptura, stop 10 (exceso vs SPY %)", "", "| Definicion | Condicion | Casos | Retorno % | Exceso % | % ganadoras |", "|---|---|---|---|---|---|"]
    for k, grupos in res["volumen"].items():
        for c, d in grupos.items():
            if d["n"]:
                L.append(f"| {_nom(k)} | {c} | {d['n']} | {d['ret']} | {d['exceso']} | {d['pct_gan']} |")
    L += ["", "## Como leerlo", "",
          "- Una forma aporta algo si su exceso le gana al de la BASE con el mismo stop, se repite en las dos mitades y en distintos regimenes, y su intervalo no incluye el cero.",
          "- Con menos de 30 casos (o menos de 30 dias) no concluir nada.",
          "- El retorno simulado no es una recomendacion ni incluye costos; sirve solo para comparar definiciones.",
          "- Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un solo regimen, RS y plantilla con proxy propio, solo cierres, umbrales elegidos por mi."]
    return "\n".join(L) + "\n"


def correr(C=None, V=None, guardar=True):
    if C is None:
        from config import TICKERS, BENCHMARK
        C, V = v1.descargar(list(dict.fromkeys(list(TICKERS) + [BENCHMARK])))
        bench = BENCHMARK
    else:
        bench = "SPY"
    if bench not in C.columns or C.shape[1] < 100 or len(C) < MIN_HIST + 60:
        log.error("Pocos datos -- se aborta")
        sys.exit(1)
    spy = C[bench]
    cols = [t for t in C.columns if t != bench and V[t].notna().sum() > 200]
    C2, V2 = C[cols], V[cols]
    S = v1._senales(C2, V2)
    formas, _ = v2._formas(C2, V2, S)
    df = _eventos(C2, S, spy, formas)
    res, corte = analizar(df, C2, spy)
    f0, f1 = C.index[0].strftime("%Y-%m-%d"), C.index[-1].strftime("%Y-%m-%d")
    if guardar:
        with open(RUTA_JSON, "w", encoding="utf-8") as f:
            json.dump(dict(generado=f1, universo=len(cols), resultados=res), f, ensure_ascii=False, indent=1)
        with open(RUTA_MD, "w", encoding="utf-8") as f:
            f.write(_md(res, len(cols), f0, f1))
    return res, df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
