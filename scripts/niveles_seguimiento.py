"""
Avisos por Telegram cuando un activo en seguimiento toca un nivel marcado
(por ejemplo "31,84 en HIMS" o "tu stop en TSLA"), y aviso al cierre de la
rueda diciendo si el nivel se sostuvo o no.

Pedido de Victoria (5/10): durante la rueda puede pasar algo antes del cierre
y no quiere depender de mirar la pantalla. Esto es ADITIVO:
  * no toca ninguna señal existente ni la Auditoría;
  * tiene su propia configuración (data/niveles_seguimiento.json), su propio
    estado (data/niveles_estado.json) y su propia bitácora, que solo se
    agrega al final (data/log_niveles.jsonl -- append-only);
  * baja los precios por su cuenta (no depende de que el activo esté en el
    universo del radar: HIMX, por ejemplo, no está).

Cómo funciona, por cada nivel:
  1. En cada corrida (cada 30 min en rueda) se mira si el precio actual
     CRUZÓ el nivel respecto de la corrida anterior. Si sí -> aviso de "tocó".
     Máximo un aviso de toque mientras el cruce siga "abierto".
  2. La primera corrida después del cierre de la rueda mira dónde cerró:
     si cerró del lado del nivel -> "se sostuvo" (y cuenta cierres seguidos);
     si no -> "no se sostuvo" y el nivel vuelve a quedar armado.
  3. La primera vez que se ve un nivel solo se registra de qué lado está:
     no se manda aviso (evita un aviso falso al empezar).

Limitaciones honestas: se chequea cada 30 minutos (no al instante) y el dato
gratuito puede tener unos minutos de demora. No reemplaza una alerta de
precio de TradingView o del broker; las complementa con el contexto
(volumen del día, cierre).
"""
import json
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

log = logging.getLogger("radar.niveles")

RUTA_CONFIG = "data/niveles_seguimiento.json"
RUTA_ESTADO = "data/niveles_estado.json"
RUTA_LOG = "data/log_niveles.jsonl"
NY = ZoneInfo("America/New_York")
MINUTOS_POST_CIERRE = 5  # margen para que Yahoo ya tenga la vela final


def _clave(n: dict) -> str:
    return f"{n['ticker']}|{n['nivel']}|{n['direccion']}"


def _cargar_json(ruta, defecto):
    if not os.path.exists(ruta):
        return defecto
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"No se pudo leer {ruta} ({e}) -- se usa el valor por defecto")
        return defecto


