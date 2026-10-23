"""Perfil de las alertas que rindieron: que datos tenian en comun al momento de la alerta.

Solo LEE data/log_alertas.jsonl y data/auditoria_resultados.jsonl. No toca el radar ni la Auditoria.
Escribe data/perfiles.json, data/perfiles_resumen.md y agrega UNA linea a data/log_perfiles.jsonl (append-only).

Metodo (exploratorio, para generar hipotesis, no reglas):
 - "Gano" = rindio mas que el SPY a 20 ruedas (vs_spy20 > 0).
 - Por cada grupo de alerta y cada dato numerico: AUC (0.5 = no distingue; 1 = los que ganaron siempre tenian mas).
 - p por permutacion (se mezclan las etiquetas ganó/perdió) y chequeo en las dos mitades por fecha.
 - Se prueban muchos datos a la vez: un dato es CANDIDATO solo si p < P_MAX (corregido por cantidad de datos),
   |AUC-0.5| >= AUC_MIN, la misma direccion en las dos mitades y hay muestra suficiente.
 - Los casos del mismo dia no son independientes: la confianza real es menor que la del p.
"""
import json, os, random, statistics as st, collections, datetime as dt

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
RES = os.path.join(DATA, "auditoria_resultados.jsonl")
LOG = os.path.join(DATA, "log_alertas.jsonl")
OUT_JSON = os.path.join(DATA, "perfiles.json")
OUT_MD = os.path.join(DATA, "perfiles_resumen.md")
OUT_LOG = os.path.join(DATA, "log_perfiles.jsonl")

OBJETIVO = "vs_spy20"
MIN_GRUPO = 25          # casos con resultado para analizar un grupo solo (con menos solo entra en TODAS)
MIN_POR_LADO = 8        # ganadores y perdedores con dato, como minimo
MIN_POR_MITAD = 8
AUC_MIN = 0.15          # |AUC - 0.5| minimo para llamarlo candidato
P_MAX_BASE = 0.05       # se divide por la cantidad de datos probados (Bonferroni)
PERMUTACIONES = 3000
FEATURES = ["radar_score", "rs_score", "vol_rel", "rsi", "dist_max52w_pct", "var_dia_pct",
            "var_spy_dia_pct", "regimen_score", "atr_contraction", "pendiente_ok",
            "apoyo_avwap", "cruce_avwap_52w", "vcp_valido"]


def leer(path):
    if not os.path.exists(path):
        return []
    out = []
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if l:
            try:
                out.append(json.loads(l))
            except Exception:
                pass
    return out


def limpio(s):
    return "".join(ch for ch in (s or "") if ch.isalnum() or ch == " ")


def num(v):
    if isinstance(v, bool):
        return float(v)
    return float(v) if isinstance(v, (int, float)) and v == v else None


def unir():
    res, log = leer(RES), leer(LOG)
    idx = collections.defaultdict(list)
    for r in log:
        idx[(r.get("ticker"), (r.get("timestamp") or "")[:10])].append(r)
    filas = []
    for r in res:
        if r.get(OBJETIVO) is None:
            continue
        c = idx.get((r["ticker"], r["fecha"]), [])
        palabras = limpio(r["señal"]).split()[:2]
        m = [x for x in c if all(w in limpio(x.get("estado")) for w in palabras)] or c
        if not m:
            continue
        f = dict(m[0]); f.update(r)
        filas.append(f)
    return filas


