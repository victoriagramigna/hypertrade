"""
Watchlist VCP -- seguimiento de la "forma VCP" del hilo de Market Strength / Kasliwal.

ADITIVO: no usa ni modifica ninguna senal del radar ni la Auditoria. Tiene su propio
estado (data/vcp_watchlist.json) y su propia bitacora que solo se agrega al final
(data/log_vcp.jsonl). Se evalua UNA vez por rueda, con el cierre ya terminado.

Condiciones de entrada a la lista (aproximadas con cierres; tramos de 20 ruedas ~ 4 semanas):
  1. Tres retrocesos (caida maxima de cierre en cada tramo de 20 ruedas) cada uno MENOR
     que el anterior, y el ultimo de 8% o menos.
  2. Cierre a menos de 15% del maximo de 52 semanas.
  3. Cierre sobre la media de 50 ruedas.
  4. Fuerza relativa del radar (RS_Score) de 50 o mas.
El volumen (promedio de 10 ruedas / promedio de 50 ruedas, menor a 100% = "se seca") NO
saca a nadie de la lista: se muestra como dato y ordena.
Niveles: pivote = maximo cierre del ultimo tramo; stop = minimo cierre del ultimo tramo.

Estados:
  formacion : cumple la forma, todavia no cerro sobre el pivote.
  ruptura   : un cierre por encima del pivote del dia anterior. El pivote y el stop quedan
              FIJOS desde ese dia. "Con volumen" = volumen del dia >= 1,5x el promedio de las
              50 ruedas previas (umbral mio, NO validado).
Salidas de la lista:
  * en formacion: la forma deja de cumplirse al cierre (se anota cual condicion fallo).
  * en ruptura: cierre bajo el stop (invalidada) o 20 ruedas de seguimiento cumplidas.
En la bitacora se anota cada alta, ruptura, salida y, a las 5/10/20 ruedas de cada ruptura,
el resultado (retorno y exceso contra SPY), para medir hacia adelante con datos reales.

Origen y limites (decirlo siempre): las condiciones salen de capturas del hilo (el video no
se pudo leer); la deteccion con tramos fijos de 20 ruedas es una aproximacion; el estudio
historico propio (1 anio, un solo regimen) NO valida que la forma funcione.
"""
import json
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np

log = logging.getLogger("radar.vcp_watchlist")

RUTA_ESTADO = "data/vcp_watchlist.json"
RUTA_LOG = "data/log_vcp.jsonl"
RUTA_ULTIMO = "data/ultimo.json"

TRAMO = 20
MAX_ULT_RETROCESO = 8.0
CERCA_MAX52 = 0.85
RS_MIN = 50.0
VENTANA_VOL = (10, 50)
VOL_RUPTURA = 1.5
SEGUIMIENTO_RUEDAS = 20
HORIZONTES = (5, 10, 20)
MIN_RUEDAS = 200
# Telegram apagado hasta tener datos reales de la bitacora (el estudio v4 no valido ventaja). La watchlist y la bitacora siguen igual.
TELEGRAM_ACTIVO = False
NY = ZoneInfo("America/New_York")
MINUTOS_POST_CIERRE = 5


# ------------------------------------------------------------------ calculo
def _mdd(w):
    pico = np.maximum.accumulate(w)
    return float(((pico - w) / pico).max() * 100)


