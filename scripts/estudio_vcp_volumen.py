"""
Estudio VCP / retrocesos decrecientes + VOLUMEN (idea del hilo de Market Strength).

Aparte y aditivo: NO toca el radar, la app ni la Auditoria. Se corre a mano desde
Actions ("Estudio VCP + volumen"). Hace tres cosas:
  1) Baja ~2 anios de CIERRE y VOLUMEN diario de Yahoo para todo el universo.
  2) Guarda el volumen en data/volumenes_diarios.jsonl (una linea por rueda,
     append-only: solo agrega fechas que faltan) para uso futuro.
  3) Mide que paso 5/10/20 ruedas despues de la ruptura de la "forma" del hilo y la
     compara contra una base sin la forma. Escribe data/estudio_vcp_volumen.json,
     data/estudio_vcp_volumen_resumen.md y data/vcp_forma_hoy.json (quienes la
     cumplen hoy, con pivote, stop y volumen).

Regla del hilo (aproximada con cierres, tramos de 20 ruedas ~ 4 semanas):
  * 3 retrocesos (caida maxima de cierre en cada tramo) cada uno menor al anterior,
    el ultimo <= 8%
  * cierre a menos de 15% del maximo de 52 semanas y sobre la SMA50
  * fuerza relativa: retorno de 126 ruedas en el percentil >= 50 del universo
    (PROXY propio, no es el RS Score del radar)
  * volumen "secandose": promedio 10 ruedas / promedio 50 ruedas < 100%
  * pivote = maximo cierre del ultimo tramo; stop = minimo cierre del ultimo tramo
  * ruptura = cierre sobre el pivote (del dia previo); "con volumen" = volumen del dia
    >= 1.5x el promedio de 50 ruedas (umbral mio, NO validado)
Limitaciones (se escriben tambien en el resumen): universo actual (sesgo de
supervivencia), ~1 anio de eventos en un solo regimen de mercado, eventos del mismo
ticker/categoria separados >=20 ruedas solo para no contar dos veces el mismo caso.
"""
import json, logging, os, sys
import numpy as np
import pandas as pd

log = logging.getLogger("radar.estudio_vcp_volumen")
RUTA_VOL = "data/volumenes_diarios.jsonl"
RUTA_JSON = "data/estudio_vcp_volumen.json"
RUTA_MD = "data/estudio_vcp_volumen_resumen.md"
RUTA_HOY = "data/vcp_forma_hoy.json"

TRAMO = 20
MAX_ULT_RETROCESO = 8.0
CERCA_MAX52 = 0.85
RS_PERCENTIL = 50
VENTANA_SECA = (10, 50)
VOL_RUPTURA = 1.5
HORIZONTES = (5, 10, 20)
SEPARACION = 20
MIN_HIST = 252


# ---------------------------------------------------------------- descarga
def descargar(simbolos, period="2y"):
    import yfinance as yf
    cierres, vols = {}, {}
    for i in range(0, len(simbolos), 40):
        lote = simbolos[i:i + 40]
        try:
            df = yf.download(lote, period=period, auto_adjust=True, progress=False,
                             group_by="column", threads=True)
            c, v = df["Close"], df["Volume"]
        except Exception as e:
            log.error(f"lote {i} fallo: {e}")
            continue
        if isinstance(c, pd.Series):
            c, v = c.to_frame(lote[0]), v.to_frame(lote[0])
        for t in c.columns:
            sc = c[t].dropna()
            if len(sc) < 60:
                continue
            sc.index = pd.to_datetime(sc.index).tz_localize(None).normalize()
            sv = v[t].reindex(c[t].index)
            sv.index = pd.to_datetime(sv.index).tz_localize(None).normalize()
            cierres[t] = sc[~sc.index.duplicated(keep="last")]
            vols[t] = sv[~sv.index.duplicated(keep="last")]
    C = pd.DataFrame(cierres).sort_index()
    V = pd.DataFrame(vols).sort_index().reindex(C.index)
    return C, V


