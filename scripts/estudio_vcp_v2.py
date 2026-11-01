"""
Estudio VCP v2 -- ¿que definicion de "forma VCP" y de stop se parece a la teoria y como le fue?

Aparte y aditivo: NO toca el radar, la app, la Watchlist VCP ni la Auditoria. Se corre a
mano desde Actions ("Estudio VCP v2"). Baja ~2 anios de cierre y volumen de Yahoo (usa la
descarga del estudio anterior) y escribe data/estudio_vcp_v2.json y
data/estudio_vcp_v2_resumen.md.

Dos preguntas, medidas sobre la historia:
 A) FORMA. La forma actual mide la caida maxima dentro de cada tramo de 20 ruedas; una suba
    casi recta tiene caidas chicas y la pasa, aunque no sea una base. La teoria describe un
    triangulo: el RANGO de precio se angosta tramo a tramo, con maximos parecidos y minimos
    que suben. Formas comparadas (todas sobre tres tramos de 20 ruedas, con cierres):
      F0  forma actual (caidas maximas decrecientes, la ultima <= 8%, cerca del maximo anual,
          sobre la media de 50, FR >= 50).
      F0T F0 + plantilla de tendencia de Minervini (9 condiciones).
      F1  RANGOS decrecientes (maximo-minimo de cada tramo), el ultimo <= 10%, + tendencia
          (cerca del maximo anual, sobre la media de 50, FR >= 50).
      F2  F1 + minimos que no bajan de un tramo al siguiente (triangulo).
      F3  F2 + plantilla de tendencia.
 B) STOP. Minimo cierre de las ultimas 20 (S20), 10 (S10) o 5 (S5) ruedas, o 8% bajo el pivote
    (S8). Pivote = maximo cierre de las ultimas 20 ruedas.
Operacion simulada (solo para comparar definiciones, no es una recomendacion): entrada al
cierre de la ruptura (cierre sobre el pivote del dia anterior, con la forma cumplida el dia
anterior); salida en el primer cierre bajo el stop (al precio de ese cierre) o, si no pasa, al
cierre de la rueda 20. Se mide riesgo inicial, % que toco el stop, retorno, % ganadoras y el
retorno en multiplos del riesgo (R = retorno / riesgo inicial).
Plantilla de tendencia (9): precio sobre las medias de 150 y 200; ambas medias suben (vs 20
ruedas atras); media de 50 sobre las de 150 y 200; precio >= 30% sobre el minimo de 52
semanas; a menos de 25% del maximo de 52 semanas; fuerza relativa >= 70 (aca: percentil de
retorno a 126 ruedas dentro del universo, un PROXY propio, no el RS Score del radar).
Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un solo
regimen, eventos del mismo ticker y forma separados >= 20 ruedas, el intervalo del promedio
usa remuestreo simple y subestima la incertidumbre porque los casos se agrupan en los mismos
dias de mercado; las formas estrictas dan pocos casos.
"""
import json, logging, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts")
import estudio_vcp_volumen as v1

log = logging.getLogger("radar.estudio_vcp_v2")
RUTA_JSON = "data/estudio_vcp_v2.json"
RUTA_MD = "data/estudio_vcp_v2_resumen.md"
TRAMO = 20
MAX_RANGO_ULTIMO = 10.0
STOPS = {"S20": 20, "S10": 10, "S5": 5, "S8": None}
FORMAS = ["F0", "F0T", "F1", "F2", "F3"]
HORIZONTE = 20
SEPARACION = 20
MIN_HIST = 252
UMBRALES_VOL = (1.0, 1.5, 2.0, 3.0)


def _plantilla(C):
    """DataFrame booleano: plantilla de tendencia de Minervini (9 condiciones)."""
    m50, m150, m200 = C.rolling(50).mean(), C.rolling(150).mean(), C.rolling(200).mean()
    mx, mn = C.rolling(252).max(), C.rolling(252).min()
    ret126 = C / C.shift(126) - 1
    rs70 = ret126.rank(axis=1, pct=True) * 100 >= 70
    cond = [C > m150, C > m200, m150 > m150.shift(20), m200 > m200.shift(20), m50 > m150, m50 > m200,
            C >= 1.3 * mn, C >= 0.75 * mx, rs70]
    out = cond[0]
    for c in cond[1:]:
        out = out & c
    return out.fillna(False).astype(bool)


