"""
Top 30: ¿los que ENTRAN le ganan al SPY? (pedido de Victoria, 9/10/2026).

Mide, para cada ticker que ENTRÓ al Top 30 (de Fuerza Relativa y de Radar Score), cuánto rindió
desde el cierre previo a la foto en que apareció hasta el último cierre, contra el SPY en el mismo
período. Cuenta TODOS los que entraron, también los que ya salieron (si no, solo se verían los
que salieron bien parados y el resultado sería engañosamente bueno).

Es 100% aditivo: solo LEE data/top30_diario.jsonl y data/top30_radar_diario.jsonl (que ya existen) y
escribe sus propios archivos. No toca el Top 30, el ranking, las alertas ni la Auditoría.

  data/log_top30_ingresos.jsonl  -- append-only: una línea por ingreso con su precio de entrada
                                    (una vez escrito, no se reescribe nunca)
  data/top30_retorno.json        -- foto para la app (se regenera cada vez)

Regla de fechas: la foto de un día D la guarda la primera corrida del día, ANTES de que abra el
mercado, así que refleja el último cierre anterior a D. El precio de entrada es ese cierre.
Un ticker "entra" si está en la foto D y no estaba en la foto anterior. La primera foto no genera
ingresos (no hay contra qué comparar).
"""
import json
import logging
import os
import statistics
from datetime import datetime, timezone

log = logging.getLogger("radar.top30_retorno")

LISTAS = {
    "fr": ("data/top30_diario.jsonl", "Fuerza Relativa"),
    "radar": ("data/top30_radar_diario.jsonl", "Radar Score"),
}
RUTA_LOG = "data/log_top30_ingresos.jsonl"
RUTA_SALIDA = "data/top30_retorno.json"
MIN_SESIONES = 1   # para entrar al resumen, el ingreso tiene que tener al menos 1 sesión transcurrida


