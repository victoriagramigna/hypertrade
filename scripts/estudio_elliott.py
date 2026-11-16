"""
Estudio de ondas de Elliott (conteo MECANICO) v2 -- descriptivo, aparte y aditivo.

NO toca el radar, la app, la Auditoria ni ninguna lista. Se corre a mano desde Actions ("Estudio Elliott").
Baja ~2 anios de OHLC y volumen de Yahoo (mismo universo del radar) y escribe data/estudio_elliott.json y
data/estudio_elliott_resumen.md.

Que mide. Usa los giros REALES (maximos/minimos del dia confirmados K ruedas despues, igual que el Estudio VCP v4:
nunca se mira el futuro) y busca, dia por dia, secuencias que cumplan las reglas "duras" de un impulso.
Las longitudes de onda se miden en ESCALA LOGARITMICA (ln del precio), como dice usar el autor del hilo.
  * Setup ONDA 3 (se confirma el minimo de la onda 2):  L0 -> H1 -> L2
      - onda 1 >= 5%; L2 sobre L0 (la onda 2 no pasa del inicio de la 1); la onda 2 retrocede 23,6% a 78,6% de la 1.
      - Entrada hipotetica: cierre del dia de confirmacion. Invalidacion: L2.
      - Objetivos (desde L2): 100%, 161,8%, 200%, 261,8% de la onda 1. El principal es 161,8%.
  * Setup ONDA 5 (se confirma el minimo de la onda 4):  L0 -> H1 -> L2 -> H3 -> L4
      - lo anterior, mas: H3 > H1, onda 3 mayor que la 1 (version estricta de "la 3 no es la mas corta": en la
        entrada la onda 5 todavia no existe), L4 sobre H1 (sin superposicion), onda 4 retrocede 23,6% a 50% de la 3.
      - Entrada hipotetica: cierre del dia de confirmacion. Invalidacion: L4.
      - Objetivos (desde L4): 61,8%, 100%, 161,8% de la onda 1. El principal es 100%.
  * CONTROL: cualquier minimo confirmado con el cierre sobre la media de 50 ruedas (sin reglas de Elliott), con la
    misma entrada y la misma invalidacion (el minimo).
  Sin modelar: diagonales (permiten superposicion 1-4), zigzag/flat/triangulo/combinaciones y subdivision interna
  en 5 o 3 ondas: son demasiado subjetivos para medirlos con velas diarias.

HIPOTESIS FIJADAS DE ANTEMANO (no se agregan otras despues de ver los resultados; cada una se mira en las dos mitades
del periodo, por fecha, y solo cuenta si va en el mismo sentido en las dos):
  H1  ONDA5 contra CONTROL (exceso a 20 ruedas contra SPY).
  H2  ONDA5 con ALTERNANCIA (onda 2 profunda, retroceso >= 50%, y onda 4 superficial, <= 38,2%) contra sin ella.
  H3  ONDA5 con RSI(14) >= 70 en el maximo de la onda 3 contra sin eso.
  H4  ONDA5 con volumen promedio de la onda 3 mayor que el de la onda 1 contra sin eso.
  H5  ONDA3 con onda 2 profunda (retroceso >= 50% de la onda 1) contra superficial.
  H6  ONDA3 con volumen promedio de la onda 2 menor que el de la onda 1 contra sin eso.
Como son 6 comparaciones, los intervalos se muestran al 99% (no al 95%).
Mide a 5/10/20 ruedas el retorno y el exceso contra SPY (cierre), y que ocurre primero en 20 ruedas para cada
objetivo: objetivo, invalidacion (el MINIMO del dia toca el nivel; si el mismo dia toca ambos se cuenta la
invalidacion) o ninguno. Un solo evento por activo cada 20 ruedas.

Limites (decirlo siempre): el conteo de Elliott es subjetivo; esto es UNA forma mecanica y estricta de contarlo.
Universo actual (sesgo de supervivencia), ~1 anio de eventos utiles en un solo regimen, eventos de activos distintos
el mismo dia estan correlacionados (los intervalos son optimistas), umbrales y proporciones elegidos por mi, no
validados. Un resultado aca NO prueba que sirva ni que no sirva.
"""
import json
import logging
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "scripts")
import estudio_vcp_v4 as v4

log = logging.getLogger("radar.estudio_elliott")
RUTA_JSON = "data/estudio_elliott.json"
RUTA_MD = "data/estudio_elliott_resumen.md"

