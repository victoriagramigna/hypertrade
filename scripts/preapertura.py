"""
Aviso "Antes de la apertura" -- aparte del radar: no toca el ranking ni la Auditoria.

Corre ~10:10 hora argentina (antes de que abra Wall Street) y arma dos listas:
  1) Posibles gaps al abrir: papeles cuyo PREMARKET ya sube 2% o mas contra el cierre
     anterior y que cumplen la macrotendencia de la alerta "Gap alcista con
     macrotendencia" (cierre previo sobre su SMA200 y precio en maximos de las ultimas
     10 ruedas).
  2) Balances de hoy o de manana (antes de la apertura / despues del cierre) y cuantas
     veces ese papel se movio 3% o mas en sus balances anteriores.

Son listas para MIRAR, no senales de compra: el premarket tiene poco volumen y se revierte
seguido; el balance anuncia movimiento, no direccion.

Cada aviso se guarda en data/log_preapertura.jsonl (solo se agregan lineas, nunca se
editan) y en cada corrida se mide, con el cierre real, como le fue a los avisos de dias
anteriores (data/auditoria_preapertura.json), contra la frecuencia normal de gaps.
"""
import json, logging, os, sys, time
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

log = logging.getLogger("preapertura")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

UMBRAL_PM_PCT = 2.0         # premarket: sube al menos 2% contra el cierre previo
UMBRAL_GAP_PCT = 3.0        # "gap real" = cierra al menos +3% contra el cierre previo (regla del radar)
VENTANA_MAX = 10
RUTA_LOG = "data/log_preapertura.jsonl"
RUTA_SNAP = "data/preapertura.json"
RUTA_AUD = "data/auditoria_preapertura.json"
RUTA_CACHE_BAL = "data/balances_cache.json"
RUTA_ULTIMO = "data/ultimo.json"
ET = ZoneInfo("America/New_York")
DISCLAIMER = "\n\n⚠️ Lista para mirar, no es señal de compra ni de venta. Premarket = poco volumen, se revierte seguido."


# ---------------------------------------------------------------- utilidades
def _json(ruta, defecto):
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def _log_leer():
    out = []
    try:
        with open(RUTA_LOG, "r", encoding="utf-8") as f:
            for l in f:
                l = l.strip()
                if l:
                    try:
                        out.append(json.loads(l))
                    except Exception:
                        pass
    except FileNotFoundError:
        pass
    return out


def _log_agregar(eventos):
    if not eventos:
        return
    with open(RUTA_LOG, "a", encoding="utf-8") as f:
        for e in eventos:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def cargar_universo():
    u = _json(RUTA_ULTIMO, {})
    return {r["Ticker"]: r.get("Sector", "otro") for r in u.get("ranking", []) if r.get("Ticker")}


def _proximo_dia_habil(d: date) -> date:
    n = d + timedelta(days=1)
    while n.weekday() >= 5:
        n += timedelta(days=1)
    return n


# ---------------------------------------------------------------- descargas (Yahoo)
def _partir(df, tickers):
    """yf.download(group_by='ticker') -> dict ticker -> DataFrame sin NaN totales."""
    out = {}
    if df is None or len(df) == 0:
        return out
    if isinstance(df.columns, pd.MultiIndex):
        for t in tickers:
            if t in df.columns.get_level_values(0):
                s = df[t].dropna(how="all")
                if len(s):
                    out[t] = s
    else:
        out[tickers[0]] = df.dropna(how="all")
    return out


def bajar_diarios(tickers, periodo="1y"):
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 120):
        lote = tickers[i:i + 120]
        try:
            df = yf.download(lote, period=periodo, interval="1d", auto_adjust=True, group_by="ticker",
                             threads=True, progress=False)
            out.update(_partir(df, lote))
        except Exception as e:
            log.warning(f"Lote diario fallo ({e})")
    return out


def bajar_premarket(tickers):
    import yfinance as yf
    out = {}
    for i in range(0, len(tickers), 120):
        lote = tickers[i:i + 120]
        try:
            df = yf.download(lote, period="2d", interval="1m", prepost=True, auto_adjust=False,
                             group_by="ticker", threads=True, progress=False)
            out.update(_partir(df, lote))
        except Exception as e:
            log.warning(f"Lote premarket fallo ({e})")
    return out