def auc(pos, neg):
    """AUC por rangos (Mann-Whitney), con empates promediados."""
    todo = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg], key=lambda t: t[0])
    n = len(todo); rangos = [0.0] * n; i = 0
    while i < n:
        j = i
        while j + 1 < n and todo[j + 1][0] == todo[i][0]:
            j += 1
        for k in range(i, j + 1):
            rangos[k] = (i + j) / 2 + 1
        i = j + 1
    sp = sum(rangos[k] for k in range(n) if todo[k][1] == 1)
    return (sp - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def p_perm(pos, neg, rng):
    obs = abs(auc(pos, neg) - 0.5); al = pos + neg; k = len(pos); c = 0
    for _ in range(PERMUTACIONES):
        rng.shuffle(al)
        if abs(auc(al[:k], al[k:]) - 0.5) >= obs:
            c += 1
    return (c + 1) / (PERMUTACIONES + 1)


def valores(sub, f):
    gan = [num(x.get(f)) for x in sub if x[OBJETIVO] > 0]
    per = [num(x.get(f)) for x in sub if x[OBJETIVO] <= 0]
    return [v for v in gan if v is not None], [v for v in per if v is not None]


def analizar_grupo(nombre, sub, rng):
    fechas = sorted(x["fecha"] for x in sub)
    corte = fechas[len(fechas) // 2]
    mit1 = [x for x in sub if x["fecha"] < corte]; mit2 = [x for x in sub if x["fecha"] >= corte]
    ganan = sum(1 for x in sub if x[OBJETIVO] > 0)
    out = {"grupo": nombre, "n": len(sub), "ganan": ganan, "pierden": len(sub) - ganan,
           "mediana_vs_spy20": round(st.median([x[OBJETIVO] for x in sub]), 2),
           "dias_distintos": len({x["fecha"] for x in sub}), "datos": []}
    p_max = P_MAX_BASE / len(FEATURES)
    for f in FEATURES:
        g, p = valores(sub, f)
        if len(g) < MIN_POR_LADO or len(p) < MIN_POR_LADO:
            continue
        a = auc(g, p)
        pv = p_perm(g, p, rng)
        a1 = a2 = None
        g1, p1 = valores(mit1, f); g2, p2 = valores(mit2, f)
        if min(len(g1), len(p1), len(g2), len(p2)) >= MIN_POR_MITAD // 2 and len(g1) + len(p1) >= MIN_POR_MITAD and len(g2) + len(p2) >= MIN_POR_MITAD:
            a1, a2 = auc(g1, p1), auc(g2, p2)
        consistente = a1 is not None and (a1 - 0.5) * (a - 0.5) > 0 and (a2 - 0.5) * (a - 0.5) > 0
        cand = pv < p_max and abs(a - 0.5) >= AUC_MIN and consistente
        out["datos"].append({"dato": f, "auc": round(a, 3), "p": round(pv, 4),
                             "mediana_ganan": round(st.median(g), 2), "mediana_pierden": round(st.median(p), 2),
                             "n_ganan": len(g), "n_pierden": len(p),
                             "auc_mitad1": None if a1 is None else round(a1, 3),
                             "auc_mitad2": None if a2 is None else round(a2, 3),
                             "consistente": consistente, "candidato": cand})
    out["datos"].sort(key=lambda d: -abs(d["auc"] - 0.5))
    out["candidatos"] = [d for d in out["datos"] if d["candidato"]]
    return out


def main():
    filas = unir()
    rng = random.Random(7)
    grupos = collections.defaultdict(list)
    for x in filas:
        grupos[x["señal"]].append(x)
    res = []
    if len(filas) >= MIN_GRUPO:
        res.append(analizar_grupo("TODAS", filas, rng))
    for nombre, sub in sorted(grupos.items(), key=lambda t: -len(t[1])):
        if len(sub) >= MIN_GRUPO:
            res.append(analizar_grupo(nombre, sub, rng))
    chicos = {k: len(v) for k, v in grupos.items() if len(v) < MIN_GRUPO}
    hoy = dt.datetime.now(dt.timezone.utc)
    doc = {"generado_utc": hoy.isoformat(), "objetivo": "rendir mas que el SPY a 20 ruedas",
           "casos": len(filas), "grupos_con_muestra_chica": chicos,
           "reglas": {"min_grupo": MIN_GRUPO, "auc_min": AUC_MIN, "p_max": round(P_MAX_BASE / len(FEATURES), 4)},
           "grupos": res}
    json.dump(doc, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    md = [f"# Perfil de las alertas que rindieron ({hoy.date()})", "",
          f"Casos con resultado a 20 ruedas: {len(filas)}. Exploratorio: genera hipotesis, no reglas. Informativo.", "",
          f"Candidato = p < {doc['reglas']['p_max']} (corregido por {len(FEATURES)} datos), |AUC-0.5| >= {AUC_MIN}, misma direccion en las dos mitades por fecha.",
          "AUC 0.5 = no distingue; mayor a 0.5 = los que ganaron tenian MAS de ese dato.", ""]
    for g in res:
        md.append(f"## {g['grupo']}: {g['n']} casos ({g['ganan']} ganan vs SPY, {g['pierden']} pierden), {g['dias_distintos']} dias distintos, mediana vs SPY {g['mediana_vs_spy20']}")
        md += ["", "| Dato | AUC | p | mediana ganan | mediana pierden | mitad 1 | mitad 2 | candidato |", "|---|---|---|---|---|---|---|---|"]
        for d in g["datos"][:6]:
            md.append(f"| {d['dato']} | {d['auc']} | {d['p']} | {d['mediana_ganan']} | {d['mediana_pierden']} | {d['auc_mitad1']} | {d['auc_mitad2']} | {'SI' if d['candidato'] else 'no'} |")
        md.append("")
    if chicos:
        md.append("Sin analizar por muestra chica: " + ", ".join(f"{k} ({v})" for k, v in chicos.items()))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")

    linea = {"fecha": str(hoy.date()), "casos": len(filas),
             "grupos": [{"grupo": g["grupo"], "n": g["n"], "candidatos": [
                 {"dato": d["dato"], "auc": d["auc"], "p": d["p"]} for d in g["candidatos"]]} for g in res]}
    with open(OUT_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(linea, ensure_ascii=False) + "\n")
    print(f"Perfiles: {len(filas)} casos, {len(res)} grupos analizados")
    for g in res:
        print(" ", g["grupo"], g["n"], "candidatos:", [(d["dato"], d["auc"]) for d in g["candidatos"]])


if __name__ == "__main__":
    main()