def _guardar_estado(estado: dict):
    os.makedirs(os.path.dirname(RUTA_ESTADO), exist_ok=True)
    with open(RUTA_ESTADO, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def _agregar_log(eventos: list):
    if not eventos:
        return
    os.makedirs(os.path.dirname(RUTA_LOG), exist_ok=True)
    with open(RUTA_LOG, "a", encoding="utf-8") as f:  # solo agregar, nunca reescribir
        for e in eventos:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _traer_precio_yahoo(simbolo: str):
    """Devuelve dict {precio, fecha (de la última vela), vol_rel_parcial} o None."""
    import yfinance as yf
    hist = yf.Ticker(simbolo).history(period="2mo", auto_adjust=True)
    if hist is None or hist.empty:
        return None
    ultimo = hist.iloc[-1]
    previos = hist["Volume"].iloc[:-1].tail(20)
    prom = float(previos.mean()) if len(previos) else 0.0
    vol_rel = round(float(ultimo["Volume"]) / prom, 2) if prom > 0 else None
    return {"precio": float(ultimo["Close"]),
            "fecha": hist.index[-1].strftime("%Y-%m-%d"),
            "vol_rel_parcial": vol_rel}


def _num(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _msg_toque(n, precio, vol_rel):
    lado = "arriba" if n["direccion"] == "arriba" else "abajo"
    dist = (precio - n["nivel"]) / n["nivel"] * 100
    vol = f" · volumen del día hasta ahora: {vol_rel * 100:.0f}% del promedio diario" if vol_rel is not None else ""
    return (f"🔔 <b>{n['ticker']}</b> tocó el nivel de {lado}: <b>{_num(n['nivel'])}</b>\n"
            f"   Precio ahora: {_num(precio)} ({dist:+.2f}% vs. el nivel){vol}\n"
            f"   Nivel marcado: {n.get('etiqueta', '-')}\n"
            f"   La rueda todavía no cerró: un cruce durante el día puede revertirse. "
            f"Al cierre se avisa si se sostuvo. (Dato con unos minutos de demora; no es una recomendación.)")


def _msg_cierre(n, precio, ok, seguidos):
    lado = "por encima" if n["direccion"] == "arriba" else "por debajo"
    if ok:
        extra = f" · {seguidos}° cierre seguido del mismo lado" if seguidos > 1 else " · es el primer cierre de ese lado"
        return (f"📌 <b>{n['ticker']}</b> cerró {lado} de {_num(n['nivel'])} (cierre {_num(precio)}){extra}\n"
                f"   Nivel marcado: {n.get('etiqueta', '-')}")
    return (f"↩️ <b>{n['ticker']}</b> no se sostuvo: cerró en {_num(precio)}, del otro lado de {_num(n['nivel'])}\n"
            f"   Nivel marcado: {n.get('etiqueta', '-')} · el nivel vuelve a quedar armado")


def procesar_niveles(modo: str, token=None, chat_id=None, ahora=None, fetch=None):
    """
    Corre una pasada. Nunca lanza excepción hacia afuera (la llama main.py
    dentro de un try/except igual, doble seguro).
    modo: "produccion" manda Telegram y guarda estado/bitácora; cualquier
    otro valor solo calcula y loguea (no manda, no guarda).
    fetch(simbolo) -> dict|None, inyectable para pruebas.
    """
    from telegram_bot import enviar_mensaje
    ahora = ahora or datetime.now(timezone.utc)
    fetch = fetch or _traer_precio_yahoo
    cfg = _cargar_json(RUTA_CONFIG, {"niveles": []})
    niveles = [n for n in cfg.get("niveles", []) if n.get("ticker") and n.get("nivel") and n.get("direccion") in ("arriba", "abajo")]
    if not niveles:
        log.info("Niveles de seguimiento: no hay niveles configurados")
        return {"avisos": 0}

    ny = ahora.astimezone(NY)
    hoy_ny = ny.strftime("%Y-%m-%d")
    es_dia_habil = ny.weekday() < 5
    if not es_dia_habil:
        log.info("Niveles de seguimiento: fin de semana, no se evalúa nada")
        return {"avisos": 0}
    cierre = ny.replace(hour=16, minute=MINUTOS_POST_CIERRE, second=0, microsecond=0)
    post_cierre = es_dia_habil and ny >= cierre
    estado = _cargar_json(RUTA_ESTADO, {})
    if not isinstance(estado, dict):
        estado = {}
    niv_est = estado.setdefault("niveles", {})
    cierre_hecho = estado.get("cierre_procesado") == hoy_ny

    precios = {}
    for t in sorted({n["ticker"] for n in niveles}):
        try:
            precios[t] = fetch(t)
        except Exception as e:
            log.warning(f"Niveles: no se pudo traer {t} ({e})")
            precios[t] = None

    mensajes, eventos = [], []
    ts = ahora.isoformat()
    for n in niveles:
        d = precios.get(n["ticker"])
        # sin dato, o la última vela no es de hoy (feriado / aún sin abrir): no se evalúa
        if not d or d.get("fecha") != hoy_ny:
            continue
        precio = d["precio"]
        k = _clave(n)
        e = niv_est.setdefault(k, {"lado": None, "cruzado": False, "cierres_seguidos": 0})
        lado_gatillo = "arriba" if n["direccion"] == "arriba" else "abajo"
        lado_ahora = "arriba" if precio >= n["nivel"] else "abajo"

        if post_cierre:
            if not cierre_hecho and e["cruzado"]:
                if lado_ahora == lado_gatillo:
                    e["cierres_seguidos"] += 1
                    mensajes.append(_msg_cierre(n, precio, True, e["cierres_seguidos"]))
                    ev = "cierre_ok"
                else:
                    mensajes.append(_msg_cierre(n, precio, False, 0))
                    e["cruzado"], e["cierres_seguidos"] = False, 0
                    ev = "cierre_no_sostuvo"
                eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": n["ticker"], "nivel": n["nivel"],
                                "direccion": n["direccion"], "evento": ev, "precio": round(precio, 2),
                                "cierres_seguidos": e["cierres_seguidos"], "etiqueta": n.get("etiqueta")})
        else:
            if (not e["cruzado"]) and e["lado"] is not None and e["lado"] != lado_gatillo and lado_ahora == lado_gatillo:
                e["cruzado"], e["cierres_seguidos"] = True, 0
                mensajes.append(_msg_toque(n, precio, d.get("vol_rel_parcial")))
                eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": n["ticker"], "nivel": n["nivel"],
                                "direccion": n["direccion"], "evento": "toque", "precio": round(precio, 2),
                                "vol_rel_parcial": d.get("vol_rel_parcial"), "etiqueta": n.get("etiqueta")})
        e["lado"] = lado_ahora

    if post_cierre and not cierre_hecho and any(precios.get(n["ticker"]) and precios[n["ticker"]].get("fecha") == hoy_ny for n in niveles):
        estado["cierre_procesado"] = hoy_ny

    enviados = 0
    if modo == "produccion":
        for m in mensajes:
            if enviar_mensaje(token, chat_id, m):
                enviados += 1
        _agregar_log(eventos)
        _guardar_estado(estado)
        log.info(f"Niveles de seguimiento: {len(mensajes)} aviso(s), {enviados} enviado(s) a Telegram")
    else:
        log.info(f"MODO=test -- niveles de seguimiento: {len(mensajes)} aviso(s) NO enviados, no se guarda estado")
    return {"avisos": len(mensajes), "mensajes": mensajes, "eventos": eventos}