def fechas_balance_yahoo(ticker):
    """Lista de datetimes (hora de Nueva York, sin tz) de balances pasados y proximos."""
    import yfinance as yf
    try:
        d = yf.Ticker(ticker).get_earnings_dates(limit=24)
    except Exception:
        return None
    if d is None or len(d) == 0:
        return None
    idx = pd.DatetimeIndex(d.index)
    if idx.tz is not None:
        idx = idx.tz_convert(ET).tz_localize(None)
    return sorted(set(idx.to_pydatetime().tolist()))


# ---------------------------------------------------------------- calculo
def premarket_de_hoy(df, hoy_et: date):
    """(ultimo precio, volumen acumulado) de las barras de premarket de hoy, o None."""
    if df is None or len(df) == 0 or "Close" not in df:
        return None
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    idx = idx.tz_convert(ET)
    m = (idx.date == hoy_et) & ((idx.hour < 9) | ((idx.hour == 9) & (idx.minute < 30)))
    if not m.any():
        return None
    sub = df[m].dropna(subset=["Close"])
    if len(sub) == 0:
        return None
    vol = float(sub["Volume"].fillna(0).sum()) if "Volume" in sub else 0.0
    return float(sub["Close"].iloc[-1]), vol


def evaluar_gap(daily: pd.DataFrame, pm_precio: float, pm_vol: float, hoy_et: date):
    """Aplica la macrotendencia del radar. Devuelve dict o None si faltan datos."""
    d = daily.copy()
    d.index = pd.DatetimeIndex(d.index).tz_localize(None).normalize() if pd.DatetimeIndex(d.index).tz is None else pd.DatetimeIndex(d.index).tz_convert(None).normalize()
    d = d[d.index.date < hoy_et].dropna(subset=["Close"])
    if len(d) < 200:
        return None
    cierre = d["Close"]
    prev = float(cierre.iloc[-1])
    sma200 = float(cierre.iloc[-200:].mean())
    max10 = float(cierre.iloc[-VENTANA_MAX:].max())
    vol20 = float(d["Volume"].iloc[-20:].mean()) if "Volume" in d else 0.0
    pct = (pm_precio / prev - 1) * 100
    return {
        "cierre_previo": round(prev, 2), "pm_precio": round(pm_precio, 2), "pm_pct": round(pct, 2),
        "pm_vol": int(pm_vol), "pm_vol_rel_pct": round(pm_vol / vol20 * 100, 2) if vol20 > 0 else None,
        "sobre_sma200": prev > sma200, "en_maximos": pm_precio >= 0.999 * max10,
        "macro": bool(prev > sma200 and pm_precio >= 0.999 * max10),
    }


def reaccion_balance(fecha_dt: datetime) -> date:
    """Dia en que el mercado reacciona al balance: antes de la apertura -> ese dia; si no, el siguiente habil."""
    return fecha_dt.date() if fecha_dt.hour < 12 else _proximo_dia_habil(fecha_dt.date())


def balance_cerca(fechas, hoy_et: date):
    """'hoy' / 'manana' si la reaccion al balance cae hoy o el proximo dia habil; si no None."""
    sig = _proximo_dia_habil(hoy_et)
    for f in fechas or []:
        r = reaccion_balance(f)
        if r == hoy_et:
            return "hoy", f
        if r == sig:
            return "manana", f
    return None, None