K_PRINCIPAL = 5
K_SENSIBILIDAD = (3, 8)
HORIZONTES = (5, 10, 20)
SEPARACION = 20
MIN_HIST = 252
MIN_ONDA1 = np.log(1.05)
RETR2 = (0.236, 0.786)
RETR4 = (0.236, 0.5)
OBJ3 = (1.0, 1.618, 2.0, 2.618)
OBJ5 = (0.618, 1.0, 1.618)
PRINCIPAL = {"ONDA3": 1.618, "ONDA5": 1.0}
GRUPOS = ["ONDA3", "ONDA5", "CONTROL"]
Z99 = 2.576

# (id, descripcion, grupo, columna booleana)
HIPOTESIS = [
    ("H2", "ONDA5 con alternancia (onda 2 >= 50% y onda 4 <= 38,2%)", "ONDA5", "alternancia"),
    ("H3", "ONDA5 con RSI >= 70 en el maximo de la onda 3", "ONDA5", "rsi_h3_70"),
    ("H4", "ONDA5 con volumen de la onda 3 mayor que el de la onda 1", "ONDA5", "vol3_mayor_vol1"),
    ("H5", "ONDA3 con onda 2 profunda (>= 50%)", "ONDA3", "onda2_profunda"),
    ("H6", "ONDA3 con volumen de la onda 2 menor que el de la onda 1", "ONDA3", "vol2_menor_vol1"),
]


def _rsi(c, n=14):
    s = pd.Series(c)
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).values


def _vol_tramo(v, i0, i1):
    seg = v[i0:i1 + 1]
    seg = seg[~np.isnan(seg)]
    return float(seg.mean()) if len(seg) else np.nan


def _setup(zz, vol, rsi):
    """Con el zigzag causal hasta hoy (ultimo giro = minimo): lista de (grupo, invalidacion, {mult: objetivo}, rasgos)."""
    if not zz or zz[-1][0] != "L":
        return []
    out = []
    if len(zz) >= 3 and [x[0] for x in zz[-3:]] == ["L", "H", "L"]:
        (_, i0, l0), (_, i1, h1), (_, i2, l2) = zz[-3:]
        w1 = np.log(h1 / l0)
        if l0 > 0 and w1 >= MIN_ONDA1 and l2 > l0:
            r2 = (np.log(h1) - np.log(l2)) / w1
            if RETR2[0] <= r2 <= RETR2[1]:
                v1, v2 = _vol_tramo(vol, i0, i1), _vol_tramo(vol, i1, i2)
                rasgos = {"retr2": round(float(r2), 3), "onda2_profunda": bool(r2 >= 0.5),
                          "vol2_menor_vol1": bool(v2 < v1) if v1 == v1 and v2 == v2 else None}
                out.append(("ONDA3", l2, {m: l2 * float(np.exp(m * w1)) for m in OBJ3}, rasgos))
    if len(zz) >= 5 and [x[0] for x in zz[-5:]] == ["L", "H", "L", "H", "L"]:
        (_, i0, l0), (_, i1, h1), (_, i2, l2), (_, i3, h3), (_, i4, l4) = zz[-5:]
        w1, w3 = np.log(h1 / l0), np.log(h3 / l2)
        if l0 > 0 and w1 >= MIN_ONDA1 and l2 > l0 and h3 > h1 and w3 > w1 and l4 > h1:
            r2 = (np.log(h1) - np.log(l2)) / w1
            r4 = (np.log(h3) - np.log(l4)) / w3
            if RETR2[0] <= r2 <= RETR2[1] and RETR4[0] <= r4 <= RETR4[1]:
                v1, v3 = _vol_tramo(vol, i0, i1), _vol_tramo(vol, i2, i3)
                rasgos = {"retr2": round(float(r2), 3), "retr4": round(float(r4), 3),
                          "alternancia": bool(r2 >= 0.5 and r4 <= 0.382),
                          "rsi_h3": round(float(rsi[i3]), 1) if rsi[i3] == rsi[i3] else None,
                          "rsi_h3_70": bool(rsi[i3] >= 70) if rsi[i3] == rsi[i3] else None,
                          "rsi_l4": round(float(rsi[i4]), 1) if rsi[i4] == rsi[i4] else None,
                          "vol3_mayor_vol1": bool(v3 > v1) if v1 == v1 and v3 == v3 else None}
                out.append(("ONDA5", l4, {m: l4 * float(np.exp(m * w1)) for m in OBJ5}, rasgos))
    return out


