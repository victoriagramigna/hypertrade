"""
Medias de 200: ¿SMA200 o EMA200? -- registro aparte, de solo agregado.

Pregunta de Victoria (11/10): para evaluar entradas y salidas, ¿cual de las dos medias de 200 ruedas
avisa mejor? Este script anota cada vez que un ticker CRUZA su SMA200 o su EMA200 (cierre diario) y
mide despues como le fue contra el SPY.

Usa solo data/cierres_diarios.jsonl (ya existente). NO toca el radar, ni ultimo.json, ni la Auditoria.
Escribe:
  data/log_medias200.jsonl   (append-only; una linea por cruce; id M200-{T}-{fecha}-{tipo})
  data/medias200_eval.json   (se recalcula entero en cada corrida)
Tipos: sma_pierde / ema_pierde (cierre pasa de arriba a abajo), sma_recupera / ema_recupera (de abajo a arriba).
Los cruces de fechas viejas se reconstruyen desde los cierres guardados (marcados "reconstruido": true);
de ahi en mas se anotan solos, dia a dia. Informativo: no cambia ninguna alerta ni recomendacion.
"""
import json, os, sys
from datetime import datetime, timezone, timedelta
import pandas as pd

RUTA_CIERRES = "data/cierres_diarios.jsonl"
RUTA_LOG = "data/log_medias200.jsonl"
RUTA_EVAL = "data/medias200_eval.json"
BENCH = "SPY"
HORIZONTES = (1, 5, 10, 20)       # ruedas
FALSA_ALARMA_RUEDAS = 5
VENTANA_ADELANTO = 20
TIPOS = ("sma_pierde", "ema_pierde", "sma_recupera", "ema_recupera")