def historial_reacciones(daily_largo: pd.DataFrame, fechas, hoy_et: date):
    """Como se movio el papel el dia de reaccion en balances PASADOS."""
    if daily_largo is None or len(daily_largo) < 30:
        return {"n": 0}
    c = daily_largo["Close"].dropna()
    idx = pd.DatetimeIndex(c.index)
    idx = idx.tz_localize(None).normalize() if idx.tz is None else idx.tz_convert(None).normalize()
    c = pd.Series(c.values, index=idx)
    rets = []
    for f in fechas or []:
        r = reaccion_balance(f)
        if r >= hoy_et:
            continue
        rd = pd.Timestamp(r)
        if rd not in c.index:
            continue
        i = c.index.get_loc(rd)
        if i == 0:
            continue
        rets.append((c.iloc[i] / c.iloc[i - 1] - 1) * 100)
    if not rets:
        return {"n": 0}
    a = np.array(rets)
    return {"n": int(len(a)), "sube3": int((a >= 3).sum()), "baja3": int((a <= -3).sum()),
            "mov_abs_mediano_pct": round(float(np.median(np.abs(a))), 1),
            "ultimos": [round(float(x), 1) for x in a[-4:]]}


# ---------------------------------------------------------------- auditoria de los avisos
def _cierre_y_apertura(daily, fecha_iso):
    d = daily.dropna(subset=["Close"])
    idx = pd.DatetimeIndex(d.index)
    idx = idx.tz_localize(None).normalize() if idx.tz is None else idx.tz_convert(None).normalize()
    d = d.set_axis(idx)
    ts = pd.Timestamp(fecha_iso)
    if ts not in d.index:
        return None
    i = d.index.get_loc(ts)
    if i == 0:
        return None
    prev = float(d["Close"].iloc[i - 1])
    return {"ret_cierre_pct": round((float(d["Close"].iloc[i]) / prev - 1) * 100, 2),
            "gap_apertura_pct": round((float(d["Open"].iloc[i]) / prev - 1) * 100, 2) if "Open" in d else None}


def _base_del_dia(diarios, fecha_iso):
    """Frecuencia normal: de los papeles con macrotendencia ese dia, que % cerro +3% o mas."""
    n = k = 0
    ts = pd.Timestamp(fecha_iso)
    for t, d in diarios.items():
        try:
            c = d["Close"].dropna()
            idx = pd.DatetimeIndex(c.index)
            idx = idx.tz_localize(None).normalize() if idx.tz is None else idx.tz_convert(None).normalize()
            c = pd.Series(c.values, index=idx)
            if ts not in c.index:
                continue
            i = c.index.get_loc(ts)
            if i < 200:
                continue
            prev = c.iloc[i - 1]
            if not prev > c.iloc[i - 200:i].mean():
                continue
            n += 1
            if (c.iloc[i] / prev - 1) * 100 >= UMBRAL_GAP_PCT:
                k += 1
        except Exception:
            continue
    return {"n": n, "pct_gap": round(k / n * 100, 2) if n else None}


def actualizar_auditoria(diarios, hoy_et: date):
    aud = _json(RUTA_AUD, {"evaluados": [], "base_por_fecha": {}})
    hechos = {e["id"] for e in aud.get("evaluados", [])}
    nuevos = 0
    for ev in _log_leer():
        if ev.get("evento") != "aviso" or ev["id"] in hechos:
            continue
        if date.fromisoformat(ev["fecha"]) >= hoy_et:
            continue
        d = diarios.get(ev["ticker"])
        if d is None:
            continue
        r = _cierre_y_apertura(d, ev["fecha"])
        if r is None:
            continue
        if ev["fecha"] not in aud["base_por_fecha"]:
            aud["base_por_fecha"][ev["fecha"]] = _base_del_dia(diarios, ev["fecha"])
        aud["evaluados"].append({"id": ev["id"], "fecha": ev["fecha"], "ticker": ev["ticker"], "tipo": ev["tipo"],
                                 "pm_pct": ev.get("pm_pct"), "balance": ev.get("balance"), **r,
                                 "gap_real": r["ret_cierre_pct"] >= UMBRAL_GAP_PCT})
        nuevos += 1
    res = {}
    for tipo in ("gap_candidato", "balance"):
        xs = [e for e in aud["evaluados"] if e["tipo"] == tipo]
        if not xs:
            continue
        rets = np.array([e["ret_cierre_pct"] for e in xs])
        bases = [aud["base_por_fecha"][e["fecha"]]["pct_gap"] for e in xs
                 if aud["base_por_fecha"].get(e["fecha"], {}).get("pct_gap") is not None]
        res[tipo] = {"n": len(xs), "gap_real": int(sum(e["gap_real"] for e in xs)),
                     "pct_gap_real": round(sum(e["gap_real"] for e in xs) / len(xs) * 100, 1),
                     "mediana_ret_cierre_pct": round(float(np.median(rets)), 2),
                     "mov_abs_mediano_pct": round(float(np.median(np.abs(rets))), 2),
                     "pct_gap_normal": round(float(np.mean(bases)), 1) if bases else None}
    aud["resumen"] = res
    aud["actualizado_utc"] = datetime.now(timezone.utc).isoformat()
    aud["nota"] = ("Se mide el cierre del dia del aviso contra el cierre anterior. 'pct_gap_normal' es la frecuencia habitual "
                   "de gaps de +3% entre los papeles con macrotendencia ese mismo dia (con muestras chicas no concluye nada).")
    if nuevos or not os.path.exists(RUTA_AUD):
        with open(RUTA_AUD, "w", encoding="utf-8") as f:
            json.dump(aud, f, ensure_ascii=False, indent=1)
    return nuevos