def guardar_volumenes(V):
    """Agrega SOLO las fechas que faltan; no modifica lineas existentes."""
    existentes = {}
    if os.path.exists(RUTA_VOL):
        with open(RUTA_VOL, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if linea:
                    try:
                        existentes.setdefault(json.loads(linea)["fecha"], linea)
                    except Exception:
                        pass
    nuevas = 0
    for fecha, fila in V.iterrows():
        k = fecha.strftime("%Y-%m-%d")
        if k in existentes:
            continue
        d = {t: int(x) for t, x in fila.items() if pd.notna(x) and x > 0}
        if len(d) >= 50:
            existentes[k] = json.dumps({"fecha": k, "v": d}, separators=(",", ":"))
            nuevas += 1
    with open(RUTA_VOL, "w", encoding="utf-8") as f:
        for k in sorted(existentes):
            f.write(existentes[k] + "\n")
    log.info(f"Volumenes: {nuevas} fechas nuevas, {len(existentes)} en total -> {RUTA_VOL}")


# ---------------------------------------------------------------- analisis
def _mdd_rodante(c, n=TRAMO):
    """Caida maxima (%) de los cierres en la ventana de n ruedas que termina en i."""
    out = np.full(len(c), np.nan)
    for i in range(n - 1, len(c)):
        w = c[i - n + 1:i + 1]
        if np.isnan(w).any():
            continue
        pico = np.maximum.accumulate(w)
        out[i] = float(((pico - w) / pico).max() * 100)
    return out


def _senales(C, V):
    """Devuelve dict de DataFrames (misma forma que C) con las condiciones por dia."""
    ret126 = C / C.shift(126) - 1
    rs_ok = ret126.rank(axis=1, pct=True) * 100 >= RS_PERCENTIL
    sma50 = C.rolling(50).mean()
    max252 = C.rolling(252).max()
    cerca = C >= CERCA_MAX52 * max252
    sobre = C > sma50
    mdd = C.apply(lambda s: pd.Series(_mdd_rodante(s.values), index=s.index))
    d3 = mdd
    d2 = mdd.shift(TRAMO)
    d1 = mdd.shift(2 * TRAMO)
    escalera = (d1 > d2) & (d2 > d3) & (d3 <= MAX_ULT_RETROCESO)
    a, b = VENTANA_SECA
    seca = (V.rolling(a).mean() / V.rolling(b).mean()) < 1.0
    forma = escalera & cerca & sobre & rs_ok
    pivote = C.rolling(TRAMO).max()
    stop = C.rolling(TRAMO).min()
    volrel = V / V.shift(1).rolling(50).mean()
    # base: ruptura de maximo de 20 ruedas en tendencia, SIN la forma
    tendencia = cerca & sobre & rs_ok
    return dict(forma=forma, seca=seca, pivote=pivote, stop=stop, volrel=volrel,
                tendencia=tendencia, escalera=escalera)


def _eventos(C, V, S, spy):
    """Lista de eventos (ticker, fecha, categoria, retornos...)."""
    forma_prev = S["forma"].shift(1)
    piv_prev = S["pivote"].shift(1)
    stop_prev = S["stop"].shift(1)
    seca_prev = S["seca"].shift(1)
    rup = (C > piv_prev)
    rup_forma = forma_prev.fillna(False).astype(bool) & rup
    rup_base = S["tendencia"].shift(1).fillna(False).astype(bool) & rup & ~forma_prev.fillna(False).astype(bool)
    cats = {
        "forma_ruptura": rup_forma,
        "forma_ruptura_vol": rup_forma & (S["volrel"] >= VOL_RUPTURA),
        "forma_ruptura_sin_vol": rup_forma & (S["volrel"] < VOL_RUPTURA),
        "forma_seca_ruptura_vol": rup_forma & seca_prev.fillna(False).astype(bool) & (S["volrel"] >= VOL_RUPTURA),
        "base_tendencia_ruptura": rup_base,
        "base_tendencia_ruptura_vol": rup_base & (S["volrel"] >= VOL_RUPTURA),
    }
    ev = []
    idx = C.index
    spyv = spy.reindex(idx).values
    for cat, M in cats.items():
        for t in C.columns:
            m = M[t].values
            c = C[t].values
            ultimo = -10 ** 9
            for j in np.where(m)[0]:
                if j < MIN_HIST or j - ultimo < SEPARACION:
                    continue
                ultimo = j
                fila = dict(cat=cat, ticker=t, fecha=idx[j].strftime("%Y-%m-%d"),
                            volrel=float(S["volrel"][t].values[j]) if pd.notna(S["volrel"][t].values[j]) else None)
                for h in HORIZONTES:
                    if j + h < len(c) and not np.isnan(c[j + h]):
                        fila[f"r{h}"] = (c[j + h] / c[j] - 1) * 100
                        fila[f"x{h}"] = fila[f"r{h}"] - (spyv[j + h] / spyv[j] - 1) * 100
                sp = stop_prev[t].values[j]
                if j + 20 < len(c) and pd.notna(sp):
                    fila["stop_20"] = bool(np.nanmin(c[j + 1:j + 21]) < sp)
                ev.append(fila)
    return ev


def _resumir(ev):
    df = pd.DataFrame(ev)
    out = {}
    if df.empty:
        return out
    for cat, g in df.groupby("cat"):
        d = dict(n=int(len(g)))
        for h in HORIZONTES:
            r = g[f"r{h}"].dropna() if f"r{h}" in g else pd.Series(dtype=float)
            x = g[f"x{h}"].dropna() if f"x{h}" in g else pd.Series(dtype=float)
            d[f"n{h}"] = int(len(r))
            d[f"prom{h}"] = round(float(r.mean()), 2) if len(r) else None
            d[f"mediana{h}"] = round(float(r.median()), 2) if len(r) else None
            d[f"pct_pos{h}"] = round(float((r > 0).mean() * 100), 1) if len(r) else None
            d[f"exceso_spy{h}"] = round(float(x.mean()), 2) if len(x) else None
        s = g["stop_20"].dropna() if "stop_20" in g else pd.Series(dtype=bool)
        d["pct_stop_20"] = round(float(s.mean() * 100), 1) if len(s) else None
        out[cat] = d
    return out


def _hoy(C, V, S):
    i = len(C) - 1
    lista = []
    for t in C.columns:
        if bool(S["forma"][t].iloc[i]):
            lista.append(dict(
                ticker=t, cierre=round(float(C[t].iloc[i]), 2),
                pivote=round(float(S["pivote"][t].iloc[i]), 2),
                stop=round(float(S["stop"][t].iloc[i]), 2),
                vol_10_vs_50_pct=round(float(V[t].rolling(10).mean().iloc[i] / V[t].rolling(50).mean().iloc[i] * 100), 1),
                vol_rel_hoy=round(float(S["volrel"][t].iloc[i]), 2),
                vol_seca=bool(S["seca"][t].iloc[i])))
    return dict(fecha=C.index[-1].strftime("%Y-%m-%d"), n=len(lista),
                lista=sorted(lista, key=lambda x: x["ticker"]))


NOMBRES = {
    "forma_ruptura": "Forma + ruptura del pivote (cualquier volumen)",
    "forma_ruptura_vol": "Forma + ruptura con volumen >= 1,5x",
    "forma_ruptura_sin_vol": "Forma + ruptura con volumen < 1,5x",
    "forma_seca_ruptura_vol": "Forma + volumen seco previo + ruptura con volumen >= 1,5x",
    "base_tendencia_ruptura": "BASE: tendencia fuerte + ruptura de 20 ruedas, SIN la forma",
    "base_tendencia_ruptura_vol": "BASE con volumen >= 1,5x",
}


def _md(res, hoy, nt, f0, f1):
    L = ["# Estudio VCP / retrocesos decrecientes + volumen", "",
         f"Universo: {nt} activos. Datos Yahoo del {f0} al {f1}. Retornos de cierre a cierre desde el dia de la ruptura.", "",
         "| Categoria | n | Prom 20r % | Mediana 20r % | % positivos 20r | Exceso vs SPY 20r | Prom 5r | Prom 10r | % que toco el stop en 20r |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k in NOMBRES:
        d = res.get(k)
        if not d:
            L.append(f"| {NOMBRES[k]} | 0 | - | - | - | - | - | - | - |")
            continue
        L.append(f"| {NOMBRES[k]} | {d['n']} | {d['prom20']} | {d['mediana20']} | {d['pct_pos20']} | {d['exceso_spy20']} | {d['prom5']} | {d['prom10']} | {d['pct_stop_20']} |")
    L += ["", f"Cumplen la forma HOY ({hoy['fecha']}): {hoy['n']} activos (detalle en data/vcp_forma_hoy.json).", "",
          "## Como leerlo", "",
          "- Cualquier categoria con n menor a 30 es muestra chica: no concluir nada.",
          "- Lo que importa es la comparacion contra la BASE (misma tendencia, sin la forma) y el exceso vs SPY, no el promedio solo.",
          "- Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un unico regimen de mercado, RS aproximado con retorno de 126 ruedas, umbral de volumen 1,5x elegido por mi (no validado).",
          "- Los eventos del mismo ticker y categoria se separan >= 20 ruedas solo para no contar dos veces el mismo caso."]
    return "\n".join(L) + "\n"


def correr(C=None, V=None, guardar=True):
    sys.path.insert(0, "scripts")
    if C is None:
        from config import TICKERS, BENCHMARK
        simbolos = list(dict.fromkeys(list(TICKERS) + [BENCHMARK]))
        C, V = descargar(simbolos)
        bench = BENCHMARK
    else:
        bench = "SPY"
    if bench not in C.columns or C.shape[1] < 100 or len(C) < MIN_HIST + 60:
        log.error("Pocos datos -- se aborta")
        sys.exit(1)
    if guardar:
        guardar_volumenes(V)
    spy = C[bench]
    cols = [t for t in C.columns if t != bench and V[t].notna().sum() > 200]
    C2, V2 = C[cols], V[cols]
    S = _senales(C2, V2)
    ev = _eventos(C2, V2, S, spy)
    res = _resumir(ev)
    hoy = _hoy(C2, V2, S)
    f0, f1 = C.index[0].strftime("%Y-%m-%d"), C.index[-1].strftime("%Y-%m-%d")
    out = dict(generado=f1, universo=len(cols), resumen=res, params=dict(
        tramo=TRAMO, max_ult_retroceso=MAX_ULT_RETROCESO, cerca_max52=CERCA_MAX52,
        rs_percentil=RS_PERCENTIL, vol_ruptura=VOL_RUPTURA, separacion=SEPARACION))
    if guardar:
        with open(RUTA_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        with open(RUTA_HOY, "w", encoding="utf-8") as f:
            json.dump(hoy, f, ensure_ascii=False, indent=1)
        with open(RUTA_MD, "w", encoding="utf-8") as f:
            f.write(_md(res, hoy, len(cols), f0, f1))
    return out, hoy, ev


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