def evaluar(close, vol, rs):
    """close/vol: arrays hasta el ultimo cierre. Devuelve dict con todo lo medido, o None."""
    close = np.asarray(close, float)
    if len(close) < MIN_RUEDAS or np.isnan(close[-60:]).any():
        return None
    c = close[-1]
    t3, t2, t1 = close[-TRAMO:], close[-2 * TRAMO:-TRAMO], close[-3 * TRAMO:-2 * TRAMO]
    d1, d2, d3 = _mdd(t1), _mdd(t2), _mdd(t3)
    max52 = float(np.nanmax(close[-252:]))
    sma50 = float(np.mean(close[-50:]))
    out = dict(cierre=c, retrocesos=[round(d1, 1), round(d2, 1), round(d3, 1)],
               max52=max52, dist_max52_pct=(c / max52 - 1) * 100, sma50=sma50,
               pivote=float(np.max(t3)), stop=float(np.min(t3)), rs=rs,
               vol10_50_pct=None, vol_seca=None, vol_rel=None)
    v = None if vol is None else np.asarray(vol, float)
    if v is not None and len(v) == len(close):
        a, b = VENTANA_VOL
        v10, v50 = np.nanmean(v[-a:]), np.nanmean(v[-b:])
        if v50 and v50 > 0 and not np.isnan(v10):
            out["vol10_50_pct"] = float(v10 / v50 * 100)
            out["vol_seca"] = bool(v10 / v50 < 1.0)
        prev50 = np.nanmean(v[-b - 1:-1])
        if prev50 and prev50 > 0 and not np.isnan(v[-1]):
            out["vol_rel"] = float(v[-1] / prev50)
    fallas = []
    if not (d1 > d2 > d3):
        fallas.append("los retrocesos no son decrecientes")
    if d3 > MAX_ULT_RETROCESO:
        fallas.append(f"el ultimo retroceso supera {MAX_ULT_RETROCESO:.0f}%")
    if c < CERCA_MAX52 * max52:
        fallas.append("esta a mas de 15% del maximo de 52 semanas")
    if c <= sma50:
        fallas.append("cerro bajo la media de 50 ruedas")
    if rs is None or rs < RS_MIN:
        fallas.append("fuerza relativa menor a 50")
    out["fallas"] = fallas
    out["cumple"] = not fallas
    return out


