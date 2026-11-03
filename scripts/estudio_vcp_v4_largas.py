"""
Estudio VCP v4 -- BASES LARGAS (aparte: no toca el radar, la Watchlist VCP, la seccion "Bases VCP reales" ni la Auditoria).

Pregunta: la base V4 hoy acepta como maximo 150 ruedas (~7 meses) y 4 contracciones.
  * Que pasa si se aceptan bases mas largas (250 o 325 ruedas, ~1 a 1,3 anios) y hasta 6 contracciones?
  * Las bases largas dan un exceso sobre SPY distinto de las de hasta 150 ruedas?

Misma definicion de base, misma entrada (primer cierre sobre el pivote, en tendencia), mismos stops y misma
medida (exceso vs SPY a igual plazo) que estudio_vcp_v4.py. Solo cambian MAX_BASE y MAX_CONTR.
Baja 5 anios de datos (el v4 usaba 2): ademas de las bases largas, esto prueba la base V4 original en
3 anios que no habia visto (prueba fuera de muestra en el tiempo).

Limites que se informan en el resumen: el universo es el actual (sesgo de supervivencia), los eventos de
20 ruedas se solapan (el IC95 agrupa por dia), y probar varias variantes aumenta la chance de un falso hallazgo.
Es una pista, no una validacion.

Se corre a mano: Actions -> "Estudio VCP v4 bases largas" -> Run workflow.
"""
import json, logging, sys
import numpy as np
import pandas as pd

import estudio_vcp_v4 as v4

v1, v2, v3 = v4.v1, v4.v2, v4.v3
log = logging.getLogger("vcp_largas")

RUTA_JSON = "data/estudio_vcp_v4_largas.json"
RUTA_MD = "data/estudio_vcp_v4_largas_resumen.md"

PERIODO = "5y"
VARIANTES = {
    "A (actual: 150 ruedas, 4 contr.)": dict(MAX_BASE=150, MAX_CONTR=4),
    "B (250 ruedas, 4 contr.)": dict(MAX_BASE=250, MAX_CONTR=4),
    "C (325 ruedas, 4 contr.)": dict(MAX_BASE=325, MAX_CONTR=4),
    "D (325 ruedas, 6 contr.)": dict(MAX_BASE=325, MAX_CONTR=6),
}
DEFAULT = dict(MAX_BASE=v4.MAX_BASE, MAX_CONTR=v4.MAX_CONTR)
CLAVES = ["V4A+S10L", "V4A+SU", "V4B+S10L", "V4P+S10L", "V4C+S10L", "BASE+S10L"]
TRAMOS = (("hasta 150 ruedas", 0, 150), ("151 a 250", 151, 250), ("251 a 325", 251, 325))


def _poner(cfg):
    for k, v in cfg.items():
        setattr(v4, k, v)


def _fmt(r):
    if not r or r.get("n", 0) == 0:
        return "n 0"
    ic = r.get("exceso_ic95")
    ics = f" [{ic[0]:+.2f}, {ic[1]:+.2f}]" if isinstance(ic, (list, tuple)) and len(ic) == 2 and None not in ic else ""
    return f"{r['exceso']:+.2f}{ics} (n {r['n']}, R {r['R']:+.2f}, parado {r['pct_parado']:.0f}%)"


def _anual(C, spy):
    """Retorno medio a 20 ruedas de SPY y del universo por anio (contexto: que hizo el mercado cada anio)."""
    h = v4.HORIZONTE
    fw = (C.shift(-h) / C - 1) * 100
    fs = (spy.shift(-h) / spy - 1) * 100
    pos = np.arange(len(C))
    ok = (pos >= v4.MIN_HIST) & (pos + h < len(C))
    idx = C.index[ok]
    uni = fw.loc[idx].mean(axis=1)
    sp = fs.loc[idx]
    out = {}
    for y in sorted({d.year for d in idx}):
        m = np.array([d.year == y for d in idx])
        out[str(y)] = dict(dias=int(m.sum()), spy_20r=round(float(sp[m].mean()), 2), universo_20r=round(float(uni[m].mean()), 2))
    return out


