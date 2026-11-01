"""
Bases VCP con contracciones reales (definicion del Estudio VCP v4) -- seguimiento descriptivo.

ADITIVO: no usa ni modifica ninguna senal del radar, la Auditoria ni la Watchlist VCP. Tiene su
propio estado (data/vcp_v4.json) y su propia bitacora, que solo se agrega al final (data/log_vcp_v4.jsonl).
NO envia Telegram. Se evalua UNA vez por rueda cerrada.

Definicion (la misma funcion del estudio: estudio_vcp_v4._base): giros reales (maximos y minimos del dia,
confirmados 5 ruedas despues), 2 a 4 contracciones seguidas de profundidad decreciente, la primera >= 10%, la
ultima <= 10%, ultimo maximo a menos de 5% del maximo de la base. Pivote = ultimo maximo; stop = minimo de la
ultima contraccion. En tendencia: cierre a menos de 15% del maximo de 52 semanas, sobre la media de 50 y FR >= 50.
Estados: formacion (sin cerrar sobre el pivote) -> ruptura (primer cierre sobre el pivote; pivote y stop quedan
fijos; se sigue 20 ruedas o hasta que el minimo del dia toque el stop).
Bitacora: alta, ruptura, resultado a 5/10/20 ruedas (retorno y exceso vs SPY al cierre), invalidada (con la salida
simulada en el stop, o en la apertura si abrio por debajo), fin_seguimiento y salida_formacion.

Limites (decirlo siempre): el estudio historico (1 anio, un solo regimen) NO valido ventaja: V4A +1,5 de exceso a
20 ruedas contra +0,4 de la base sin forma, pero con intervalos que incluyen el cero, dependiente del largo del giro
y concentrado en un trimestre. Los umbrales de la base son mios. FR = RS_Score del radar.
"""
import json
import logging
import os
from datetime import datetime, timezone

import numpy as np

log = logging.getLogger("radar.vcp_base_v4")

RUTA_ESTADO = "data/vcp_v4.json"
RUTA_LOG = "data/log_vcp_v4.jsonl"
K = 5
RS_MIN = 50.0
CERCA_MAX52 = 0.85
VOL_RUPTURA = 1.5
SEGUIMIENTO_RUEDAS = 20
HORIZONTES = (5, 10, 20)
MIN_RUEDAS = 200


def _ohlc_hasta(df, fecha):
    idx = [str(d)[:10] for d in df.index]
    n = sum(1 for d in idx if d <= fecha)
    return df.iloc[:n]


def _plantilla(c, rs):
    """Plantilla de tendencia de Minervini (9 condiciones) a la ultima rueda; None si faltan datos."""
    if len(c) < 221 or rs is None:
        return None
    m50, m150, m200 = c[-50:].mean(), c[-150:].mean(), c[-200:].mean()
    m150_ant, m200_ant = c[-170:-20].mean(), c[-220:-20].mean()
    mx, mn = np.nanmax(c[-252:]), np.nanmin(c[-252:])
    x = c[-1]
    return bool(x > m150 and x > m200 and m150 > m150_ant and m200 > m200_ant and m50 > m150 and m50 > m200
                and x >= 1.3 * mn and x >= 0.75 * mx and rs >= 70)


def _evaluar(df, rs, vol_ok=True):
    """df: OHLCV hasta la rueda a evaluar. Devuelve dict con la base vigente (o None) y datos del dia."""
    from estudio_vcp_v4 import _giros, _agregar, _base
    c, h, l, o = (df[k].values.astype(float) for k in ("Close", "High", "Low", "Open"))
    n = len(c)
    if n < MIN_RUEDAS or np.isnan(c[-60:]).any() or np.isnan(h[-60:]).any() or np.isnan(l[-60:]).any():
        return None
    h = np.where(np.isnan(h), c, h)
    l = np.where(np.isnan(l), c, l)
    giros = _giros(h, l, K)
    zz = []
    for j in range(n):
        e = giros.get(j)
        if e:
            _agregar(zz, e)
    base = _base(zz, n - 1) if zz and zz[-1][0] == "L" else None
    max52 = float(np.nanmax(c[-252:]))
    sma50 = float(np.mean(c[-50:]))
    tendencia = bool(c[-1] >= CERCA_MAX52 * max52 and c[-1] > sma50 and rs is not None and rs >= RS_MIN)
    v = df["Volume"].values.astype(float) if vol_ok and "Volume" in df else None
    vol_rel = None
    if v is not None and len(v) == n:
        p = np.nanmean(v[-51:-1])
        if p and p > 0 and not np.isnan(v[-1]):
            vol_rel = float(v[-1] / p)
    return dict(base=base, cierre=float(c[-1]), cierre_ant=float(c[-2]), minimo=float(l[-1]), apertura=float(o[-1]),
                tendencia=tendencia, plantilla=_plantilla(c, rs), vol_rel=vol_rel,
                dist_max52_pct=(c[-1] / max52 - 1) * 100)