def cargar_cierres():
    filas = {}
    with open(RUTA_CIERRES, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                d = json.loads(linea)
                filas[d["fecha"]] = d["c"]
    df = pd.DataFrame.from_dict(filas, orient="index").sort_index()
    df.index = pd.to_datetime(df.index)
    return df.ffill(limit=3)


def eventos(df):
    """Devuelve lista de dicts con cada cruce detectado."""
    sma = df.rolling(200, min_periods=200).mean()
    ema = df.ewm(span=200, adjust=False, min_periods=200).mean()
    out = []
    for nombre, ma in (("sma", sma), ("ema", ema)):
        debajo = (df < ma).where(ma.notna() & df.notna())
        prev = debajo.shift(1)
        baja = (debajo == True) & (prev == False)      # noqa: E712
        sube = (debajo == False) & (prev == True)      # noqa: E712
        for tipo, mask in ((f"{nombre}_pierde", baja), (f"{nombre}_recupera", sube)):
            ys, xs = mask.values.nonzero()
            for i, j in zip(ys, xs):
                t = df.columns[j]
                if t == BENCH:
                    continue
                fecha = df.index[i]
                out.append({
                    "ticker": t, "fecha": fecha.strftime("%Y-%m-%d"), "tipo": tipo,
                    "cierre": round(float(df.iloc[i, j]), 2),
                    "sma200": round(float(sma.iloc[i, j]), 2) if pd.notna(sma.iloc[i, j]) else None,
                    "ema200": round(float(ema.iloc[i, j]), 2) if pd.notna(ema.iloc[i, j]) else None,
                    "dist_sma_%": round((df.iloc[i, j] / sma.iloc[i, j] - 1) * 100, 2) if pd.notna(sma.iloc[i, j]) else None,
                    "dist_ema_%": round((df.iloc[i, j] / ema.iloc[i, j] - 1) * 100, 2) if pd.notna(ema.iloc[i, j]) else None,
                })
    return out


def leer_log():
    if not os.path.exists(RUTA_LOG):
        return []
    res = []
    with open(RUTA_LOG, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea:
                try:
                    res.append(json.loads(linea))
                except json.JSONDecodeError:
                    pass
    return res


def registrar(evs, hoy=None):
    existentes = {r.get("id") for r in leer_log()}
    hoy = hoy or datetime.now(timezone.utc).date()
    limite = (hoy - timedelta(days=3)).strftime("%Y-%m-%d")
    nuevos = []
    for e in sorted(evs, key=lambda x: (x["fecha"], x["ticker"], x["tipo"])):
        i = f"M200-{e['ticker']}-{e['fecha']}-{e['tipo']}"
        if i in existentes:
            continue
        nuevos.append({"id": i, **e, "reconstruido": e["fecha"] < limite})
    if nuevos:
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            for r in nuevos:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(nuevos)


def evaluar(df):
    log = {r["id"]: r for r in leer_log()}.values()
    fechas = list(df.index)
    pos = {d.strftime("%Y-%m-%d"): k for k, d in enumerate(fechas)}
    spy = df[BENCH]
    res = {t: {"n": 0, "reconstruidos": 0, "h": {h: [] for h in HORIZONTES}, "falsas": [0, 0]} for t in TIPOS}
    porticker = {}
    for r in log:
        t, tipo, k = r["ticker"], r["tipo"], pos.get(r["fecha"])
        if k is None or t not in df.columns or tipo not in res:
            continue
        g = res[tipo]; g["n"] += 1; g["reconstruidos"] += 1 if r.get("reconstruido") else 0
        porticker.setdefault((t, tipo), []).append(k)
        p0, s0 = df[t].iloc[k], spy.iloc[k]
        for h in HORIZONTES:
            if k + h < len(fechas):
                p1, s1 = df[t].iloc[k + h], spy.iloc[k + h]
                if pd.notna(p0) and pd.notna(p1) and pd.notna(s0) and pd.notna(s1):
                    g["h"][h].append(((p1 / p0 - 1) * 100, (s1 / s0 - 1) * 100))
        # falsa alarma: a una "pierde" le sigue un cierre sobre la misma media dentro de N ruedas (y al reves)
        if tipo.endswith("_pierde") or tipo.endswith("_recupera"):
            if k + FALSA_ALARMA_RUEDAS < len(fechas):
                ma = (df[t].rolling(200, min_periods=200).mean() if tipo.startswith("sma") else df[t].ewm(span=200, adjust=False, min_periods=200).mean())
                ventana = df[t].iloc[k + 1:k + 1 + FALSA_ALARMA_RUEDAS] > ma.iloc[k + 1:k + 1 + FALSA_ALARMA_RUEDAS]
                vuelve = bool(ventana.any()) if tipo.endswith("_pierde") else bool((~ventana).any())
                g["falsas"][1] += 1; g["falsas"][0] += 1 if vuelve else 0

    def resumen(g):
        o = {"n": g["n"], "reconstruidos": g["reconstruidos"], "h": {}}
        for h, v in g["h"].items():
            if v:
                ex = [a - b for a, b in v]
                o["h"][str(h)] = {"n": len(v), "ret_medio": round(sum(a for a, _ in v) / len(v), 2),
                                  "exceso_medio": round(sum(ex) / len(ex), 2),
                                  "pct_le_gana": round(100 * sum(1 for x in ex if x > 0) / len(ex), 0),
                                  "pct_cae": round(100 * sum(1 for a, _ in v if a < 0) / len(v), 0)}
        n_f = g["falsas"][1]
        o["falsas_alarmas"] = {"n": n_f, "pct": round(100 * g["falsas"][0] / n_f, 0) if n_f else None}
        return o

    # ¿cual avisa primero? (solo cruces hacia abajo, mismo ticker, dentro de 20 ruedas)
    ade = {"ema_primero": 0, "sma_primero": 0, "mismo_dia": 0, "solo_ema": 0, "solo_sma": 0, "dias_medio_ventaja_ema": None}
    difs = []
    tickers = {t for (t, _) in porticker}
    for t in tickers:
        for ke in porticker.get((t, "ema_pierde"), []):
            cand = [ks for ks in porticker.get((t, "sma_pierde"), []) if abs(ks - ke) <= VENTANA_ADELANTO]
            if not cand:
                ade["solo_ema"] += 1; continue
            ks = min(cand, key=lambda x: abs(x - ke))
            if ks > ke: ade["ema_primero"] += 1; difs.append(ks - ke)
            elif ks < ke: ade["sma_primero"] += 1; difs.append(ks - ke)
            else: ade["mismo_dia"] += 1
        for ks in porticker.get((t, "sma_pierde"), []):
            if not any(abs(ks - ke) <= VENTANA_ADELANTO for ke in porticker.get((t, "ema_pierde"), [])):
                ade["solo_sma"] += 1
    if difs:
        ade["dias_medio_ventaja_ema"] = round(sum(difs) / len(difs), 1)
    fechas_log = sorted(r["fecha"] for r in log)
    return {
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "ultimo_cierre": fechas[-1].strftime("%Y-%m-%d") if fechas else None,
        "primera": fechas_log[0] if fechas_log else None, "ultima": fechas_log[-1] if fechas_log else None,
        "registros": len(fechas_log),
        "tipos": {t: resumen(res[t]) for t in TIPOS},
        "adelanto": ade,
        "horizontes": list(HORIZONTES), "falsa_alarma_ruedas": FALSA_ALARMA_RUEDAS, "ventana_adelanto": VENTANA_ADELANTO,
        "nota": ("Cruces de la SMA200 y de la EMA200 de cada ticker (cierre diario). 'Exceso' = rendimiento del ticker menos el del SPY a las N ruedas. "
                 "'Falsa alarma' = a las 5 ruedas el precio volvio al lado anterior de la misma media. Los cruces con fecha vieja se reconstruyeron desde los "
                 "cierres guardados (hay pocos meses de historia); los nuevos se anotan dia a dia. Informativo, no es una recomendacion."),
    }


def correr():
    df = cargar_cierres()
    if BENCH not in df.columns or len(df) < 210:
        print("Pocos cierres para una media de 200 -- se omite"); return
    n = registrar(eventos(df))
    ev = evaluar(df)
    with open(RUTA_EVAL, "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print(f"{n} cruces nuevos; {ev['registros']} en el registro")


if __name__ == "__main__":
    correr()