def _formas(C, V, S):
    """Devuelve dict forma -> DataFrame booleano (misma forma que C)."""
    r = lambda sh: (C.rolling(TRAMO).max().shift(sh) - C.rolling(TRAMO).min().shift(sh)) / C.rolling(TRAMO).max().shift(sh) * 100
    r3, r2, r1 = r(0), r(TRAMO), r(2 * TRAMO)
    m3, m2, m1 = C.rolling(TRAMO).min(), C.rolling(TRAMO).min().shift(TRAMO), C.rolling(TRAMO).min().shift(2 * TRAMO)
    tend = S["tendencia"]
    pl = _plantilla(C)
    f0 = S["forma"].fillna(False).astype(bool)
    f1 = ((r1 > r2) & (r2 > r3) & (r3 <= MAX_RANGO_ULTIMO) & tend).fillna(False).astype(bool)
    f2 = (f1 & (m3 >= m2) & (m2 >= m1)).fillna(False).astype(bool)
    return {"F0": f0, "F0T": f0 & pl, "F1": f1, "F2": f2, "F3": f2 & pl}, pl


def _eventos(C, V, S, formas):
    pivote = C.rolling(TRAMO).max().shift(1)
    stp = {k: C.rolling(n).min().shift(1) for k, n in STOPS.items() if n}
    seca_prev = S["seca"].shift(1).fillna(False).astype(bool)
    idx = C.index
    filas = []
    for fk, F in formas.items():
        rup = F.shift(1).fillna(False).astype(bool) & (C > pivote)
        for t in C.columns:
            m, c = rup[t].values, C[t].values
            ultimo = -10 ** 9
            for j in np.where(m)[0]:
                if j < MIN_HIST or j - ultimo < SEPARACION or j + HORIZONTE >= len(c):
                    continue
                ultimo = j
                entrada = c[j]
                vr = S["volrel"][t].values[j]
                base = dict(forma=fk, ticker=t, fecha=idx[j].strftime("%Y-%m-%d"),
                            volrel=float(vr) if pd.notna(vr) else None, seca=bool(seca_prev[t].values[j]))
                futuro = c[j + 1:j + HORIZONTE + 1]
                for sk in STOPS:
                    nivel = pivote[t].values[j] * 0.92 if sk == "S8" else stp[sk][t].values[j]
                    if not np.isfinite(nivel) or nivel >= entrada:
                        continue
                    riesgo = (entrada - nivel) / entrada * 100
                    bajo = np.where(futuro < nivel)[0]
                    salida, parado = (futuro[bajo[0]], True) if len(bajo) else (futuro[-1], False)
                    ret = (salida / entrada - 1) * 100
                    filas.append(dict(base, stop=sk, riesgo=riesgo, parado=parado, ret=ret, R=ret / riesgo))
    return pd.DataFrame(filas)


def _ic(x, n=2000, seed=7):
    x = np.asarray(x, float)
    if len(x) < 10:
        return None
    m = np.random.default_rng(seed).choice(x, (n, len(x))).mean(axis=1)
    return [round(float(np.percentile(m, 2.5)), 2), round(float(np.percentile(m, 97.5)), 2)]


def _resumen(g, con_ic=False):
    if g.empty:
        return dict(n=0)
    d = dict(n=int(len(g)), riesgo_prom=round(float(g["riesgo"].mean()), 1), pct_parado=round(float(g["parado"].mean() * 100), 1),
             ret_prom=round(float(g["ret"].mean()), 2), ret_mediana=round(float(g["ret"].median()), 2),
             pct_ganadoras=round(float((g["ret"] > 0).mean() * 100), 1), R_prom=round(float(g["R"].mean()), 2))
    if con_ic:
        d["ret_prom_ic95"] = _ic(g["ret"])
    return d


