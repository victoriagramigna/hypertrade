"""
Screener (solapa Mercado) -- tres listas informativas y su medicion posterior.

Listas (misma definicion que docs/index.html, constantes SCREENER_* de config.py):
  * zona_ma200 : tickers a +/- SCREENER_ZONA_MA200_PCT % de su SMA200 (testeando la tendencia de largo plazo).
  * pullback   : tickers SOBRE su SMA200 con RSI (14) entre SCREENER_PULLBACK_RSI_MIN y _MAX (retroceso dentro de una tendencia alcista).
  * rebote     : (desde el 21/10) tickers con al menos SCREENER_REBOTE_RACHA_MIN cierres seguidos a la baja y el ultimo dia en verde,
                 ordenados por la suba del dia. Las lineas del log anteriores al 21/10 no tienen esta lista (no se reconstruye nada).

Registro propio, append-only: data/log_screener.jsonl -- UNA linea por rueda cerrada:
    {"fecha": "2026-10-20", "spy": 672.1, "zona_ma200": [{"t": "AEM", "p": 123.4, "d200": -0.04, "rsi": 51.2}, ...], "pullback": [...]}
Es totalmente independiente de la Auditoria de siempre y de las alertas: no cambia ningun puntaje ni senal.

Medicion: data/auditoria_screener.json -- para cada lista y horizonte (5, 10, 20 ruedas) cuanto rindieron los tickers que
estaban en la lista cada dia, contra el SPY y contra el promedio de todo el universo en la misma ventana. Usa los cierres de
data/cierres_diarios.jsonl. Con pocos dias registrados la muestra es chica: la pantalla lo avisa.

Uso manual (recalcular la medicion sin esperar a la corrida):  python scripts/screener.py --medir
"""
import json, logging, os, sys
from datetime import datetime, timezone

try:
    from config import SCREENER_ZONA_MA200_PCT, SCREENER_PULLBACK_RSI_MIN, SCREENER_PULLBACK_RSI_MAX, SCREENER_REBOTE_RACHA_MIN
except Exception:  # ejecucion suelta
    SCREENER_ZONA_MA200_PCT, SCREENER_PULLBACK_RSI_MIN, SCREENER_PULLBACK_RSI_MAX, SCREENER_REBOTE_RACHA_MIN = 1.0, 30, 40, 3

log = logging.getLogger("radar.screener")
RUTA_LOG = "data/log_screener.jsonl"
RUTA_CIERRES = "data/cierres_diarios.jsonl"
RUTA_AUD = "data/auditoria_screener.json"
HORA_CIERRE_UTC = (21, 10)
HORIZONTES = (5, 10, 20)
LISTAS = ("zona_ma200", "pullback", "rebote")
DESCRIPCION = {
    "zona_ma200": f"A +/-{SCREENER_ZONA_MA200_PCT:g}% de su SMA200",
    "pullback": f"Sobre su SMA200 con RSI entre {SCREENER_PULLBACK_RSI_MIN} y {SCREENER_PULLBACK_RSI_MAX}",
    "rebote": f"{SCREENER_REBOTE_RACHA_MIN}+ cierres seguidos a la baja y hoy en verde",
}


def _num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def listas(ranking):
    """ranking: lista de dicts (filas de ultimo.json -> ranking). Devuelve {lista: [filas chicas]}."""
    zona, pull, reb = [], [], []
    for r in ranking:
        t, p = r.get("Ticker"), _num(r.get("Precio"))
        d200, rsi = _num(r.get("Dist_SMA200_%")), _num(r.get("RSI"))
        if not t or p is None or d200 is None:
            continue
        fila = {"t": t, "p": round(p, 2), "d200": round(d200, 2), "rsi": round(rsi, 1) if rsi is not None else None}
        if abs(d200) <= SCREENER_ZONA_MA200_PCT:
            zona.append(fila)
        if d200 > 0 and rsi is not None and SCREENER_PULLBACK_RSI_MIN <= rsi <= SCREENER_PULLBACK_RSI_MAX:
            pull.append(fila)
        racha, dia = _num(r.get("Racha_bajista")), _num(r.get("Var_dia_%"))
        if racha is not None and dia is not None and racha >= SCREENER_REBOTE_RACHA_MIN and dia > 0:
            reb.append({**fila, "racha": int(racha), "dia": round(dia, 2)})
    zona.sort(key=lambda f: abs(f["d200"]))
    pull.sort(key=lambda f: f["rsi"])
    reb.sort(key=lambda f: -f["dia"])
    return {"zona_ma200": zona, "pullback": pull, "rebote": reb}


def _leer_jsonl(ruta):
    out = []
    if not os.path.exists(ruta):
        return out
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            try:
                out.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return out


