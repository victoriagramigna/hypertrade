"""
Estudio VCP v4 -- contracciones REALES (maximos y minimos del dia) y stop bajo el ultimo minimo.

Aparte y aditivo: NO toca el radar, la app, la Watchlist VCP ni la Auditoria. Se corre a mano desde
Actions ("Estudio VCP v4"). Baja ~2 anios de apertura/maximo/minimo/cierre/volumen de Yahoo y escribe
data/estudio_vcp_v4.json y data/estudio_vcp_v4_resumen.md.

Que cambia respecto de la v3 (que medio tramos fijos de 20 ruedas con cierres):
  * Las contracciones se miden de PICO a VALLE reales: maximos y minimos del dia, detectados como
    "giros" (swing high / swing low). Un giro de K ruedas se confirma recien K ruedas despues, y asi
    se usa en el estudio: nunca se mira el futuro.
  * Una base VCP = 2 a 4 contracciones consecutivas de profundidad decreciente (cada una menor que la
    anterior), la ultima <= 10%, la primera >= 10%, con el ultimo maximo a menos de 5% del maximo de la base.
  * Pivote = ultimo maximo de la base (tope de la ultima contraccion). Stop "SU" = minimo de la ultima
    contraccion. Entrada: primer cierre sobre el pivote.
  * Stop evaluado con el MINIMO del dia: si el minimo toca el stop se sale al stop (o a la apertura si abrio
    por debajo). Antes se miraba solo el cierre.
Formas: V4A contracciones decrecientes en tendencia; V4B = V4A + minimos que no bajan (triangulo real);
V4P = V4A + plantilla de tendencia (9 condiciones, proxy propio); V4C = V4B + plantilla.
BASE = ruptura del maximo de cierre de 20 ruedas en tendencia, sin base VCP.
Stops comparables entre todas: S10L (minimo de las ultimas 10 ruedas) y F8 (8% bajo la entrada). SU solo para las VCP.
Exceso = retorno de la operacion menos el de SPY (cierre) entre la entrada y el dia de salida.
Limitaciones: universo actual (sesgo de supervivencia), ~1 anio de eventos en un solo regimen, RS y plantilla
con proxy propio, entrada al cierre de la ruptura, SPY medido al cierre aunque la salida sea intradia, umbrales mios.
"""
import json, logging, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "scripts")
import estudio_vcp_volumen as v1
import estudio_vcp_v2 as v2
import estudio_vcp_v3 as v3

log = logging.getLogger("radar.estudio_vcp_v4")
RUTA_JSON = "data/estudio_vcp_v4.json"
RUTA_MD = "data/estudio_vcp_v4_resumen.md"

K_PRINCIPAL = 5
K_SENSIBILIDAD = (3, 8)
MAX_CONTR = 4
MAX_ULT = 10.0          # profundidad maxima de la ultima contraccion (%)
MIN_PRIMERA = 10.0      # profundidad minima de la primera contraccion (%)
PIVOTE_CERCA = 0.95     # ultimo maximo >= 95% del maximo de la base
MAX_EDAD_BAJO = 40      # el ultimo minimo no puede tener mas de 40 ruedas
MAX_EDAD_PIVOTE = 60
MAX_BASE = 150          # la base no puede empezar hace mas de 150 ruedas
HORIZONTE = 20
SEPARACION = 20
MIN_HIST = 252
FORMAS = ["V4A", "V4B", "V4P", "V4C", "BASE"]
STOPS_VCP = ["SU", "S10L", "F8"]
STOPS_BASE = ["S10L", "F8"]
UMBRALES_VOL = (1.0, 1.5, 2.0, 3.0)


