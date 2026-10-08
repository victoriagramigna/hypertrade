"""
Estudio histórico del "Gap alcista con macrotendencia" (pedido de Victoria, 8/10).

Pregunta: ¿se pueden detectar en la previa los CEDEARs que después disparan
Gap alcista? Y, sobre todo, ¿en los que NO son tan volátiles (no SATL, SPCE, etc.)?

Es un ESTUDIO aparte (ADITIVO):
  * no toca ninguna señal, el Radar Score ni la Auditoría;
  * no escribe nada de lo que usa el radar: solo crea data/estudio_gap.json y
    data/estudio_gap_resumen.md (se pisan en cada corrida del estudio);
  * se corre a mano desde GitHub Actions (workflow "Estudio Gap alcista").

Qué hace:
  1. Baja ~5 años de precios diarios de los CEDEARs del universo (+ SPY).
  2. Encuentra TODOS los gaps con la MISMA regla que el radar (alertas.py):
     suba de cierre a cierre >= UMBRAL_GAP_ALCISTA_PCT, ayer sobre su SMA200,
     y hoy es el cierre más alto de los últimos VENTANA_GAP_MAXIMO_DIAS.
  3. Para cada gap mide cómo estaba el papel el día ANTERIOR (lo que se
     podría haber visto en la previa) y qué pasó después (+1/+5/+10/+20 ruedas,
     contra SPY, y la peor caída en las 10 ruedas siguientes).
  4. Arma la tabla de "lift": de todos los días con macrotendencia, ¿cuánto
     más seguido aparece un gap en las 5 ruedas siguientes cuando el papel
     tiene cierta característica? Los cortes se calculan con la primera parte
     de la historia (entrenamiento) y se verifican en la última parte (prueba),
     para no engañarnos con algo que solo funcionó "mirando hacia atrás".
  5. Todo se informa por grupo de volatilidad (baja / media / alta).

Limitaciones honestas: el gap de cierre a cierre no es el gap de apertura; la
volatilidad se mide con el pasado; muchos gaps vienen de noticias o balances
que no se pueden ver antes. Esto mide cuánto SE PUEDE ver, no promete nada.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

log = logging.getLogger("estudio.gap")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# --- Mismos parámetros que el radar (config.py) ---
UMBRAL_GAP_ALCISTA_PCT = 3
VENTANA_GAP_MAXIMO_DIAS = 10
# --- Parámetros del estudio ---
PERIODO = "5y"
ENFRIAMIENTO_RUEDAS = 5          # un gap no cuenta como "nuevo" si hubo otro en las 5 ruedas previas
HORIZONTE_PREVIA = 5             # "se viene un gap" = hay un gap en las próximas 5 ruedas
FORWARD = (1, 5, 10, 20)
VOL_BAJA_MAX = 30.0              # % anualizado (60 ruedas): hasta acá = volatilidad baja
VOL_MEDIA_MAX = 50.0             # hasta acá = media; más = alta (SATL, SPCE, etc.)
FRACCION_ENTRENAMIENTO = 0.6
MIN_FILAS = 260
BENCHMARK = "SPY"
RUTA_SALIDA = "data/estudio_gap.json"
RUTA_RESUMEN = "data/estudio_gap_resumen.md"

FEATURES = {
    "dist_sma50_pct": "Distancia a la SMA50 (%)",
    "dist_sma200_pct": "Distancia a la SMA200 (%)",
    "dist_max52w_pct": "Distancia al máximo de 52 semanas (%)",
    "rsi14": "RSI diario (14)",
    "compresion_bb": "Compresión de Bollinger (ancho hoy / ancho típico del año; <1 = comprimido)",
    "rango10_pct": "Rango de las últimas 10 ruedas (% del precio; bajo = consolidando)",
    "vol_secado": "Volumen últimas 5 ruedas / promedio 60 (<1 = se secó)",
    "ret20_pct": "Retorno 20 ruedas (%)",
    "rs20_pct": "Retorno 20 ruedas menos el de SPY (puntos)",
    "atr_pct": "ATR 14 (% del precio)",
}


def _rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def calcular_ticker(df: pd.DataFrame, spy_close: pd.Series) -> pd.DataFrame:
    """df: Open/High/Low/Close/Volume diario. Devuelve una fila por rueda con
    características (con datos hasta ESA rueda) y marca de gap."""
    c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]
    out = pd.DataFrame(index=df.index)
    out["close"] = c
    sma20, sma50, sma200 = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    ret = c.pct_change() * 100
    out["ret_dia"] = ret
    out["dist_sma50_pct"] = (c / sma50 - 1) * 100
    out["dist_sma200_pct"] = (c / sma200 - 1) * 100
    out["dist_max52w_pct"] = (c / c.rolling(252, min_periods=200).max() - 1) * 100
    out["rsi14"] = _rsi(c)
    bbw = (c.rolling(20).std() * 4) / sma20
    out["compresion_bb"] = bbw / bbw.rolling(252, min_periods=120).median()
    out["rango10_pct"] = (c.rolling(10).max() - c.rolling(10).min()) / c * 100
    out["vol_secado"] = v.rolling(5).mean() / v.rolling(60).mean().replace(0, np.nan)
    out["ret20_pct"] = (c / c.shift(20) - 1) * 100
    spy = spy_close.reindex(df.index).ffill()
    out["spy_sobre_sma200"] = spy > spy.rolling(200).mean()
    out["rs20_pct"] = out["ret20_pct"] - (spy / spy.shift(20) - 1) * 100
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    out["atr_pct"] = tr.rolling(14).mean() / c * 100
    out["vol60_anual"] = ret.rolling(60).std() * np.sqrt(252)
    # Regla del radar (alertas.py), evaluada rueda por rueda
    macro_ok = (c.shift(1) > sma200.shift(1)) & sma200.shift(1).notna()
    es_max = c >= c.rolling(VENTANA_GAP_MAXIMO_DIAS).max() * 0.999
    out["macro_ok"] = macro_ok
    gap = (ret >= UMBRAL_GAP_ALCISTA_PCT) & macro_ok & es_max
    # enfriamiento: no contar gaps pegados a otro gap reciente
    previo = gap.shift(1, fill_value=False).rolling(ENFRIAMIENTO_RUEDAS, min_periods=1).max().astype(bool)
    out["gap"] = gap & ~previo
    # Qué pasó después
    spyc = spy.copy()
    for n in FORWARD:
        out[f"fwd{n}"] = (c.shift(-n) / c - 1) * 100
        out[f"alpha{n}"] = out[f"fwd{n}"] - (spyc.shift(-n) / spyc - 1) * 100
    peor = pd.concat([l.shift(-k) for k in range(1, 11)], axis=1).min(axis=1)
    out["peor_caida10"] = (peor / c - 1) * 100
    # Etiqueta de "previa": ¿habrá un gap nuevo en las próximas HORIZONTE_PREVIA ruedas?
    g = out["gap"].astype(float)
    futuro = pd.concat([g.shift(-k) for k in range(1, HORIZONTE_PREVIA + 1)], axis=1).max(axis=1)
    out["gap_pronto"] = futuro
    out.loc[out.index[-HORIZONTE_PREVIA:], "gap_pronto"] = np.nan  # no se conoce todavía
    return out


def grupo_vol(x: float) -> str:
    if x is None or not np.isfinite(x):
        return "sin_dato"
    return "baja" if x <= VOL_BAJA_MAX else ("media" if x <= VOL_MEDIA_MAX else "alta")


def _stats(s: pd.Series) -> dict:
    s = s.dropna()
    if len(s) == 0:
        return {"n": 0}
    return {"n": int(len(s)), "media": round(float(s.mean()), 2), "mediana": round(float(s.median()), 2),
            "pct_positivos": round(float((s > 0).mean() * 100), 1)}


def resumen_eventos(ev: pd.DataFrame) -> dict:
    out = {"n": int(len(ev))}
    for n in FORWARD:
        out[f"fwd{n}"] = _stats(ev[f"fwd{n}"])
        out[f"alpha{n}"] = _stats(ev[f"alpha{n}"])
    out["peor_caida10_mediana"] = None if ev["peor_caida10"].dropna().empty else round(float(ev["peor_caida10"].median()), 2)
    return out


def tabla_lift(base: pd.DataFrame, corte: pd.Timestamp) -> dict:
    """Para cada característica: quintiles calculados con la parte de ENTRENAMIENTO,
    y tasa de 'gap pronto' en entrenamiento y en PRUEBA por quintil."""
    base = base[base["macro_ok"] & base["gap_pronto"].notna()]
    ent, pru = base[base.index < corte], base[base.index >= corte]
    res = {}
    for f in FEATURES:
        x = ent[f].dropna()
        if len(x) < 500:
            continue
        cortes = np.unique(np.nanquantile(x, [0.2, 0.4, 0.6, 0.8]))
        filas = []
        for nombre, d in (("entrenamiento", ent), ("prueba", pru)):
            tasa_base = d["gap_pronto"].mean() * 100
            bins = np.digitize(d[f].values, cortes)
            for q in range(len(cortes) + 1):
                m = (bins == q) & d[f].notna().values
                if m.sum() < 200:
                    continue
                t = d["gap_pronto"].values[m].mean() * 100
                filas.append({"muestra": nombre, "quintil": q + 1, "n_dias": int(m.sum()),
                              "tasa_gap_pct": round(float(t), 2), "tasa_base_pct": round(float(tasa_base), 2),
                              "lift": round(float(t / tasa_base), 2) if tasa_base > 0 else None})
        res[f] = {"cortes": [round(float(c), 2) for c in cortes], "filas": filas}
    return res


def diagnostico(lift: dict) -> list:
    """Características donde el MISMO quintil tiene lift >= 1,3 en entrenamiento Y en prueba."""
    hallazgos = []
    for f, d in lift.items():
        porq = {}
        for r in d["filas"]:
            porq.setdefault(r["quintil"], {})[r["muestra"]] = r
        for q, m in porq.items():
            if "entrenamiento" in m and "prueba" in m:
                a, b = m["entrenamiento"]["lift"], m["prueba"]["lift"]
                if a and b and a >= 1.3 and b >= 1.3:
                    hallazgos.append({"caracteristica": f, "quintil": q, "lift_entrenamiento": a, "lift_prueba": b,
                                      "tasa_prueba_pct": m["prueba"]["tasa_gap_pct"], "tasa_base_prueba_pct": m["prueba"]["tasa_base_pct"]})
    return sorted(hallazgos, key=lambda h: -min(h["lift_entrenamiento"], h["lift_prueba"]))


def correr(series: dict, spy_close: pd.Series, universo_etiquetas: dict | None = None) -> dict:
    filas, eventos = [], []
    for t, df in series.items():
        try:
            r = calcular_ticker(df, spy_close)
        except Exception as e:
            log.warning(f"{t}: no se pudo calcular ({e})")
            continue
        r["ticker"] = t
        vol_t = float(r["vol60_anual"].median()) if r["vol60_anual"].notna().any() else None
        r["grupo_vol"] = grupo_vol(vol_t)
        r["vol_tipica"] = vol_t
        filas.append(r)
    if not filas:
        raise RuntimeError("Sin datos para ningún ticker")
    todo = pd.concat(filas)
    todo.index.name = "fecha"
    ev = todo[todo["gap"]].copy()
    fechas = np.sort(todo.index.unique())
    corte = pd.Timestamp(fechas[int(len(fechas) * FRACCION_ENTRENAMIENTO)])

    out = {
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "regla": f"suba >= {UMBRAL_GAP_ALCISTA_PCT}% de cierre a cierre, ayer sobre SMA200, hoy máximo de {VENTANA_GAP_MAXIMO_DIAS} ruedas (igual que el radar), sin otro gap en las {ENFRIAMIENTO_RUEDAS} ruedas previas",
        "grupos_volatilidad": f"baja <= {VOL_BAJA_MAX}% anual, media <= {VOL_MEDIA_MAX}%, alta > {VOL_MEDIA_MAX}% (desvío de 60 ruedas anualizado, mediana del papel)",
        "periodo": PERIODO, "corte_entrenamiento_prueba": str(corte.date()),
        "tickers_analizados": len(series),
        "tickers_por_grupo": {g: int(n) for g, n in todo.groupby("grupo_vol")["ticker"].nunique().items()},
        "eventos_total": int(len(ev)),
        "eventos": {}, "previa_comparada": {}, "lift": {}, "hallazgos": {}, "mas_repetidos": {}, "ultimos_eventos": [],
    }
    grupos = {"baja": ["baja"], "baja_o_media": ["baja", "media"], "media": ["media"], "alta": ["alta"], "todos": ["baja", "media", "alta", "sin_dato"]}
    for nombre, gs in grupos.items():
        e = ev[ev["grupo_vol"].isin(gs)]
        b = todo[todo["grupo_vol"].isin(gs)]
        out["eventos"][nombre] = resumen_eventos(e) if len(e) else {"n": 0}
        out["lift"][nombre] = tabla_lift(b, corte) if len(b) else {}
        out["hallazgos"][nombre] = diagnostico(out["lift"][nombre])
    # Previa comparada (día anterior al gap vs. días normales con macrotendencia), por grupo
    todo_prev = todo.copy()
    for f in FEATURES:
        todo_prev[f + "_prev"] = todo.groupby("ticker")[f].shift(1)
    ev_prev = todo_prev[todo_prev["gap"]]
    normales = todo_prev[todo_prev["macro_ok"] & ~todo_prev["gap"]]
    for nombre, gs in grupos.items():
        e = ev_prev[ev_prev["grupo_vol"].isin(gs)]
        n_ = normales[normales["grupo_vol"].isin(gs)]
        comp = {}
        for f in FEATURES:
            if e[f + "_prev"].notna().sum() >= 10:
                comp[f] = {"antes_del_gap_mediana": round(float(e[f + "_prev"].median()), 2),
                           "dia_normal_mediana": round(float(n_[f + "_prev"].median()), 2)}
        out["previa_comparada"][nombre] = comp
    for nombre in ("baja_o_media",):
        e = ev[ev["grupo_vol"].isin(grupos[nombre])]
        out["mas_repetidos"][nombre] = {k: int(v) for k, v in e["ticker"].value_counts().head(15).items()}
    # Consistencia: ¿el resultado depende de un año raro o de un mercado en pánico?
    e_b = ev[ev["grupo_vol"].isin(["baja", "media"])]
    por_anio = {}
    for anio, d in e_b.groupby(e_b.index.year):
        por_anio[str(anio)] = {"n": int(len(d)), "fwd5": _stats(d["fwd5"]), "fwd10": _stats(d["fwd10"]), "peor_caida10_mediana": None if d["peor_caida10"].dropna().empty else round(float(d["peor_caida10"].median()), 2)}
    out["por_anio_baja_o_media"] = por_anio
    out["por_regimen_baja_o_media"] = {
        "SPY sobre su SMA200": resumen_eventos(e_b[e_b["spy_sobre_sma200"] == True]) if (e_b["spy_sobre_sma200"] == True).any() else {"n": 0},
        "SPY bajo su SMA200": resumen_eventos(e_b[e_b["spy_sobre_sma200"] == False]) if (e_b["spy_sobre_sma200"] == False).any() else {"n": 0},
    }
    ult = ev.sort_index().tail(40)
    for fecha, r in ult.iterrows():
        out["ultimos_eventos"].append({"fecha": str(pd.Timestamp(fecha).date()), "ticker": r["ticker"], "grupo_vol": r["grupo_vol"],
                                       "ret_dia": round(float(r["ret_dia"]), 2),
                                       **{f"fwd{n}": (None if pd.isna(r[f"fwd{n}"]) else round(float(r[f"fwd{n}"]), 2)) for n in (5, 10)}})
    return out


def resumen_md(res: dict) -> str:
    L = ["# Estudio Gap alcista (CEDEARs)", "", f"Generado: {res['generado_utc'][:16]} UTC · Regla: {res['regla']}.",
         f"Volatilidad: {res['grupos_volatilidad']}.", f"Papeles analizados: {res['tickers_analizados']} {res['tickers_por_grupo']}. Eventos: {res['eventos_total']}.",
         f"Entrenamiento hasta {res['corte_entrenamiento_prueba']}, prueba después.", ""]
    for g in ("baja_o_media", "alta"):
        e = res["eventos"].get(g, {})
        L.append(f"## Qué pasó después del gap — volatilidad {g.replace('_', ' ')} (n={e.get('n', 0)})")
        for n in FORWARD:
            s, a = e.get(f"fwd{n}", {}), e.get(f"alpha{n}", {})
            if s.get("n"):
                L.append(f"- +{n} ruedas: mediana {s['mediana']}% ({s['pct_positivos']}% positivos), contra SPY {a.get('mediana')} pts")
        L.append(f"- Peor caída en las 10 ruedas siguientes (mediana): {e.get('peor_caida10_mediana')}%")
        L.append("")
    L.append("## ¿Depende del año o del mercado? (volatilidad baja o media, +5 ruedas)")
    for a, d in res.get("por_anio_baja_o_media", {}).items():
        f5 = d.get("fwd5", {})
        L.append(f"- {a}: {d['n']} gaps, mediana {f5.get('mediana')}% ({f5.get('pct_positivos')}% positivos), peor caída 10 ruedas {d.get('peor_caida10_mediana')}%")
    for r, d in res.get("por_regimen_baja_o_media", {}).items():
        f5 = d.get("fwd5", {})
        if d.get("n"):
            L.append(f"- {r}: {d['n']} gaps, mediana {f5.get('mediana')}% ({f5.get('pct_positivos')}% positivos)")
    L.append("")
    for g in ("baja_o_media",):
        L.append(f"## Señales de la previa con lift ≥1,3 en entrenamiento y prueba — {g.replace('_', ' ')}")
        h = res["hallazgos"].get(g, [])
        if not h:
            L.append("- Ninguna característica sostuvo el resultado en la parte de prueba (no hay evidencia de que se pueda detectar en la previa con estas medidas).")
        for x in h[:10]:
            L.append(f"- {FEATURES[x['caracteristica']]}: quintil {x['quintil']} -> lift {x['lift_entrenamiento']} (entrenamiento) y {x['lift_prueba']} (prueba); tasa de gap pronto {x['tasa_prueba_pct']}% vs {x['tasa_base_prueba_pct']}% base.")
        L.append("")
    return "\n".join(L)


# ---------------------------------------------------------------------------
def _universo() -> list:
    """CEDEARs con dato (de ultimo.json) que además estén en el universo del radar."""
    try:
        with open("data/ultimo.json", "r", encoding="utf-8") as f:
            u = json.load(f)
        ced = [c["Ticker"] for c in u["cedears_pricing"]["cedears"] if not c.get("sin_datos")]
        return sorted(set(ced))
    except Exception as e:
        log.warning(f"No se pudo leer la lista de CEDEARs de ultimo.json ({e})")
        return []


def _bajar(simbolo: str):
    import yfinance as yf
    h = yf.Ticker(simbolo).history(period=PERIODO, auto_adjust=True)
    if h is None or len(h) < MIN_FILAS:
        return None
    h = h[["Open", "High", "Low", "Close", "Volume"]].copy()
    h.index = h.index.tz_localize(None).normalize() if getattr(h.index, "tz", None) is not None else h.index.normalize()
    return h


def main():
    tickers = _universo()
    if not tickers:
        log.error("No hay lista de CEDEARs -- se aborta")
        sys.exit(1)
    log.info(f"Bajando {len(tickers)} CEDEARs + {BENCHMARK} ({PERIODO})...")
    spy = _bajar(BENCHMARK)
    if spy is None:
        log.error("No se pudo bajar SPY -- se aborta")
        sys.exit(1)
    series, falló = {}, []
    for t in tickers:
        if t == BENCHMARK:
            continue
        try:
            d = _bajar(t)
        except Exception as e:
            d = None
            log.warning(f"{t}: {e}")
        if d is None:
            falló.append(t)
        else:
            series[t] = d
        time.sleep(0.2)
    log.info(f"Listo: {len(series)} bajados, {len(falló)} sin datos suficientes: {falló}")
    res = correr(series, spy["Close"])
    res["sin_datos"] = falló
    os.makedirs("data", exist_ok=True)
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(RUTA_RESUMEN, "w", encoding="utf-8") as f:
        f.write(resumen_md(res))
    log.info(f"Guardado {RUTA_SALIDA} y {RUTA_RESUMEN}")


if __name__ == "__main__":
    main()