def _clase(r):
    return "hasta 8%" if r <= 8 else "8 a 10%" if r <= 10 else "mas de 10%"


def analizar(df):
    out = {"definiciones": {}, "por_riesgo": {}, "por_mitad": {}, "por_volumen": {}}
    if df.empty:
        return out
    fechas = sorted(df["fecha"].unique())
    corte = fechas[len(fechas) // 2]
    for (f, s), g in df.groupby(["forma", "stop"]):
        out["definiciones"][f"{f}+{s}"] = _resumen(g, con_ic=True)
        if s in ("S10", "S20"):
            out["por_mitad"][f"{f}+{s}"] = {"primera": _resumen(g[g["fecha"] < corte]), "segunda": _resumen(g[g["fecha"] >= corte]), "corte": corte}
    for f in ("F0", "F1", "F2"):
        g = df[(df["forma"] == f) & (df["stop"] == "S10")].copy()
        if g.empty:
            continue
        g["clase"] = g["riesgo"].map(_clase)
        out["por_riesgo"][f"{f}+S10"] = {c: _resumen(h) for c, h in g.groupby("clase")}
        out["por_volumen"][f"{f}+S10"] = {f"vol>={u}x": _resumen(g[g["volrel"].fillna(0) >= u]) for u in UMBRALES_VOL}
        out["por_volumen"][f"{f}+S10"]["vol>=1.5x y volumen previo seco"] = _resumen(g[(g["volrel"].fillna(0) >= 1.5) & g["seca"]])
    return out


def _hoy(C, V, S, formas, pl):
    i = len(C) - 1
    lista = []
    for t in C.columns:
        flags = {k: bool(F[t].iloc[i]) for k, F in formas.items()}
        if not any(flags.values()):
            continue
        c = C[t].values
        pv = float(np.max(c[-TRAMO:]))
        fila = dict(ticker=t, cierre=round(float(c[-1]), 2), pivote=round(pv, 2), plantilla_completa=bool(pl[t].iloc[i]),
                    rango_ult_tramo_pct=round(float((np.max(c[-TRAMO:]) - np.min(c[-TRAMO:])) / np.max(c[-TRAMO:]) * 100), 1), **flags)
        for sk, n in STOPS.items():
            nivel = pv * 0.92 if sk == "S8" else float(np.min(c[-n:]))
            fila[f"riesgo_{sk}_pct"] = round((nivel / pv - 1) * 100, 1)
        lista.append(fila)
    return dict(fecha=C.index[-1].strftime("%Y-%m-%d"), lista=sorted(lista, key=lambda x: x["ticker"]))


NOM_F = {"F0": "F0 forma actual", "F0T": "F0T forma actual + plantilla", "F1": "F1 rangos decrecientes", "F2": "F2 rangos decrecientes + minimos que suben (triangulo)", "F3": "F3 triangulo + plantilla"}


def _nom(k):
    f, s = k.split("+")
    return f"{NOM_F[f]} · stop {s}"


def _md(res, hoy, nt, f0, f1):
    L = ["# Estudio VCP v2 -- forma y stop", "", f"Universo: {nt} activos. Yahoo del {f0} al {f1}. Operacion simulada: entrada al cierre de la ruptura; salida en el primer cierre bajo el stop o a las 20 ruedas.", "",
         "## 1. Hoy: quien cumple cada forma", ""]
    n = {k: sum(1 for x in hoy["lista"] if x[k]) for k in FORMAS}
    L.append("Cantidad de activos que cumplen hoy (" + hoy["fecha"] + "): " + ", ".join(f"{NOM_F[k].split(' ')[0]}: {v}" for k, v in n.items()) + ".")
    L += ["", "| Ticker | F0 | F0T | F1 | F2 | F3 | Rango ultimo tramo | Riesgo S20 | Riesgo S10 | Riesgo S5 | Riesgo S8 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    ok = lambda b: "si" if b else "-"
    for x in hoy["lista"]:
        L.append(f"| {x['ticker']} | " + " | ".join(ok(x[k]) for k in FORMAS) + f" | {x['rango_ult_tramo_pct']}% | {x['riesgo_S20_pct']}% | {x['riesgo_S10_pct']}% | {x['riesgo_S5_pct']}% | {x['riesgo_S8_pct']}% |")
    L += ["", "## 2. Forma x stop (mismo criterio de ruptura)", "", "| Definicion | n | Riesgo prom % | % toco el stop | Retorno prom % (IC 95%) | Mediana % | % ganadoras | R prom |", "|---|---|---|---|---|---|---|---|"]
    for f in FORMAS:
        for s in STOPS:
            d = res["definiciones"].get(f"{f}+{s}")
            if d and d["n"]:
                L.append(f"| {_nom(f + '+' + s)} | {d['n']} | {d['riesgo_prom']} | {d['pct_parado']} | {d['ret_prom']} {d.get('ret_prom_ic95') or ''} | {d['ret_mediana']} | {d['pct_ganadoras']} | {d['R_prom']} |")
    L += ["", "## 3. Estabilidad: primera y segunda mitad del periodo (stop 10 y stop 20)", "", "| Definicion | Mitad | n | Retorno prom % | % ganadoras | R prom |", "|---|---|---|---|---|---|"]
    for k, d in res["por_mitad"].items():
        for m in ("primera", "segunda"):
            x = d[m]
            if x["n"]:
                L.append(f"| {_nom(k)} | {m} (corte {d['corte']}) | {x['n']} | {x['ret_prom']} | {x['pct_ganadoras']} | {x['R_prom']} |")
    L += ["", "## 4. Por riesgo inicial (stop 10)", "", "| Definicion | Riesgo | n | % toco el stop | Retorno prom % | % ganadoras | R prom |", "|---|---|---|---|---|---|---|"]
    for k, grupos in res["por_riesgo"].items():
        for c in ("hasta 8%", "8 a 10%", "mas de 10%"):
            d = grupos.get(c)
            if d and d["n"]:
                L.append(f"| {_nom(k)} | {c} | {d['n']} | {d['pct_parado']} | {d['ret_prom']} | {d['pct_ganadoras']} | {d['R_prom']} |")
    L += ["", "## 5. Umbral de volumen de la ruptura (stop 10)", "", "| Definicion | Condicion | n | Retorno prom % | % ganadoras | R prom |", "|---|---|---|---|---|---|"]
    for k, grupos in res["por_volumen"].items():
        for c, d in grupos.items():
            if d["n"]:
                L.append(f"| {_nom(k)} | {c} | {d['n']} | {d['ret_prom']} | {d['pct_ganadoras']} | {d['R_prom']} |")
    L += ["", "## Como leerlo", "",
          "- Un stop mas cercano baja el riesgo pero lo tocan mas seguido: importa el retorno en multiplos del riesgo (R) y que se repita en las dos mitades, no una columna sola.",
          "- Con menos de 30 casos no concluir nada. Las formas estrictas (F2, F3) dan pocos casos. El intervalo del promedio subestima la incertidumbre porque los casos se agrupan en los mismos dias de mercado.",
          "- El retorno simulado no es una recomendacion ni incluye costos; sirve solo para comparar definiciones.",
          "- Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un solo regimen, RS aproximado con retorno de 126 ruedas, umbrales elegidos por mi."]
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
    cols = [t for t in C.columns if t != bench and V[t].notna().sum() > 200]
    C2, V2 = C[cols], V[cols]
    S = v1._senales(C2, V2)
    formas, pl = _formas(C2, V2, S)
    df = _eventos(C2, V2, S, formas)
    res = analizar(df)
    hoy = _hoy(C2, V2, S, formas, pl)
    f0, f1 = C.index[0].strftime("%Y-%m-%d"), C.index[-1].strftime("%Y-%m-%d")
    if guardar:
        with open(RUTA_JSON, "w", encoding="utf-8") as f:
            json.dump(dict(generado=f1, universo=len(cols), resultados=res, hoy=hoy), f, ensure_ascii=False, indent=1)
        with open(RUTA_MD, "w", encoding="utf-8") as f:
            f.write(_md(res, hoy, len(cols), f0, f1))
    return res, hoy, df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