# ---------------------------------------------------------------- datos
def descargar_ohlc(simbolos, period="2y"):
    import yfinance as yf
    O, Hh, Ll, Cc, Vv = {}, {}, {}, {}, {}
    for i in range(0, len(simbolos), 40):
        lote = simbolos[i:i + 40]
        try:
            df = yf.download(lote, period=period, auto_adjust=True, progress=False, group_by="column", threads=True)
            partes = {k: df[k] for k in ("Open", "High", "Low", "Close", "Volume")}
        except Exception as e:
            log.error(f"lote {i} fallo: {e}")
            continue
        if isinstance(partes["Close"], pd.Series):
            partes = {k: v.to_frame(lote[0]) for k, v in partes.items()}
        for t in partes["Close"].columns:
            sc = partes["Close"][t].dropna()
            if len(sc) < 60:
                continue
            for nombre, dic in (("Open", O), ("High", Hh), ("Low", Ll), ("Close", Cc), ("Volume", Vv)):
                s = partes[nombre][t].reindex(partes["Close"][t].index)
                s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
                dic[t] = s[~s.index.duplicated(keep="last")]
    C = pd.DataFrame(Cc).sort_index()
    f = lambda d: pd.DataFrame(d).sort_index().reindex(C.index)
    O, H, L, V = f(O), f(Hh), f(Ll), f(Vv)
    # huecos de apertura/maximo/minimo: usar el cierre (no inventa movimiento)
    O, H, L = O.fillna(C), H.fillna(C), L.fillna(C)
    H = np.maximum(H, C)
    L = np.minimum(L, C)
    return O, H, L, C, V


# ---------------------------------------------------------------- giros y bases
def _giros(H, L, K):
    """Giros confirmados: dict {rueda_de_confirmacion: (tipo, indice, precio)}."""
    n = len(H)
    out = {}
    for i in range(K, n - K):
        alto = H[i] > H[i + 1:i + K + 1].max() and H[i] >= H[i - K:i].max()
        bajo = L[i] < L[i + 1:i + K + 1].min() and L[i] <= L[i - K:i].min()
        if alto == bajo:      # ni uno ni otro, o rueda "exterior": se descarta
            continue
        out[i + K] = ("H", i, float(H[i])) if alto else ("L", i, float(L[i]))
    return out


def _agregar(zz, e):
    """Zigzag causal: alterna maximo/minimo; si llegan dos del mismo tipo se queda el mas extremo."""
    if zz and zz[-1][0] == e[0]:
        if (e[0] == "H" and e[2] > zz[-1][2]) or (e[0] == "L" and e[2] < zz[-1][2]):
            zz[-1] = e
        return
    zz.append(e)


def _base(zz, t):
    """Base VCP vigente con los giros conocidos a la rueda t (o None)."""
    if len(zz) < 4 or zz[-1][0] != "L":
        return None
    pares, k = [], len(zz) - 1
    while k >= 1 and zz[k][0] == "L" and zz[k - 1][0] == "H" and len(pares) < MAX_CONTR:
        pares.append((zz[k - 1], zz[k]))
        k -= 2
    pares.reverse()
    prof = [(h[2] - l[2]) / h[2] * 100 for h, l in pares]
    n = 1
    while n < len(pares) and prof[-n - 1] > prof[-n]:
        n += 1
    if n < 2:
        return None
    pares, prof = pares[-n:], prof[-n:]
    hn, ln = pares[-1]
    if prof[-1] <= 0 or prof[-1] > MAX_ULT or prof[0] < MIN_PRIMERA:
        return None
    if t - ln[1] > MAX_EDAD_BAJO or t - hn[1] > MAX_EDAD_PIVOTE or t - pares[0][0][1] > MAX_BASE:
        return None
    if hn[2] < PIVOTE_CERCA * max(p[0][2] for p in pares):
        return None
    suben = all(pares[i][1][2] >= pares[i - 1][1][2] for i in range(1, n))
    return dict(n=n, prof=[round(x, 1) for x in prof], pivote=hn[2], stop=ln[2], suben=suben,
                inicio=int(pares[0][0][1]), idx_pivote=int(hn[1]), idx_bajo=int(ln[1]))


def _simular(O, L, C, j, entrada, nivel, spyv):
    fut = L[j + 1:j + HORIZONTE + 1]
    bajo = np.where(fut <= nivel)[0]
    if len(bajo):
        k = int(bajo[0]) + 1
        px = min(nivel, O[j + k])
    else:
        k, px = HORIZONTE, C[j + HORIZONTE]
    ret = (px / entrada - 1) * 100
    return k, ret, ret - (spyv[j + k] / spyv[j] - 1) * 100, bool(len(bajo))