# ---------------------------------------------------------------- balances (cache semanal)
def actualizar_cache_balances(tickers, fechas_fn, hoy_et: date, presupuesto_seg=420):
    cache = _json(RUTA_CACHE_BAL, {"por_ticker": {}})
    pt = cache.setdefault("por_ticker", {})
    t0 = time.time()
    hechos = 0
    for t in tickers:
        info = pt.get(t)
        if info and info.get("bajado") and (hoy_et - date.fromisoformat(info["bajado"])).days < 7:
            continue
        if time.time() - t0 > presupuesto_seg:
            break
        f = fechas_fn(t)
        pt[t] = {"bajado": hoy_et.isoformat(), "fechas": [x.isoformat() for x in f] if f else []}
        hechos += 1
    cache["actualizado"] = hoy_et.isoformat()
    with open(RUTA_CACHE_BAL, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False)
    log.info(f"Cache de balances: {hechos} papeles actualizados")
    return {t: [datetime.fromisoformat(x) for x in v.get("fechas", [])] for t, v in pt.items()}


# ---------------------------------------------------------------- mensaje
def armar_mensaje(snap):
    L = ["🌅 <b>Antes de la apertura</b> — lista para mirar"]
    if snap["candidatos"]:
        L.append("\n<b>Posibles gaps al abrir</b> (premarket +2% o más, con macrotendencia):")
        for c in snap["candidatos"][:8]:
            vr = f", volumen {c['pm_vol_rel_pct']}% del diario" if c.get("pm_vol_rel_pct") is not None else ""
            L.append(f"• {c['ticker']}  premarket {c['pm_pct']:+.1f}% (cierre previo {c['cierre_previo']}{vr})")
    elif not snap["premarket_disponible"]:
        L.append("\nHoy no hay datos de premarket (feriado o Yahoo sin datos).")
    else:
        L.append("\nNingún papel con macrotendencia cotiza hoy +2% o más en premarket.")
    if snap["balances"]:
        L.append("\n<b>Balances de hoy y mañana</b> (anuncian movimiento, no dirección):")
        hoy = date.fromisoformat(snap["fecha_et"])
        for b in snap["balances"][:10]:
            f = datetime.fromisoformat(b["fecha_balance"])
            dia = "hoy" if f.date() == hoy else "mañana"
            momento = "antes de la apertura" if f.hour < 12 else "después del cierre"
            h = b.get("historial", {})
            txt = ""
            if h.get("n"):
                txt = f" — en {h['n']} balances previos: {h['sube3']} subió ≥3%, {h['baja3']} bajó ≥3%"
            L.append(f"• {b['ticker']}  presenta {dia} {momento}{txt}")
    return "\n".join(L) + DISCLAIMER