def _leer_jsonl(ruta):
    if not os.path.exists(ruta):
        return []
    out = []
    with open(ruta, encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if not l:
                continue
            try:
                out.append(json.loads(l))
            except json.JSONDecodeError:
                continue
    return out


def detectar_ingresos(fotos):
    """fotos: lista [{fecha, tickers}] -> lista de (fecha_foto, ticker) que entraron."""
    fotos = sorted((f for f in fotos if f.get("fecha")), key=lambda f: f["fecha"])
    out = []
    for i in range(1, len(fotos)):
        antes = set(fotos[i - 1].get("tickers", []))
        for t in sorted(set(fotos[i].get("tickers", [])) - antes):
            out.append((fotos[i]["fecha"], t))
    return out


def _cierre_previo(serie, fecha):
    """Último cierre con fecha ESTRICTAMENTE anterior a `fecha` (YYYY-MM-DD). -> (fecha_iso, precio)|None"""
    previos = serie[[str(i)[:10] < fecha for i in serie.index]]
    previos = previos.dropna()
    if previos.empty:
        return None
    return str(previos.index[-1])[:10], float(previos.iloc[-1])


def bajar_precios(tickers, periodo="6mo"):
    import yfinance as yf
    out = {}
    tickers = sorted(set(tickers))
    for i in range(0, len(tickers), 100):
        lote = tickers[i:i + 100]
        try:
            df = yf.download(lote, period=periodo, interval="1d", auto_adjust=True,
                             group_by="ticker", threads=True, progress=False)
        except Exception as e:
            log.warning(f"Lote fallo ({e})")
            continue
        for t in lote:
            try:
                s = (df[t]["Close"] if len(lote) > 1 else df["Close"]).dropna()
                if len(s):
                    out[t] = s
            except Exception:
                continue
    return out


def correr(precios_fn=bajar_precios, ahora=None):
    ahora = ahora or datetime.now(timezone.utc)
    fotos_por_lista = {k: _leer_jsonl(v[0]) for k, v in LISTAS.items()}
    ingresos = {k: detectar_ingresos(f) for k, f in fotos_por_lista.items()}
    ya = {e.get("id") for e in _leer_jsonl(RUTA_LOG)}
    tickers = {t for k in ingresos for _, t in ingresos[k]} | {"SPY"}
    for k, fotos in fotos_por_lista.items():
        if fotos:
            tickers |= set(max(fotos, key=lambda f: f["fecha"]).get("tickers", []))
    precios = precios_fn(sorted(tickers))
    spy = precios.get("SPY")
    if spy is None or len(spy) < 2:
        log.error("Sin precios del SPY: no se puede medir.")
        return None
    ultima_fecha = str(spy.index[-1])[:10]
    spy_hoy = float(spy.iloc[-1])

    nuevos_log, listas_out = [], {}
    for k, (ruta, nombre) in LISTAS.items():
        fotos = fotos_por_lista[k]
        actuales = set(max(fotos, key=lambda f: f["fecha"]).get("tickers", [])) if fotos else set()
        filas, sin_precio = [], 0
        for fecha_foto, t in ingresos[k]:
            ident = f"T30-{k}-{t}-{fecha_foto}"
            s = precios.get(t)
            if s is None:
                sin_precio += 1
                continue
            ce = _cierre_previo(s, fecha_foto)
            cs = _cierre_previo(spy, fecha_foto)
            if ce is None or cs is None:
                sin_precio += 1
                continue
            fecha_px, entrada = ce
            _, spy_ent = cs
            if ident not in ya:
                nuevos_log.append({"evento": "ingreso_top30", "id": ident, "lista": k, "ticker": t,
                                   "fecha_foto": fecha_foto, "fecha_precio": fecha_px,
                                   "precio_entrada": round(entrada, 4), "spy_entrada": round(spy_ent, 4),
                                   "registrado": ahora.isoformat()})
                ya.add(ident)
            actual = float(s.iloc[-1])
            sesiones = int(sum(1 for i in spy.index if fecha_px < str(i)[:10] <= ultima_fecha))
            ret = (actual / entrada - 1) * 100
            ret_spy = (spy_hoy / spy_ent - 1) * 100
            filas.append({"ticker": t, "fecha_foto": fecha_foto, "fecha_precio": fecha_px, "sesiones": sesiones,
                          "entrada": round(entrada, 2), "actual": round(actual, 2),
                          "ret_pct": round(ret, 2), "spy_pct": round(ret_spy, 2),
                          "exceso_pct": round(ret - ret_spy, 2), "sigue_en_top": t in actuales})
        med = [f for f in filas if f["sesiones"] >= MIN_SESIONES]
        resumen = None
        if med:
            ex = [f["exceso_pct"] for f in med]
            resumen = {"n": len(med), "ret_medio_pct": round(statistics.mean(f["ret_pct"] for f in med), 2),
                       "spy_medio_pct": round(statistics.mean(f["spy_pct"] for f in med), 2),
                       "exceso_medio_pct": round(statistics.mean(ex), 2),
                       "exceso_mediano_pct": round(statistics.median(ex), 2),
                       "le_ganaron_spy": sum(1 for e in ex if e > 0),
                       "pct_le_ganaron_spy": round(100 * sum(1 for e in ex if e > 0) / len(ex), 1),
                       "siguen_en_top": sum(1 for f in med if f["sigue_en_top"])}
        listas_out[k] = {"nombre": nombre, "ingresos": sorted(filas, key=lambda f: (f["fecha_foto"], f["ticker"]), reverse=True),
                         "resumen": resumen, "sin_precio": sin_precio}

    if nuevos_log:
        with open(RUTA_LOG, "a", encoding="utf-8") as f:
            for e in nuevos_log:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    salida = {"generado_utc": ahora.isoformat(), "fecha_ultimo_cierre": ultima_fecha, "listas": listas_out,
              "nota": "Rendimiento desde el cierre anterior a la foto en que el ticker entró al Top 30 hasta el último cierre, "
                      "contra el SPY en el mismo período. Cuenta a todos los que entraron, también a los que ya salieron. "
                      "Es un dato para mirar: no garantiza lo que pase después."}
    with open(RUTA_SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
    log.info(f"Ingresos nuevos registrados: {len(nuevos_log)}")
    return salida


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    correr()