def registrar(df_rs, precios, benchmark, ahora=None, degradada=False):
    """Agrega la linea del ultimo dia cerrado si falta y recalcula la medicion. Nunca rompe la corrida.
    Devuelve la fecha registrada o None."""
    try:
        if degradada or df_rs is None or len(df_rs) == 0:
            return None
        ahora = ahora or datetime.now(timezone.utc)
        spy = precios.get(benchmark)
        if spy is None or spy.dropna().empty:
            return None
        spy = spy.dropna()
        fecha = str(spy.index[-1])[:10]
        hoy = ahora.strftime("%Y-%m-%d")
        cerrado = fecha < hoy or (ahora.hour, ahora.minute) >= HORA_CIERRE_UTC
        if not cerrado:
            return None
        if any(d.get("fecha") == fecha for d in _leer_jsonl(RUTA_LOG)):
            return None
        ranking = df_rs.to_dict(orient="records") if hasattr(df_rs, "to_dict") else list(df_rs)
        l = listas(ranking)
        linea = {"fecha": fecha, "spy": round(float(spy.iloc[-1]), 2), **l}
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(linea, ensure_ascii=False, separators=(",", ":")) + "\n")
        log.info(f"Screener {fecha}: zona_ma200={len(l['zona_ma200'])}, pullback={len(l['pullback'])}, rebote={len(l['rebote'])} -> {RUTA_LOG}")
        medir(ahora)
        return fecha
    except Exception as e:
        log.error(f"Screener fallo, no afecta al resto de la corrida: {e}")
        return None


def medir(ahora=None):
    """Recalcula data/auditoria_screener.json desde el log y los cierres diarios."""
    try:
        entradas = _leer_jsonl(RUTA_LOG)
        cierres = {d["fecha"]: d["c"] for d in _leer_jsonl(RUTA_CIERRES) if d.get("fecha") and d.get("c")}
        fechas = sorted(cierres)
        pos = {f: i for i, f in enumerate(fechas)}
        cache_univ = {}

        def univ(f0, f1):
            k = (f0, f1)
            if k not in cache_univ:
                a, b = cierres[f0], cierres[f1]
                r = [b[t] / a[t] - 1 for t in a if t in b and a[t] and a[t] > 0 and t != "SPY"]
                cache_univ[k] = sum(r) / len(r) if r else None
            return cache_univ[k]

        res = {l: {str(h): {"obs": [], "fechas": set()} for h in HORIZONTES} for l in LISTAS}
        for e in entradas:
            f0 = e.get("fecha")
            if f0 not in pos:
                continue
            i = pos[f0]
            for h in HORIZONTES:
                if i + h >= len(fechas):
                    continue
                f1 = fechas[i + h]
                c0, c1 = cierres[f0], cierres[f1]
                if not c0.get("SPY") or not c1.get("SPY"):
                    continue
                spy_r = c1["SPY"] / c0["SPY"] - 1
                u = univ(f0, f1)
                for l in LISTAS:
                    for fila in e.get(l, []):
                        t = fila.get("t")
                        if t in c0 and t in c1 and c0[t] and c0[t] > 0:
                            r = c1[t] / c0[t] - 1
                            res[l][str(h)]["obs"].append((r, spy_r, u))
                            res[l][str(h)]["fechas"].add(f0)
        salida = {"actualizado": (ahora or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "dias_registrados": len(entradas),
                  "primer_registro": entradas[0]["fecha"] if entradas else None,
                  "ultimo_registro": entradas[-1]["fecha"] if entradas else None,
                  "listas": {}}
        for l in LISTAS:
            hs = {}
            for h in HORIZONTES:
                obs = res[l][str(h)]["obs"]
                n = len(obs)
                if n == 0:
                    hs[str(h)] = {"n": 0, "dias": 0}
                    continue
                m = lambda xs: round(sum(xs) / len(xs) * 100, 2)
                con_u = [(r, s, u) for r, s, u in obs if u is not None]
                hs[str(h)] = {
                    "n": n, "dias": len(res[l][str(h)]["fechas"]),
                    "ret_prom_%": m([r for r, _, _ in obs]),
                    "vs_spy_pp": m([r - s for r, s, _ in obs]),
                    "vs_universo_pp": m([r - u for r, _, u in con_u]) if con_u else None,
                    "pct_positivos": round(sum(1 for r, _, _ in obs if r > 0) / n * 100, 1),
                    "pct_supera_spy": round(sum(1 for r, s, _ in obs if r > s) / n * 100, 1),
                }
            salida["listas"][l] = {"descripcion": DESCRIPCION[l], "horizontes": hs}
        tmp = RUTA_AUD + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=2)
        os.replace(tmp, RUTA_AUD)
        return salida
    except Exception as e:
        log.error(f"Medicion del screener fallo, no afecta al resto de la corrida: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if "--medir" in sys.argv:
        r = medir()
        print(json.dumps(r, ensure_ascii=False, indent=2) if r else "sin datos")
    else:
        print(__doc__)