# ------------------------------------------------------------------ utilidades
def _cargar(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


def _num(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _hasta(s, fecha):
    if s is None:
        return None
    s = s.dropna() if hasattr(s, "dropna") else s
    idx = [str(d)[:10] for d in s.index]
    n = sum(1 for d in idx if d <= fecha)
    return s.iloc[:n]


def _msg_altas(altas):
    ls = []
    for a in sorted(altas, key=lambda x: (not x["vol_seca"], x["ticker"])):
        seco = "volumen seco" if a["vol_seca"] else "volumen sin secarse"
        ls.append(f"   • {a['ticker']}: cierre {_num(a['cierre'])}, pivote {_num(a['pivote'])} ({a['dist_pivote_pct']:+.1f}%), stop {_num(a['stop'])} · {seco}")
    return ("🌀 <b>Watchlist VCP — suman hoy</b>\n" + "\n".join(ls) +
            "\n   Cumplen la forma del hilo (3 retrocesos cada vez menores, cerca del máximo anual, sobre la media de 50, FR de 50 o más). Todavía no rompieron el pivote.")


def _msg_ruptura(it):
    vol = it.get("vol_rel")
    vtxt = "sin dato de volumen" if vol is None else (f"volumen {vol:.1f}x el promedio" + (" (con volumen)" if it["con_volumen"] else " (sin volumen fuerte)"))
    seco = {True: "venía con volumen seco", False: "venía sin volumen seco", None: ""}[it.get("vol_seca_previa")]
    return (f"🌀 <b>VCP — RUPTURA del pivote: {it['ticker']}</b>\n"
            f"   Cerró en {_num(it['cierre'])}, por encima del pivote {_num(it['pivote'])}. {vtxt}; {seco}.\n"
            f"   Se invalida con un cierre bajo {_num(it['stop'])} ({(it['stop'] / it['cierre'] - 1) * 100:+.1f}% desde el cierre).\n"
            f"   Es un escenario según la forma del hilo, no una recomendación: el estudio propio no valida que funcione; verificá las noticias.")


def _msg_rupturas_sin_volumen(lista):
    ls = []
    for r in sorted(lista, key=lambda x: x["ticker"]):
        v = "sin dato de volumen" if r.get("vol_rel") is None else f"volumen {r['vol_rel']:.1f}x"
        ls.append(f"   • {r['ticker']}: cerró en {_num(r['cierre'])} sobre el pivote {_num(r['pivote'])} · {v} · stop {_num(r['stop'])}")
    return ("🌀 <b>VCP — rupturas del pivote SIN volumen fuerte</b> (menos de 1,5x el promedio)\n" + "\n".join(ls) +
            "\n   Rompieron el pivote pero sin el respaldo de volumen que pide el hilo.")


def _msg_salidas(lista):
    ls = [f"   • {t}: {m}" for t, m in lista]
    return "🌀 <b>Watchlist VCP — salen</b>\n" + "\n".join(ls)


# ------------------------------------------------------------------ pasada
def procesar_vcp(precios, volumenes, benchmark, tickers, modo, token=None, chat_id=None,
                 ahora=None, ultimo=None, enviar=True):
    """Una pasada por rueda cerrada. Nunca lanza excepcion hacia afuera."""
    try:
        return _procesar(precios, volumenes, benchmark, tickers, modo, token, chat_id, ahora, ultimo, enviar)
    except Exception as e:
        log.warning(f"Watchlist VCP: fallo esta pasada ({e})")
        return {"avisos": 0, "error": str(e)}


def _procesar(precios, volumenes, benchmark, tickers, modo, token, chat_id, ahora, ultimo, enviar):
    ahora = ahora or datetime.now(timezone.utc)
    ny = ahora.astimezone(NY)
    hoy_ny = ny.strftime("%Y-%m-%d")
    post_cierre = ny.weekday() < 5 and ny >= ny.replace(hour=16, minute=MINUTOS_POST_CIERRE, second=0, microsecond=0)
    spy_full = precios.get(benchmark)
    if spy_full is None or spy_full.dropna().empty:
        return {"avisos": 0}
    spy = spy_full.dropna()
    fecha_proc = str(spy.index[-1])[:10]
    if fecha_proc == hoy_ny and not post_cierre:       # barra del dia todavia abierta: se usa la anterior
        spy = _hasta(spy, str(spy.index[-2])[:10])
        fecha_proc = str(spy.index[-1])[:10]
    prev = _cargar(RUTA_ESTADO, {})
    if prev.get("ultima_fecha") == fecha_proc:
        return {"avisos": 0, "ya_procesado": fecha_proc}
    ultimo = ultimo or _cargar(RUTA_ULTIMO, {})
    rs_de = {r["Ticker"]: r.get("RS_Score") for r in ultimo.get("ranking", [])}
    items_prev = {i["ticker"]: i for i in prev.get("items", []) if i.get("ticker")}
    spy_pos = {str(d)[:10]: k for k, d in enumerate(spy.index)}
    spy_vals = spy.values
    ts = ahora.isoformat()
    items, eventos, altas, rupturas, salidas = [], [], [], [], []

    for t in tickers:
        if t == benchmark:
            continue
        s = _hasta(precios.get(t), fecha_proc)
        if s is None or len(s) < MIN_RUEDAS or str(s.index[-1])[:10] != fecha_proc:
            if t in items_prev:                         # sin dato fresco: se conserva tal cual
                items.append(items_prev[t])
            continue
        v = _hasta(volumenes.get(t), fecha_proc) if volumenes.get(t) is not None else None
        varr = None
        if v is not None:
            v = v.reindex(s.index)
            varr = v.values
        ev = evaluar(s.values, varr, rs_de.get(t))
        if ev is None:
            if t in items_prev:
                items.append(items_prev[t])
            continue
        cierre_ant = float(s.values[-2])
        hoy_pct = (ev["cierre"] / cierre_ant - 1) * 100
        it = items_prev.get(t)
        base = dict(ticker=t, cierre=round(ev["cierre"], 2), hoy_pct=round(hoy_pct, 2), rs=ev["rs"],
                    retrocesos=ev["retrocesos"], dist_max52_pct=round(ev["dist_max52_pct"], 1),
                    vol10_50_pct=None if ev["vol10_50_pct"] is None else round(ev["vol10_50_pct"], 1),
                    vol_seca=ev["vol_seca"], vol_rel=None if ev["vol_rel"] is None else round(ev["vol_rel"], 2),
                    fecha_dato=fecha_proc)
        if it is None:
            if ev["cumple"]:
                nuevo = dict(base, estado="formacion", fecha_alta=fecha_proc,
                             pivote=round(ev["pivote"], 2), stop=round(ev["stop"], 2),
                             dist_pivote_pct=round((ev["pivote"] / ev["cierre"] - 1) * 100, 1),
                             dist_stop_pct=round((ev["stop"] / ev["cierre"] - 1) * 100, 1))
                items.append(nuevo)
                altas.append(nuevo)
                eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="alta", precio=nuevo["cierre"],
                                    pivote=nuevo["pivote"], stop=nuevo["stop"], retrocesos=ev["retrocesos"],
                                    vol_seca=ev["vol_seca"], vol10_50_pct=base["vol10_50_pct"], rs=ev["rs"]))
            continue
        if it.get("estado") == "formacion":
            if ev["cierre"] > it["pivote"]:             # ruptura del pivote del dia anterior
                k = spy_pos.get(fecha_proc)
                nuevo = dict(base, retrocesos=it.get("retrocesos"), estado="ruptura", fecha_alta=it["fecha_alta"], fecha_ruptura=fecha_proc,
                             pivote=it["pivote"], stop=it["stop"], precio_ruptura=round(ev["cierre"], 2),
                             spy_ruptura=float(spy_vals[k]) if k is not None else None,
                             con_volumen=bool(ev["vol_rel"] is not None and ev["vol_rel"] >= VOL_RUPTURA),
                             vol_seca_previa=it.get("vol_seca"), ruedas=0, resultados={},
                             dist_pivote_pct=round((it["pivote"] / ev["cierre"] - 1) * 100, 1),
                             dist_stop_pct=round((it["stop"] / ev["cierre"] - 1) * 100, 1))
                items.append(nuevo)
                rupturas.append(nuevo)
                eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="ruptura", precio=nuevo["cierre"],
                                    pivote=nuevo["pivote"], stop=nuevo["stop"], vol_rel=ev["vol_rel"],
                                    con_volumen=nuevo["con_volumen"], vol_seca_previa=it.get("vol_seca"),
                                    vol10_50_pct_previo=it.get("vol10_50_pct"), rs=ev["rs"]))
            elif ev["cumple"]:
                items.append(dict(it, **base, pivote=round(ev["pivote"], 2), stop=round(ev["stop"], 2),
                                  dist_pivote_pct=round((ev["pivote"] / ev["cierre"] - 1) * 100, 1),
                                  dist_stop_pct=round((ev["stop"] / ev["cierre"] - 1) * 100, 1)))
            else:
                motivo = "; ".join(ev["fallas"])
                salidas.append((t, motivo))
                eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="salida_formacion", precio=base["cierre"], motivo=motivo))
            continue
        # estado ruptura: pivote y stop fijos
        k = spy_pos.get(fecha_proc)
        k0 = spy_pos.get(it["fecha_ruptura"])
        ruedas = (k - k0) if (k is not None and k0 is not None) else it.get("ruedas", 0) + 1
        res = dict(it.get("resultados") or {})
        for h in HORIZONTES:
            if ruedas >= h and str(h) not in res:
                r = (ev["cierre"] / it["precio_ruptura"] - 1) * 100
                x = r - (float(spy_vals[k]) / it["spy_ruptura"] - 1) * 100 if it.get("spy_ruptura") else None
                res[str(h)] = dict(retorno_pct=round(r, 2), exceso_spy_pct=None if x is None else round(x, 2), fecha=fecha_proc)
                eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="resultado", horizonte=h,
                                    retorno_pct=round(r, 2), exceso_spy_pct=None if x is None else round(x, 2),
                                    con_volumen=it.get("con_volumen"), vol_seca_previa=it.get("vol_seca_previa")))
        desde = (ev["cierre"] / it["precio_ruptura"] - 1) * 100
        if ev["cierre"] < it["stop"]:
            salidas.append((t, f"cerró bajo el stop {_num(it['stop'])}: ruptura invalidada"))
            eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="invalidada", precio=base["cierre"],
                                stop=it["stop"], ruedas=ruedas, desde_ruptura_pct=round(desde, 2)))
            continue
        if ruedas >= SEGUIMIENTO_RUEDAS:
            eventos.append(dict(ts=ts, fecha=fecha_proc, ticker=t, evento="fin_seguimiento", precio=base["cierre"],
                                ruedas=ruedas, desde_ruptura_pct=round(desde, 2)))
            salidas.append((t, f"cumplió {SEGUIMIENTO_RUEDAS} ruedas de seguimiento ({desde:+.1f}% desde la ruptura)"))
            continue
        _b = {k: v for k, v in base.items() if k != "retrocesos"}     # los retrocesos quedan fijos desde la ruptura
        items.append(dict(it, **_b, ruedas=ruedas, resultados=res, desde_ruptura_pct=round(desde, 2),
                          bajo_pivote=bool(ev["cierre"] < it["pivote"]),
                          dist_pivote_pct=round((it["pivote"] / ev["cierre"] - 1) * 100, 1),
                          dist_stop_pct=round((it["stop"] / ev["cierre"] - 1) * 100, 1)))

    mensajes = []
    if altas:
        mensajes.append(_msg_altas(altas))
    mensajes += [_msg_ruptura(r) for r in rupturas if r["con_volumen"]]
    _sin = [r for r in rupturas if not r["con_volumen"]]
    if _sin:
        mensajes.append(_msg_rupturas_sin_volumen(_sin))
    if salidas:
        mensajes.append(_msg_salidas(salidas))
    salida = dict(actualizado=ts, ultima_fecha=fecha_proc, items=items,
                  resumen=dict(formacion=sum(1 for i in items if i["estado"] == "formacion"),
                               ruptura=sum(1 for i in items if i["estado"] == "ruptura"),
                               altas_hoy=len(altas), rupturas_hoy=len(rupturas), salidas_hoy=len(salidas)))
    enviados = 0
    if modo == "produccion":
        if enviar and TELEGRAM_ACTIVO:
            from telegram_bot import enviar_mensaje
            for m in mensajes:
                if enviar_mensaje(token, chat_id, m + "\n   (Información y escenarios, no una recomendación.)"):
                    enviados += 1
        if eventos:
            os.makedirs(os.path.dirname(RUTA_LOG), exist_ok=True)
            with open(RUTA_LOG, "a", encoding="utf-8") as f:       # solo agregar, nunca reescribir
                for e in eventos:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
        os.makedirs(os.path.dirname(RUTA_ESTADO), exist_ok=True)
        with open(RUTA_ESTADO, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=1, default=lambda o: bool(o) if isinstance(o, np.bool_) else float(o))
        log.info(f"Watchlist VCP {fecha_proc}: {len(items)} activo(s), {len(altas)} alta(s), {len(rupturas)} ruptura(s), "
                 f"{len(salidas)} salida(s), {enviados} aviso(s)")
    else:
        log.info(f"MODO=test -- Watchlist VCP: {len(items)} activo(s), {len(mensajes)} aviso(s) NO enviados, no se guarda")
    return dict(avisos=len(mensajes), mensajes=mensajes, eventos=eventos, salida=salida)