def correr(datos=None, guardar=True):
    if datos is None:
        from config import TICKERS, BENCHMARK
        O, H, L, C, V = v4.descargar_ohlc(list(dict.fromkeys(list(TICKERS) + [BENCHMARK])), period=PERIODO)
        bench = BENCHMARK
    else:
        O, H, L, C, V = datos
        bench = "SPY"
    if bench not in C.columns or C.shape[1] < 30 or len(C) < v4.MIN_HIST + 60:
        log.error("Pocos datos -- se aborta")
        sys.exit(1)
    spy = C[bench]
    cols = [t for t in C.columns if t != bench and V[t].notna().sum() > 200]
    C2, V2, O2, H2, L2 = C[cols], V[cols], O[cols], H[cols], L[cols]
    S = v1._senales(C2, V2)
    pl = v2._plantilla(C2)

    res = {"variantes": {}, "tramos": {}, "por_anio": {}, "hoy_largas": []}
    dfs = {}
    hoy_base = set()
    try:
        for nombre, cfg in VARIANTES.items():
            _poner(cfg)
            log.info(f"variante {nombre}")
            df, hoy = v4._eventos(O2, H2, L2, C2, S, pl, spy, v4.K_PRINCIPAL)
            dfs[nombre] = df
            if nombre.startswith("A"):
                hoy_base = {h["ticker"] for h in hoy}
            elif nombre.startswith("D"):
                res["hoy_largas"] = [h for h in hoy if h["ticker"] not in hoy_base]
            tabla = {}
            if not df.empty:
                for (f, s), g in df.groupby(["forma", "stop"]):
                    k = f"{f}+{s}"
                    if k in CLAVES:
                        tabla[k] = v3._res(g, ic=True)
            res["variantes"][nombre] = tabla
    finally:
        _poner(DEFAULT)

    # Tramos por largo de base (dentro de la variante mas amplia en contracciones, D, y en C)
    for nombre in ("C (325 ruedas, 4 contr.)", "D (325 ruedas, 6 contr.)"):
        df = dfs.get(nombre)
        if df is None or df.empty:
            continue
        out = {}
        for forma in ("V4A", "V4B", "V4P"):
            g = df[(df["forma"] == forma) & (df["stop"] == "S10L")]
            out[f"{forma}+S10L"] = {t: v3._res(g[(g["largo"] >= a) & (g["largo"] <= b)], ic=True) for t, a, b in TRAMOS}
        res["tramos"][nombre] = out

    # Por anio: la base original (A) y la mas amplia (D), contra la rama de control BASE
    for nombre in ("A (actual: 150 ruedas, 4 contr.)", "D (325 ruedas, 6 contr.)"):
        df = dfs.get(nombre)
        if df is None or df.empty:
            continue
        out = {}
        for k in ("V4A+S10L", "BASE+S10L"):
            f, s = k.split("+")
            g = df[(df["forma"] == f) & (df["stop"] == s)].copy()
            g["anio"] = g["fecha"].str[:4]
            out[k] = {y: v3._res(x) for y, x in g.groupby("anio")}
        res["por_anio"][nombre] = out
    res["mercado_por_anio"] = _anual(C2, spy)

    f0, f1 = C.index[0].strftime("%Y-%m-%d"), C.index[-1].strftime("%Y-%m-%d")
    if guardar:
        with open(RUTA_JSON, "w", encoding="utf-8") as f:
            json.dump(dict(generado=f1, universo=len(cols), periodo=PERIODO, resultados=res), f, ensure_ascii=False, indent=1)
        with open(RUTA_MD, "w", encoding="utf-8") as f:
            f.write(_md(res, len(cols), f0, f1))
    return res


def _md(res, nt, f0, f1):
    L = ["# Estudio VCP v4 -- bases largas", "",
         f"Universo: {nt} activos. Yahoo del {f0} al {f1}. Mismos criterios que el estudio v4 (giros a {v4.K_PRINCIPAL} ruedas, entrada en el primer cierre sobre el pivote, en tendencia). "
         "Medida: exceso sobre SPY a igual plazo (%), con IC95 agrupado por dia. Entre parentesis: casos, R medio, % que toco el stop.", "",
         "**Como leerlo:** es una pista, no una validacion. Universo actual (sesgo de supervivencia, que infla los anios viejos), eventos solapados, y varias variantes probadas a la vez.", "",
         "## 1. Variantes (todo el periodo, exceso vs SPY %)", "",
         "| Variante | " + " | ".join(CLAVES) + " |", "|---|" + "---|" * len(CLAVES)]
    for nombre, tabla in res["variantes"].items():
        L.append(f"| {nombre} | " + " | ".join(_fmt(tabla.get(k)) for k in CLAVES) + " |")
    L += ["", "## 2. Por largo de base (exceso vs SPY %, stop S10L)", ""]
    for nombre, out in res["tramos"].items():
        L += [f"**Variante {nombre}**", "", "| Forma | " + " | ".join(t for t, _, _ in TRAMOS) + " |", "|---|" + "---|" * len(TRAMOS)]
        for k, tr in out.items():
            L.append(f"| {k} | " + " | ".join(_fmt(tr.get(t)) for t, _, _ in TRAMOS) + " |")
        L.append("")
    L += ["## 3. Por anio (exceso vs SPY %, stop S10L)", "",
          "Los anios antes del ultimo no los habia visto el estudio v4 (usaba 2 anios): es una prueba fuera de muestra en el tiempo, con el sesgo de supervivencia ya dicho.", ""]
    mk = res.get("mercado_por_anio", {})
    for nombre, out in res["por_anio"].items():
        anios = sorted({y for d in out.values() for y in d})
        L += [f"**Variante {nombre}**", "", "| Anio | SPY 20r | Universo 20r | " + " | ".join(out) + " |", "|---|---|---|" + "---|" * len(out)]
        for y in anios:
            m = mk.get(y, {})
            L.append(f"| {y} | {m.get('spy_20r', '')} | {m.get('universo_20r', '')} | " + " | ".join(_fmt(out[k].get(y)) for k in out) + " |")
        L.append("")
    hl = res.get("hoy_largas") or []
    L += ["## 4. Candidatas de hoy que solo existen con las bases largas (variante D)", ""]
    if hl:
        L += ["| Ticker | Contr. | Profundidades % | Min. suben | Pivote | Stop | Cierre | A pivote % |", "|---|---|---|---|---|---|---|---|"]
        for h in hl:
            L.append(f"| {h['ticker']} | {h['contracciones']} | {h['profundidades']} | {'si' if h['minimos_suben'] else 'no'} | {h['pivote']} | {h['stop']} | {h['cierre']} | {h['dist_pivote_pct']} |")
    else:
        L.append("Ninguna.")
    L += ["", "## 5. Que mirar antes de sacar conclusiones", "",
          "- Si el exceso de las bases largas no se separa del de las cortas (IC95 que se solapan), alargar no agrega nada.",
          "- Si el exceso de V4A no supera al de BASE (la rama de control, sin base VCP) en los anios nuevos, la base no estaria aportando mas que la tendencia.",
          "- Un anio que concentra todo el resultado (como 2026-T1 en el v4) pesa mas que el promedio.",
          "- Con pocos casos por tramo, los IC95 son anchos: pesa mas el n que el promedio.", ""]
    return "\n".join(L)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