def _resultado(O, H, L, C, spy, t, inv, objs):
    n = len(C)
    e = C[t]
    if not (e > inv > 0):
        return None
    fila = {"riesgo_pct": round((e / inv - 1) * 100, 2)}
    for h in HORIZONTES:
        if t + h < n and not np.isnan(C[t + h]) and not np.isnan(spy[t + h]) and spy[t]:
            r = C[t + h] / e - 1
            fila[f"ret{h}"] = r * 100
            fila[f"exc{h}"] = (r - (spy[t + h] / spy[t] - 1)) * 100
    if t + 20 < n:
        for m, obj in (objs or {"x": None}).items():
            res = "ninguno"
            for j in range(t + 1, t + 21):
                if L[j] <= inv:
                    res = "invalidacion"
                    break
                if obj is not None and H[j] >= obj:
                    res = "objetivo"
                    break
            fila[f"primero_{m}"] = res
    return fila


def _eventos(O, H, L, C, V, spy, K):
    filas = []
    idx = C.index
    for t_col in C.columns:
        h, l, c, o, vv = H[t_col].values, L[t_col].values, C[t_col].values, O[t_col].values, V[t_col].values.astype(float)
        if np.isnan(c).sum() > len(c) * 0.2 or len(c) < MIN_HIST + 60:
            continue
        c_f = pd.Series(c).ffill().values
        sma50 = pd.Series(c_f).rolling(50).mean().values
        rsi = _rsi(c_f)
        giros = v4._giros(np.nan_to_num(h, nan=0.0), np.where(np.isnan(l), 1e12, l), K)
        zz = []
        ultimo = {g: -10**9 for g in GRUPOS}
        for d in sorted(giros):
            v4._agregar(zz, giros[d])
            if d < MIN_HIST - 60 or zz[-1][0] != "L" or np.isnan(c_f[d]):
                continue
            cands = _setup(zz, vv, rsi)
            if not np.isnan(sma50[d]) and c_f[d] > sma50[d]:
                cands = cands + [("CONTROL", zz[-1][2], None, {})]
            for grupo, inv, objs, rasgos in cands:
                if d - ultimo[grupo] < SEPARACION:
                    continue
                r = _resultado(o, h, l, c_f, spy, d, inv, objs)
                if r is None:
                    continue
                ultimo[grupo] = d
                r["primero"] = r.get(f"primero_{PRINCIPAL[grupo]}") if grupo in PRINCIPAL else r.get("primero_x")
                r.update(rasgos)
                r.update({"ticker": t_col, "grupo": grupo, "fecha": str(idx[d])[:10], "K": K})
                filas.append(r)
    return pd.DataFrame(filas)


def _media_ic(x, z):
    x = pd.Series(x).dropna()
    if not len(x):
        return None
    se = x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan
    return dict(n=int(len(x)), exc_prom=round(float(x.mean()), 2),
                ic=[round(float(x.mean() - z * se), 2), round(float(x.mean() + z * se), 2)] if se == se else None)


def _stats(g):
    out = {"n": int(len(g))}
    for h in HORIZONTES:
        x = g[f"exc{h}"].dropna() if f"exc{h}" in g else pd.Series(dtype=float)
        r = g[f"ret{h}"].dropna() if f"ret{h}" in g else pd.Series(dtype=float)
        if len(x):
            se = x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan
            out[f"h{h}"] = dict(n=int(len(x)), ret_med=round(float(r.median()), 2), ret_prom=round(float(r.mean()), 2),
                               exc_prom=round(float(x.mean()), 2), exc_med=round(float(x.median()), 2),
                               pct_exc_pos=round(float((x > 0).mean() * 100), 1),
                               ic95=[round(float(x.mean() - 1.96 * se), 2), round(float(x.mean() + 1.96 * se), 2)] if se == se else None)
    objs = {}
    for col in [c for c in g.columns if c.startswith("primero_")]:
        p = g[col].dropna()
        if len(p):
            objs[col.replace("primero_", "")] = {k: round(float((p == k).mean() * 100), 1) for k in ("objetivo", "invalidacion", "ninguno")} | {"n": int(len(p))}
    out["objetivos"] = objs
    out["riesgo_med_pct"] = round(float(g["riesgo_pct"].median()), 2) if len(g) else None
    return out


def _por_trimestre(g):
    if not len(g):
        return {}
    q = pd.to_datetime(g["fecha"]).dt.to_period("Q").astype(str)
    return {k: {"n": int(len(x)), "exc20": round(float(x["exc20"].mean()), 2) if "exc20" in x and x["exc20"].notna().any() else None}
            for k, x in g.groupby(q)}