def _eventos(O, H, L, C, S, pl, spy, K, diag=None):
    idx = C.index
    spyv = spy.reindex(idx).values
    spy_sobre = (spy > spy.rolling(50).mean()).reindex(idx).fillna(False).values
    tend = S["tendencia"].shift(1).fillna(False).astype(bool)
    plp = pl.shift(1).fillna(False).astype(bool)
    seca_prev = S["seca"].shift(1).fillna(False).astype(bool)
    filas, hoy = [], []
    n = len(idx)
    for t in C.columns:
        o, h, l, c = O[t].values, H[t].values, L[t].values, C[t].values
        tn, pn, sc, vr = tend[t].values, plp[t].values, seca_prev[t].values, S["volrel"][t].values
        if np.isnan(c).any():
            ok = ~np.isnan(c)
            if ok.sum() < MIN_HIST + HORIZONTE + 10:
                continue
        giros = _giros(h, l, K)
        zz, ultimo = [], {f: -10 ** 9 for f in FORMAS}
        for j in range(1, n):
            e = giros.get(j - 1)
            if e:
                _agregar(zz, e)
            if j < MIN_HIST:
                continue
            ultima = j == n - 1
            if not ultima and j + HORIZONTE >= n:
                continue
            base = None
            if zz and zz[-1][0] == "L":
                piv = zz[-2][2]
                if c[j] > piv >= c[j - 1] and c[j - 1] > zz[-1][2]:
                    base = _base(zz, j - 1)
            vcp = base is not None and bool(tn[j])
            rup20 = bool(tn[j]) and c[j] > np.nanmax(c[j - 20:j])
            marcas = {}
            if vcp:
                marcas["V4A"] = True
                marcas["V4B"] = base["suben"]
                marcas["V4P"] = bool(pn[j])
                marcas["V4C"] = base["suben"] and bool(pn[j])
            if rup20 and not vcp:
                marcas["BASE"] = True
            if ultima:
                continue
            f = idx[j]
            for forma, m in marcas.items():
                if not m or j - ultimo[forma] < SEPARACION:
                    continue
                ultimo[forma] = j
                entrada = c[j]
                niveles = {"S10L": float(np.min(l[j - 9:j + 1])), "F8": entrada * 0.92}
                if forma != "BASE":
                    niveles["SU"] = base["stop"]
                for sk, nivel in niveles.items():
                    if not np.isfinite(nivel) or nivel >= entrada:
                        continue
                    riesgo = (entrada - nivel) / entrada * 100
                    k, ret, exc, parado = _simular(o, l, c, j, entrada, nivel, spyv)
                    filas.append(dict(forma=forma, stop=sk, ticker=t, fecha=f.strftime("%Y-%m-%d"),
                                      trimestre=f"{f.year}-T{(f.month - 1) // 3 + 1}",
                                      volrel=float(vr[j]) if pd.notna(vr[j]) else None, seca=bool(sc[j]),
                                      spy_sobre50=bool(spy_sobre[j]), riesgo=riesgo, parado=parado, ret=ret,
                                      exceso=exc, R=ret / riesgo, n_contr=base["n"] if base else 0,
                                      largo=int(j - base["inicio"]) if base else 0, dias=k))
        if diag is not None:
            # incluye el giro que se confirma en la ultima rueda (el bucle de arriba llega hasta n-2)
            zd = list(zz)
            e = giros.get(n - 1)
            if e:
                _agregar(zd, e)
            diag["activos"] += 1
            if len(zd) >= 4:
                diag["con_giros"] += 1
            if len(zd) >= 4 and zd[-1][0] == "L":
                diag["termina_en_minimo"] += 1
                b = _base(zd, n - 1)
                if b:
                    diag["base_valida"] += 1
                    if c[n - 1] <= b["pivote"] and c[n - 1] > b["stop"]:
                        diag["sin_romper"] += 1
                        if bool(tn[n - 1]):
                            diag["en_tendencia"] += 1
        # candidatos de hoy: base vigente sin ruptura
        e = giros.get(n - 1)
        if e:
            _agregar(zz, e)
        if zz and zz[-1][0] == "L" and n - 1 >= MIN_HIST:
            b = _base(zz, n - 1)
            if b and tn[n - 1] is not None and c[n - 1] <= b["pivote"] and c[n - 1] > b["stop"]:
                hoy.append(dict(ticker=t, contracciones=b["n"], profundidades=b["prof"], minimos_suben=b["suben"],
                                pivote=round(b["pivote"], 2), stop=round(b["stop"], 2), cierre=round(float(c[n - 1]), 2),
                                dist_pivote_pct=round((b["pivote"] / c[n - 1] - 1) * 100, 1),
                                riesgo_desde_pivote_pct=round((b["pivote"] - b["stop"]) / b["pivote"] * 100, 1),
                                tendencia=bool(S["tendencia"][t].values[n - 1]), plantilla=bool(pl[t].values[n - 1])))
    if diag is not None:
        diag["candidatos_hoy"] = len(hoy)
    return pd.DataFrame(filas), sorted(hoy, key=lambda x: x["dist_pivote_pct"])