# ---------------------------------------------------------------- corrida
def correr(ahora=None, diarios_fn=None, premarket_fn=None, fechas_fn=None, historial_fn=None, enviar=False):
    ahora = ahora or datetime.now(timezone.utc)
    hoy_et = ahora.astimezone(ET).date()
    if hoy_et.weekday() >= 5:
        log.info("Fin de semana -- no se corre"); return None
    universo = cargar_universo()
    if not universo:
        log.error("Sin universo (data/ultimo.json)"); return None
    tickers = sorted(universo)
    diarios = (diarios_fn or bajar_diarios)(tickers)
    log.info(f"Diarios: {len(diarios)}/{len(tickers)} papeles")
    if len(diarios) < 100:
        log.error("Muy pocos datos diarios -- se aborta"); return None

    # 1) auditoria de avisos de dias anteriores (usa los diarios recien bajados)
    try:
        log.info(f"Auditoria: {actualizar_auditoria(diarios, hoy_et)} avisos nuevos medidos")
    except Exception as e:
        log.warning(f"Auditoria fallo ({e})")

    # 2) premarket
    pms = (premarket_fn or bajar_premarket)(tickers)
    candidatos, premarket_ok = [], False
    for t, df in pms.items():
        pm = premarket_de_hoy(df, hoy_et)
        if pm is None or t not in diarios:
            continue
        premarket_ok = True
        ev = evaluar_gap(diarios[t], pm[0], pm[1], hoy_et)
        if ev and ev["pm_pct"] >= UMBRAL_PM_PCT and ev["macro"]:
            candidatos.append({"ticker": t, "sector": universo.get(t), **ev})
    candidatos.sort(key=lambda x: -x["pm_pct"])

    # 3) balances de hoy y mañana
    fechas = actualizar_cache_balances(tickers, fechas_fn or fechas_balance_yahoo, hoy_et)
    balances = []
    for t in tickers:
        cuando, f = balance_cerca(fechas.get(t), hoy_et)
        if cuando:
            balances.append({"ticker": t, "sector": universo.get(t), "cuando": cuando, "fecha_balance": f.isoformat()})
    for b in balances:
        try:
            largo = (historial_fn or (lambda t: bajar_diarios([t], "5y").get(t)))(b["ticker"])
            b["historial"] = historial_reacciones(largo, fechas.get(b["ticker"]), hoy_et)
        except Exception as e:
            b["historial"] = {"n": 0}
    balances.sort(key=lambda x: (x["cuando"] != "hoy", x["ticker"]))

    snap = {"generado_utc": ahora.isoformat(), "fecha_et": hoy_et.isoformat(), "premarket_disponible": premarket_ok,
            "umbral_premarket_pct": UMBRAL_PM_PCT, "candidatos": candidatos, "balances": balances}
    with open(RUTA_SNAP, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)

    # 4) registro append-only (un aviso por papel/tipo/dia)
    existentes = {e.get("id") for e in _log_leer()}
    nuevos = []
    for c in candidatos:
        i = f"PRE-{c['ticker']}-{hoy_et.isoformat()}-gap_candidato"
        if i not in existentes:
            nuevos.append({"evento": "aviso", "id": i, "fecha": hoy_et.isoformat(), "hora_utc": ahora.strftime("%H:%M"),
                           "tipo": "gap_candidato", "ticker": c["ticker"], "pm_pct": c["pm_pct"], "pm_precio": c["pm_precio"],
                           "cierre_previo": c["cierre_previo"], "pm_vol_rel_pct": c["pm_vol_rel_pct"]})
    for b in balances:
        i = f"PRE-{b['ticker']}-{hoy_et.isoformat()}-balance"
        if i not in existentes:
            nuevos.append({"evento": "aviso", "id": i, "fecha": hoy_et.isoformat(), "hora_utc": ahora.strftime("%H:%M"),
                           "tipo": "balance", "ticker": b["ticker"], "balance": b["cuando"]})
    _log_agregar(nuevos)
    log.info(f"{len(candidatos)} candidatos, {len(balances)} balances, {len(nuevos)} avisos nuevos en el registro")

    if enviar and (candidatos or balances):
        from telegram_bot import enviar_mensaje
        enviar_mensaje(os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID"), armar_mensaje(snap))
    return snap


if __name__ == "__main__":
    sys.path.insert(0, "scripts")
    correr(enviar=os.environ.get("PREAPERTURA_ENVIAR", "1") == "1")