def _cargar(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def procesar_vcp_v4(precios, precios_ohlc, benchmark, tickers, modo, ahora=None, ultimo=None):
    """Una pasada por rueda cerrada. Nunca lanza excepcion hacia afuera."""
    try:
        return _procesar(precios, precios_ohlc, benchmark, tickers, modo, ahora, ultimo)
    except Exception as e:
        log.warning(f"Bases VCP v4: fallo esta pasada ({e})")
        return {"error": str(e)}


def _procesar(precios, precios_ohlc, benchmark, tickers, modo, ahora, ultimo):
    from vcp_watchlist import NY, MINUTOS_POST_CIERRE, RUTA_ULTIMO, _hasta
    ahora = ahora or datetime.now(timezone.utc)
    ny = ahora.astimezone(NY)
    hoy_ny = ny.strftime("%Y-%m-%d")
    post_cierre = ny.weekday() < 5 and ny >= ny.replace(hour=16, minute=MINUTOS_POST_CIERRE, second=0, microsecond=0)
    spy_full = precios.get(benchmark)
    if spy_full is None or spy_full.dropna().empty:
        return {}
    spy = spy_full.dropna()
    fecha_proc = str(spy.index[-1])[:10]
    if fecha_proc == hoy_ny and not post_cierre:       # barra del dia todavia abierta: se usa la anterior
        spy = _hasta(spy, str(spy.index[-2])[:10])
        fecha_proc = str(spy.index[-1])[:10]
    prev = _cargar(RUTA_ESTADO, {})
    if prev.get("ultima_fecha") == fecha_proc:
        return {"ya_procesado": fecha_proc}
    ultimo = ultimo or _cargar(RUTA_ULTIMO, {})
    rs_de = {r["Ticker"]: r.get("RS_Score") for r in ultimo.get("ranking", [])}
    items_prev = {i["ticker"]: i for i in prev.get("items", []) if i.get("ticker")}
    spy_pos = {str(d)[:10]: k for k, d in enumerate(spy.index)}
    spy_vals = spy.values
    ts = ahora.isoformat()
    items, eventos = [], []

    for t in tickers:
        if t == benchmark:
            continue
        df = precios_ohlc.get(t)
        it = items_prev.get(t)
        if df is None or df.empty:
            if it:
                items.append(it)
            continue
        df = _ohlc_hasta(df, fecha_proc)
        if len(df) < MIN_RUEDAS or str(df.index[-1])[:10] != fecha_proc:
            if it:                                     # sin dato fresco: se conserva tal cual
                items.append(it)
            continue
        ev = _evaluar(df, rs_de.get(t))
        if ev is None:
            if it:
                items.append(it)
            continue
        c, base = ev["cierre"], ev["base"]
        hoy_pct = (c / ev["cierre_ant"] - 1) * 100
        comun = dict(ticker=t, cierre=round(c, 2), hoy_pct=round(hoy_pct, 2), rs=rs_de.get(t),
                     vol_rel=None if ev["vol_rel"] is None else round(ev["vol_rel"], 2),
                     dist_max52_pct=round(ev["dist_max52_pct"], 1), plantilla=ev["plantilla"], fecha_dato=fecha_proc)

        def _niveles(b):
            return dict(n_contr=b["n"], profundidades=b["prof"], minimos_suben=b["suben"],
                        pivote=round(b["pivote"], 2), stop=round(b["stop"], 2),
                        riesgo_pivote_pct=round((b["pivote"] - b["stop"]) / b["pivote"] * 100, 1))

        if it is None:
            if base and ev["tendencia"] and base["stop"] < c <= base["pivote"]:
                nuevo = dict(comun, **_niveles(base), estado="formacion", fecha_alta=fecha_proc,
                             dist_pivote_pct=round((base["pivote"] / c - 1) * 100, 1))
                items.append(nuevo)
                eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="alta", precio=nuevo["cierre"], pivote=nuevo["pivote"],
                                    stop=nuevo["stop"], n_contr=nuevo["n_contr"], profundidades=nuevo["profundidades"],
                                    minimos_suben=nuevo["minimos_suben"], plantilla=ev["plantilla"], rs=nuevo["rs"]))
            continue

        if it.get("estado") == "formacion":
            if c > it["pivote"]:                        # ruptura del pivote vigente el dia anterior
                k = spy_pos.get(fecha_proc)
                nuevo = dict(it, **comun, estado="ruptura", fecha_ruptura=fecha_proc, precio_ruptura=round(c, 2),
                             spy_ruptura=float(spy_vals[k]) if k is not None else None,
                             con_volumen=bool(ev["vol_rel"] is not None and ev["vol_rel"] >= VOL_RUPTURA),
                             ruedas=0, resultados={}, dist_pivote_pct=round((it["pivote"] / c - 1) * 100, 1),
                             dist_stop_pct=round((it["stop"] / c - 1) * 100, 1),
                             riesgo_ruptura_pct=round((c - it["stop"]) / c * 100, 1))
                items.append(nuevo)
                eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="ruptura", precio=nuevo["cierre"], pivote=it["pivote"],
                                    stop=it["stop"], riesgo_pct=nuevo["riesgo_ruptura_pct"], vol_rel=ev["vol_rel"],
                                    con_volumen=nuevo["con_volumen"], n_contr=it.get("n_contr"), minimos_suben=it.get("minimos_suben"),
                                    plantilla=ev["plantilla"], rs=nuevo["rs"]))
            elif base and ev["tendencia"] and base["stop"] < c <= base["pivote"]:
                items.append(dict(it, **comun, **_niveles(base), dist_pivote_pct=round((base["pivote"] / c - 1) * 100, 1)))
            else:
                if c <= it["stop"]:
                    motivo = "cerro bajo el stop de la base"
                elif not ev["tendencia"]:
                    motivo = "salio de la tendencia (maximo de 52s, media de 50 o FR)"
                else:
                    motivo = "la base dejo de ser valida"
                eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="salida_formacion", precio=round(c, 2), motivo=motivo))
            continue

        # estado ruptura: pivote y stop fijos
        k = spy_pos.get(fecha_proc)
        k0 = spy_pos.get(it["fecha_ruptura"])
        ruedas = (k - k0) if (k is not None and k0 is not None) else it.get("ruedas", 0) + 1
        res = dict(it.get("resultados") or {})
        entrada = it["precio_ruptura"]
        spy_r = it.get("spy_ruptura")
        if ev["minimo"] <= it["stop"]:                  # el minimo del dia toco el stop
            salida = min(it["stop"], ev["apertura"])
            ret = (salida / entrada - 1) * 100
            exc = ret - (float(spy_vals[k]) / spy_r - 1) * 100 if (spy_r and k is not None) else None
            eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="invalidada", stop=it["stop"], ruedas=ruedas,
                                salida_simulada=round(salida, 2), retorno_pct=round(ret, 2),
                                exceso_spy_pct=None if exc is None else round(exc, 2),
                                con_volumen=it.get("con_volumen"), n_contr=it.get("n_contr"), minimos_suben=it.get("minimos_suben"),
                                plantilla=it.get("plantilla")))
            continue
        for hz in HORIZONTES:
            if ruedas >= hz and str(hz) not in res:
                r = (c / entrada - 1) * 100
                x = r - (float(spy_vals[k]) / spy_r - 1) * 100 if (spy_r and k is not None) else None
                res[str(hz)] = dict(retorno_pct=round(r, 2), exceso_spy_pct=None if x is None else round(x, 2), fecha=fecha_proc)
                eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="resultado", horizonte=hz, retorno_pct=round(r, 2),
                                    exceso_spy_pct=None if x is None else round(x, 2), con_volumen=it.get("con_volumen"),
                                    n_contr=it.get("n_contr"), minimos_suben=it.get("minimos_suben"), plantilla=it.get("plantilla")))
        desde = (c / entrada - 1) * 100
        if ruedas >= SEGUIMIENTO_RUEDAS:
            eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="fin_seguimiento", precio=round(c, 2), ruedas=ruedas,
                                desde_ruptura_pct=round(desde, 2)))
            continue
        items.append(dict(it, **{k_: v for k_, v in comun.items()}, ruedas=ruedas, resultados=res,
                          desde_ruptura_pct=round(desde, 2), bajo_pivote=bool(c < it["pivote"]),
                          dist_pivote_pct=round((it["pivote"] / c - 1) * 100, 1),
                          dist_stop_pct=round((it["stop"] / c - 1) * 100, 1)))

    salida = dict(actualizado=ts, ultima_fecha=fecha_proc, items=items,
                  resumen=dict(formacion=sum(1 for i in items if i["estado"] == "formacion"),
                               ruptura=sum(1 for i in items if i["estado"] == "ruptura"),
                               altas_hoy=sum(1 for e in eventos if e["evento"] == "alta"),
                               rupturas_hoy=sum(1 for e in eventos if e["evento"] == "ruptura")))
    if modo == "produccion":
        if eventos:
            os.makedirs(os.path.dirname(RUTA_LOG), exist_ok=True)
            with open(RUTA_LOG, "a", encoding="utf-8") as f:       # solo agregar, nunca reescribir
                for e in eventos:
                    f.write(json.dumps(e, ensure_ascii=False, default=lambda o: bool(o) if isinstance(o, np.bool_) else float(o)) + "\n")
        os.makedirs(os.path.dirname(RUTA_ESTADO), exist_ok=True)
        with open(RUTA_ESTADO, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=1, default=lambda o: bool(o) if isinstance(o, np.bool_) else float(o))
        log.info(f"Bases VCP v4 {fecha_proc}: {len(items)} activo(s), {len(eventos)} evento(s)")
    else:
        log.info(f"MODO=test -- Bases VCP v4: {len(items)} activo(s), no se guarda")
    return dict(eventos=eventos, salida=salida)