def _hipotesis(df):
    """H1 (ONDA5 vs CONTROL) y H2-H6 (con/sin el rasgo), cada una en las dos mitades por fecha y en todo el periodo."""
    if not len(df):
        return {}
    corte = sorted(df["fecha"].unique())[len(df["fecha"].unique()) // 2]
    mitad = np.where(df["fecha"] < corte, "mitad1", "mitad2")
    df = df.assign(mitad=mitad)
    res = {"corte_fecha": corte}

    def trio(sel_a, sel_b):
        d = {}
        for nom, m in (("mitad1", df["mitad"] == "mitad1"), ("mitad2", df["mitad"] == "mitad2"), ("todo", df["mitad"].notna())):
            a, b = _media_ic(df.loc[sel_a & m, "exc20"], Z99), _media_ic(df.loc[sel_b & m, "exc20"], Z99)
            d[nom] = {"a": a, "b": b, "dif": round(a["exc_prom"] - b["exc_prom"], 2) if a and b else None}
        return d
    res["H1"] = dict(desc="ONDA5 contra CONTROL", **trio(df["grupo"] == "ONDA5", df["grupo"] == "CONTROL"))
    for hid, desc, grupo, col in HIPOTESIS:
        if col not in df.columns:
            continue
        g = df["grupo"] == grupo
        s = df[col].astype(object)
        res[hid] = dict(desc=desc, **trio(g & (s == True), g & (s == False)))  # noqa: E712
    for hid, v in res.items():
        if hid == "corte_fecha":
            continue
        d1, d2 = (v.get("mitad1") or {}).get("dif"), (v.get("mitad2") or {}).get("dif")
        v["mismo_sentido"] = bool(d1 is not None and d2 is not None and d1 * d2 > 0)
    return res


def _md(res, hip, sens, f0, f1, nt):
    L_ = ["# Estudio de ondas de Elliott v2 (conteo mecánico, escala logarítmica)\n",
          f"Datos: {f0} a {f1} · {nt} activos · giros de K={K_PRINCIPAL} ruedas (sensibilidad K={K_SENSIBILIDAD[0]} y K={K_SENSIBILIDAD[1]}).\n",
          "Es descriptivo: no valida ni descarta el método. Ver límites al final.\n"]
    for k, nombre in (("ONDA3", "Setup onda 3 (se confirma el mínimo de la onda 2)"), ("ONDA5", "Setup onda 5 (se confirma el mínimo de la onda 4)"),
                      ("CONTROL", "Control: mínimo confirmado sobre la media de 50, sin reglas de Elliott")):
        s = res.get(k, {})
        L_.append(f"\n## {nombre}\n")
        L_.append(f"Eventos: {s.get('n', 0)} · riesgo mediano hasta la invalidación: {s.get('riesgo_med_pct')}%\n")
        L_.append("| Horizonte | n | Retorno mediano | Exceso prom. vs SPY | Exceso mediano | % con exceso > 0 | IC95% del exceso |\n|---|---|---|---|---|---|---|")
        for h in HORIZONTES:
            x = s.get(f"h{h}")
            if x:
                L_.append(f"| {h} ruedas | {x['n']} | {x['ret_med']}% | {x['exc_prom']} | {x['exc_med']} | {x['pct_exc_pos']}% | {x['ic95']} |")
        ob = s.get("objetivos") or {}
        if ob and k != "CONTROL":
            L_.append("\nQué pasa primero en 20 ruedas, por objetivo (múltiplo de la onda 1):")
            for m, p in ob.items():
                L_.append(f"- {m}: objetivo {p['objetivo']}% · invalidación {p['invalidacion']}% · ninguno {p['ninguno']}% (n={p['n']})")
        elif ob:
            p = next(iter(ob.values()))
            L_.append(f"\nQué pasa primero en 20 ruedas (sin objetivo): invalidación {p['invalidacion']}% · ninguno {p['ninguno']}% (n={p['n']}).")
        tr = res.get("trimestres", {}).get(k)
        if tr:
            L_.append("\nPor trimestre (n y exceso a 20 ruedas): " + " · ".join(f"{q}: {v['n']} / {v['exc20']}" for q, v in tr.items()))
    L_.append(f"\n## Hipótesis fijadas de antemano (exceso a 20 ruedas, IC99%, corte de mitades: {hip.get('corte_fecha')})\n")
    L_.append("Solo vale lo que va en el mismo sentido en las dos mitades. Con tantas comparaciones, alguna puede salir por azar.\n")
    L_.append("| Hipótesis | Mitad 1 (con / sin) | Mitad 2 (con / sin) | Todo (con / sin) | Mismo sentido |\n|---|---|---|---|---|")
    fmt = lambda t: (f"{t['a']['exc_prom']} (n={t['a']['n']}) / {t['b']['exc_prom']} (n={t['b']['n']}) · dif {t['dif']}" if t and t.get('a') and t.get('b') else "sin datos suficientes")
    for hid in ("H1", "H2", "H3", "H4", "H5", "H6"):
        v = hip.get(hid)
        if v:
            L_.append(f"| {hid}: {v['desc']} | {fmt(v.get('mitad1'))} | {fmt(v.get('mitad2'))} | {fmt(v.get('todo'))} | {'sí' if v['mismo_sentido'] else 'no'} |")
    L_.append("\n## Sensibilidad al largo del giro (K)\n")
    for kk, d in sens.items():
        L_.append(f"- K={kk}: " + " · ".join(f"{g} n={d.get(g, {}).get('n', 0)} exceso20={((d.get(g, {}).get('h20') or {}).get('exc_prom'))}" for g in GRUPOS))
    L_.append("\n## Límites\n- El conteo de Elliott es subjetivo; esta es una sola forma mecánica y estricta de contarlo (sin diagonales, sin zigzag/flat/triángulo ni subdivisión interna).\n"
              "- Universo actual (sesgo de supervivencia); ~1 año de eventos útiles en un solo régimen de mercado.\n"
              "- Eventos de activos distintos en el mismo día están correlacionados: los intervalos son optimistas.\n"
              "- Umbrales y proporciones (5%, 23,6–78,6%, 1,618, onda 5 = onda 1, RSI 70, alternancia 50%/38,2%) elegidos por mí, no validados.\n"
              "- \"Onda 3 mayor que la onda 1\" es más estricta que la regla de Elliott (la 3 no es la más corta de 1, 3 y 5).\n"
              "- Salida simulada al nivel exacto de la invalidación/objetivo; no incluye comisiones ni deslizamiento.\n"
              "- No es una recomendación de compra ni de venta.\n")
    return "\n".join(L_)


def correr(datos=None, guardar=True):
    if datos is None:
        from config import TICKERS, BENCHMARK
        O, H, L, C, V = v4.descargar_ohlc(list(dict.fromkeys(list(TICKERS) + [BENCHMARK])))
        bench = BENCHMARK
    else:
        O, H, L, C, V = datos
        bench = "SPY"
    if bench not in C.columns or C.shape[1] < 30 or len(C) < MIN_HIST + 60:
        log.error("Pocos datos -- se aborta")
        sys.exit(1)
    spy = C[bench].ffill().values
    cols = [t for t in C.columns if t != bench and V[t].notna().sum() > 200]
    df = _eventos(O[cols], H[cols], L[cols], C[cols], V[cols], spy, K_PRINCIPAL)
    res = {g: _stats(df[df["grupo"] == g]) for g in GRUPOS} if len(df) else {g: {"n": 0} for g in GRUPOS}
    res["trimestres"] = {g: _por_trimestre(df[df["grupo"] == g]) for g in GRUPOS} if len(df) else {}
    hip = _hipotesis(df)
    sens = {K_PRINCIPAL: {g: res[g] for g in GRUPOS}}
    for k in K_SENSIBILIDAD:
        d_k = _eventos(O[cols], H[cols], L[cols], C[cols], V[cols], spy, k)
        sens[k] = {g: _stats(d_k[d_k["grupo"] == g]) if len(d_k) else {"n": 0} for g in GRUPOS}
    sens = dict(sorted(sens.items()))
    f0, f1 = C.index[0].strftime("%Y-%m-%d"), C.index[-1].strftime("%Y-%m-%d")
    if guardar:
        with open(RUTA_JSON, "w", encoding="utf-8") as f:
            json.dump(dict(generado=f1, universo=len(cols), K=K_PRINCIPAL, resultados=res, hipotesis=hip, sensibilidad=sens), f, ensure_ascii=False, indent=1, default=str)
        with open(RUTA_MD, "w", encoding="utf-8") as f:
            f.write(_md(res, hip, sens, f0, f1, len(cols)))
    return res, df, hip


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