# ---------------------------------------------------------------- analisis
def _analizar(df, C, spy):
    out = {"definiciones": {}, "mitades": {}, "regimen": {}, "trimestres": {}, "volumen": {}, "riesgo": {}, "contracciones": {}}
    if df.empty:
        return out
    ini, fin = MIN_HIST, len(C) - HORIZONTE - 1
    corte = C.index[(ini + fin) // 2].strftime("%Y-%m-%d")
    out["corte_mitades"] = corte
    out["mercado"] = v3._mercado(C, spy, corte)
    for (f, s), g in df.groupby(["forma", "stop"]):
        k = f"{f}+{s}"
        out["definiciones"][k] = v3._res(g, ic=True)
        out["mitades"][k] = {"primera": v3._res(g[g["fecha"] < corte]), "segunda": v3._res(g[g["fecha"] >= corte])}
        out["regimen"][k] = {"SPY sobre su media de 50": v3._res(g[g["spy_sobre50"]]), "SPY bajo su media de 50": v3._res(g[~g["spy_sobre50"]])}
        out["trimestres"][k] = {q: v3._res(h) for q, h in g.groupby("trimestre")}
    for f in ("V4A", "V4P", "BASE"):
        g = df[(df["forma"] == f) & (df["stop"] == "S10L")]
        out["volumen"][f"{f}+S10L"] = {f"vol>={u}x": v3._res(g[g["volrel"].fillna(0) >= u]) for u in UMBRALES_VOL}
        out["volumen"][f"{f}+S10L"]["vol>=1.5x y volumen previo seco"] = v3._res(g[(g["volrel"].fillna(0) >= 1.5) & g["seca"]])
    g = df[(df["forma"] == "V4A") & (df["stop"] == "SU")]
    for nombre, m in (("riesgo <=5%", g["riesgo"] <= 5), ("riesgo 5-8%", (g["riesgo"] > 5) & (g["riesgo"] <= 8)),
                      ("riesgo 8-10%", (g["riesgo"] > 8) & (g["riesgo"] <= 10)), ("riesgo >10%", g["riesgo"] > 10)):
        out["riesgo"][nombre] = v3._res(g[m])
    for nc in (2, 3, 4):
        out["contracciones"][f"{nc} contracciones"] = v3._res(g[g["n_contr"] == nc])
    return out


NOM = {"V4A": "V4A contracciones decrecientes", "V4B": "V4B + minimos que no bajan", "V4P": "V4A + plantilla",
       "V4C": "V4B + plantilla", "BASE": "BASE tendencia + ruptura, sin base VCP"}


def _nom(k):
    f, s = k.split("+")
    return f"{NOM[f]} · {s}"


def _md(res, sens, hoy, nt, f0, f1, diag=None):
    L = ["# Estudio VCP v4 -- contracciones reales (maximos/minimos del dia)", "",
         f"Universo: {nt} activos. Yahoo del {f0} al {f1}. Giros confirmados a {K_PRINCIPAL} ruedas (sin mirar el futuro). "
         "Operacion simulada: entrada al cierre de la ruptura; salida al tocar el stop con el MINIMO del dia (al stop, o a la apertura si abrio por debajo) o a las 20 ruedas. "
         "Exceso = retorno menos el de SPY (cierre) en la misma tenencia. Intervalos remuestreando DIAS completos.", "",
         "## 1. Contexto de mercado (retorno medio a 20 ruedas, cualquier dia)", "", "| Periodo | Dias | SPY % | Universo % |", "|---|---|---|---|"]
    for q, d in res["mercado"].items():
        L.append(f"| {q} | {d['dias']} | {d['spy_20r']} | {d['universo_20r']} |")
    L += ["", f"Corte de mitades: {res['corte_mitades']}.", "", "## 2. Formas y BASE: todo el periodo", "",
          "| Definicion | Casos | Dias | Riesgo % | % toco stop | Retorno % | Exceso vs SPY % [IC95 por dias] | % ganadoras | R |", "|---|---|---|---|---|---|---|---|---|"]
    for e in FORMAS:
        for s in STOPS_VCP:
            d = res["definiciones"].get(f"{e}+{s}")
            if d and d["n"]:
                L.append(f"| {_nom(e + '+' + s)} | {d['n']} | {d['dias']} | {d['riesgo']} | {d['pct_parado']} | {d['ret']} | {d['exceso']} {d.get('exceso_ic95') or ''} | {d['pct_gan']} | {d['R']} |")
    for titulo, clave, sub in (("3. Por mitad del periodo (exceso vs SPY %)", "mitades", ("primera", "segunda")),
                               ("4. Segun el regimen del mercado el dia de la ruptura (exceso vs SPY %)", "regimen", ("SPY sobre su media de 50", "SPY bajo su media de 50"))):
        L += ["", f"## {titulo}", "", "| Definicion | " + " | ".join(f"{x} (casos)" for x in sub) + " |", "|---|" + "---|" * len(sub)]
        for e in FORMAS:
            for s in ("S10L", "SU"):
                d = res[clave].get(f"{e}+{s}")
                if d:
                    L.append(f"| {_nom(e + '+' + s)} | " + " | ".join(f"{d[x]['exceso']} ({d[x]['n']})" if d[x]["n"] else "- (0)" for x in sub) + " |")
    qs = sorted({q for d in res["trimestres"].values() for q in d})
    L += ["", "## 5. Por trimestre, stop S10L (exceso vs SPY %, casos)", "", "| Definicion | " + " | ".join(qs) + " |", "|---|" + "---|" * len(qs)]
    for e in FORMAS:
        d = res["trimestres"].get(f"{e}+S10L")
        if d:
            L.append(f"| {NOM[e]} | " + " | ".join(f"{d[q]['exceso']} ({d[q]['n']})" if q in d and d[q]["n"] else "-" for q in qs) + " |")
    L += ["", "## 6. Volumen de la ruptura, stop S10L (exceso vs SPY %)", "", "| Definicion | Condicion | Casos | Retorno % | Exceso % | % ganadoras |", "|---|---|---|---|---|---|"]
    for k, grupos in res["volumen"].items():
        for c, d in grupos.items():
            if d["n"]:
                L.append(f"| {_nom(k)} | {c} | {d['n']} | {d['ret']} | {d['exceso']} | {d['pct_gan']} |")
    L += ["", "## 7. V4A con su stop de manual (SU): por riesgo al stop y por cantidad de contracciones", "",
          "| Grupo | Casos | Riesgo % | % toco stop | Retorno % | Exceso % | R |", "|---|---|---|---|---|---|---|"]
    for bloque in ("riesgo", "contracciones"):
        for nombre, d in res[bloque].items():
            if d["n"]:
                L.append(f"| {nombre} | {d['n']} | {d['riesgo']} | {d['pct_parado']} | {d['ret']} | {d['exceso']} | {d['R']} |")
    L += ["", "## 8. Sensibilidad al largo del giro (exceso vs SPY %, stop S10L, casos)", "", "| Definicion | " + " | ".join(f"K={k}" for k in sens) + " |", "|---|" + "---|" * len(sens)]
    for e in FORMAS:
        cel = []
        for k, d in sens.items():
            x = d.get(f"{e}+S10L")
            cel.append(f"{x['exceso']} ({x['n']})" if x and x["n"] else "-")
        L.append(f"| {NOM[e]} | " + " | ".join(cel) + " |")
    L += ["", f"## 9. Bases VCP vigentes hoy, sin ruptura ({len(hoy)})", "",
          "| Ticker | Contracciones | Profundidades % | Minimos suben | Cierre | Pivote | Stop | A pivote % | Riesgo desde pivote % | Tendencia | Plantilla 9/9 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for h in hoy:
        L.append(f"| {h['ticker']} | {h['contracciones']} | {' > '.join(str(x) for x in h['profundidades'])} | {'si' if h['minimos_suben'] else 'no'} | {h['cierre']} | {h['pivote']} | {h['stop']} | {h['dist_pivote_pct']} | {h['riesgo_desde_pivote_pct']} | {'si' if h['tendencia'] else 'no'} | {'si' if h['plantilla'] else 'no'} |")
    if diag:
        L += ["", "## 10. Diagnostico de hoy: cuantos activos pasan cada filtro", "",
              f"- Activos evaluados: {diag['activos']}", f"- Con al menos 4 giros confirmados: {diag['con_giros']}",
              f"- Cuyo ultimo giro es un minimo: {diag['termina_en_minimo']}", f"- Con base valida (contracciones decrecientes, ultima <=10%, primera >=10%, recencia): {diag['base_valida']}",
              f"- ... y todavia sin romper pivote ni stop: {diag['sin_romper']}", f"- ... y ademas en tendencia: {diag['en_tendencia']}"]
    L += ["", "## Como leerlo", "",
          "- Una forma aporta algo si su exceso le gana al de la BASE con el mismo stop (S10L o F8), se repite en las dos mitades y en distintos regimenes, y su intervalo no incluye el cero.",
          "- Con menos de 30 casos (o menos de 30 dias) no concluir nada.",
          "- SU (stop bajo el ultimo minimo) no se puede comparar con la BASE: tiene otro riesgo. Se mira por su R y por tramos de riesgo.",
          "- Riesgos conocidos: ~1 anio de eventos y un solo regimen; universo actual (supervivencia); RS y plantilla con proxy propio; entrada al cierre de la ruptura (en la practica se puede comprar antes, intradia); SPY medido al cierre aunque la salida sea intradia; umbrales de la base (10%, 10%, 95%, 40/60/150 ruedas) elegidos por mi; el giro se confirma K ruedas tarde, asi que las rupturas que ocurren antes de que se confirme el ultimo minimo no cuentan; el retorno simulado no incluye costos ni es una recomendacion."]
    return "\n".join(L) + "\n"


def correr(datos=None, guardar=True):
    if datos is None:
        from config import TICKERS, BENCHMARK
        O, H, L, C, V = descargar_ohlc(list(dict.fromkeys(list(TICKERS) + [BENCHMARK])))
        bench = BENCHMARK
    else:
        O, H, L, C, V = datos
        bench = "SPY"
    if bench not in C.columns or C.shape[1] < 30 or len(C) < MIN_HIST + 60:
        log.error("Pocos datos -- se aborta")
        sys.exit(1)
    spy = C[bench]
    cols = [t for t in C.columns if t != bench and V[t].notna().sum() > 200]
    C2, V2, O2, H2, L2 = C[cols], V[cols], O[cols], H[cols], L[cols]
    S = v1._senales(C2, V2)
    pl = v2._plantilla(C2)
    diag = dict(activos=0, con_giros=0, termina_en_minimo=0, base_valida=0, sin_romper=0, en_tendencia=0)
    df, hoy = _eventos(O2, H2, L2, C2, S, pl, spy, K_PRINCIPAL, diag)
    res = _analizar(df, C2, spy)
    sens = {}
    for k in K_SENSIBILIDAD:
        d_k, _ = _eventos(O2, H2, L2, C2, S, pl, spy, k)
        sens[k] = {kk: v3._res(g) for kk, g in ((f"{f}+{s}", x) for (f, s), x in d_k.groupby(["forma", "stop"]))}
    sens = {K_PRINCIPAL: {k: v for k, v in res["definiciones"].items()}, **sens}
    sens = dict(sorted(sens.items()))
    f0, f1 = C.index[0].strftime("%Y-%m-%d"), C.index[-1].strftime("%Y-%m-%d")
    if guardar:
        with open(RUTA_JSON, "w", encoding="utf-8") as f:
            json.dump(dict(generado=f1, universo=len(cols), K=K_PRINCIPAL, resultados=res, sensibilidad=sens, hoy=hoy, diagnostico_hoy=diag), f, ensure_ascii=False, indent=1)
        with open(RUTA_MD, "w", encoding="utf-8") as f:
            f.write(_md(res, sens, hoy, len(cols), f0, f1, diag))
    return res, df, hoy


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
