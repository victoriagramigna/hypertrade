"""
Seguimiento de activos en lista de "posible entrada" (pedido de Victoria, 27/10).

Es ADITIVO, igual que niveles_seguimiento.py:
  * no toca ninguna señal existente ni la Auditoría;
  * configuración propia  : data/entradas_seguimiento.json (la lista y sus niveles);
  * estado propio         : data/entradas_estado.json (lo que lee la app);
  * bitácora propia       : data/log_entradas.jsonl -- SOLO se agrega al final.

Para cada activo de la lista se define de antemano, con datos del radar:
  * una zona de demanda (piso y techo) y un nivel de CONFIRMACIÓN (cierre diario
    por encima) y uno de INVALIDACIÓN (cierre diario por debajo);
  * un motivo y qué vigilar.
Cada corrida se calcula el estado con el precio de ultimo.json:
  esperando  : entre invalidación y confirmación, fuera de la zona de demanda
  en_zona    : el precio está dentro de la zona de demanda
  sobre_confirmacion / bajo_invalidacion (intradía, puede revertirse)
  confirmada / invalidada : SOLO se fijan con el cierre de la rueda
La primera corrida posterior al cierre cuenta los cierres seguidos de cada lado
y deja una foto diaria en la bitácora (precio, hoy, RSI, fuerza relativa, volumen).
ESCENARIO DE ENTRADA (lo que Victoria pidió que se avise con claridad), por activo:
  A) REBOTE: el precio llegó a su piso (zona de demanda, y la media de 50 ruedas si el activo la
     tiene activada con "usar_sma50") y la rueda CIERRA por encima del techo de ese piso, sin
     haber cerrado bajo el nivel de invalidación. El toque vale 14 días corridos.
  B) RUPTURA: la rueda cierra por encima del nivel de confirmación.
Avisos por Telegram: (1) "llegó al piso" durante la rueda, una sola vez por toque; (2) al cierre,
"ESCENARIO DE ENTRADA" cuando se cumple A o B; (3) al cierre, invalidada / entró en zona.
Es información y escenarios, no una recomendación.
"""
import json
import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

log = logging.getLogger("radar.entradas")

RUTA_CONFIG = "data/entradas_seguimiento.json"
RUTA_ESTADO = "data/entradas_estado.json"
RUTA_LOG = "data/log_entradas.jsonl"
RUTA_ULTIMO = "data/ultimo.json"
NY = ZoneInfo("America/New_York")
MINUTOS_POST_CIERRE = 5
DIAS_VALIDEZ_TOQUE = 14   # días corridos que vale un toque de piso para el escenario de rebote
BANDA_SMA50 = 0.01        # la media de 50 ruedas se trata como un piso de +/-1%
ETIQUETA_ESTADO = {
    "esperando": "Esperando", "en_zona": "En zona de demanda",
    "sobre_confirmacion": "Sobre la confirmación (intradía)", "bajo_invalidacion": "Bajo la invalidación (intradía)",
    "confirmada": "Confirmada al cierre", "invalidada": "Invalidada al cierre",
}


def _cargar(ruta, defecto):
    if not os.path.exists(ruta):
        return defecto
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"No se pudo leer {ruta} ({e})")
        return defecto


def _num(x, d=2):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _nivel(item, clave, fila):
    """Nivel fijo, o tomado de un campo del radar (p. ej. Max_52w, SMA50) si trae 'campo'."""
    n = item.get(clave) or {}
    if n.get("campo") and fila and fila.get(n["campo"]) is not None:
        return float(fila[n["campo"]])
    return float(n["nivel"]) if n.get("nivel") is not None else None


def calcular_estado_actual(precio, conf, inv, zona_techo):
    if inv is not None and precio < inv:
        return "bajo_invalidacion"
    if conf is not None and precio >= conf:
        return "sobre_confirmacion"
    if zona_techo is not None and inv is not None and inv <= precio <= zona_techo:
        return "en_zona"
    return "esperando"


def _msg_cierre(it, cambio, precio, extra):
    t = it["ticker"]
    if cambio == "confirmada":
        return (f"✅ <b>{t}</b> cerró en {_num(precio)}, por encima de su nivel de confirmación ({_num(extra['conf'])}).\n"
                f"   Volumen del día: {extra['vol']}{'' if extra['vol_ok'] else ' (por debajo del promedio: cierre sin respaldo de volumen)'}. Es el cierre n° {extra['cierres']} de ese lado.\n"
                f"   Lo que se esperaba: {it.get('confirmacion', {}).get('texto', '-')}")
    if cambio == "invalidada":
        return (f"⛔ <b>{t}</b> cerró en {_num(precio)}, por debajo de su nivel de invalidación ({_num(extra['inv'])}).\n"
                f"   La idea de apoyo ya no vale con este cierre. {it.get('invalidacion', {}).get('texto', '')}")
    if cambio == "en_zona":
        return (f"📍 <b>{t}</b> cerró dentro de su zona de demanda ({_num(extra['inv'])} a {_num(extra['zona_techo'])}): {_num(precio)}.\n"
                f"   Confirmación pendiente: cierre sobre {_num(extra['conf'])}.")
    return (f"↩️ <b>{t}</b> cerró en {_num(precio)}, fuera del estado anterior ({ETIQUETA_ESTADO.get(extra['antes'], extra['antes'])}) "
            f"→ ahora: {ETIQUETA_ESTADO.get(cambio, cambio)}.")


# Criterios del filtro de candidatos y de salida. OJO: son los que se usaron al armar la lista el 27/10 y NO están
# validados con un backtest; por eso cada candidato y cada salida sugerida queda anotado en la bitácora propia
# (append-only) para poder medir más adelante qué pasó con ellos y ajustar estos números con datos.
CAND_FR_MIN = 70            # fuerza relativa mínima
CAND_RSI = (40, 68)         # ni sobrevendido extremo ni sobrecomprado
CAND_HOY_MIN = -3.0         # sin caída fuerte hoy
CAND_MAX = 10               # cuántos candidatos se muestran (la lista en sí tiene tope de 30 activos)
SAL_CIERRES_BAJO_SMA50 = 2  # cierres seguidos bajo la media de 50 ruedas
SAL_FR_MIN = 50             # fuerza relativa por debajo de este valor
SAL_DIAS_VENCIDA = 30       # días corridos sin confirmar desde el alta
SAL_CIERRES_CONFIRMADA = 3  # cierres seguidos sobre la confirmación: el escenario se cumplió


def buscar_candidatos(filas, zonas, excluidos):
    """Activos del universo que cumplen la base (tendencia + fuerza + no sobrecomprado) y además tienen
    VCP, squeeze o tocan una zona de demanda. Ordenados por Radar Score. No son una recomendación."""
    out = []
    for t, r in filas.items():
        if t in excluidos:
            continue
        try:
            if not (r.get("Sobre_SMA50") and (r.get("Dist_SMA200_%") or -1) > 0 and (r.get("RS_Score") or 0) >= CAND_FR_MIN
                    and CAND_RSI[0] <= (r.get("RSI") or 0) <= CAND_RSI[1] and (r.get("Var_dia_%") or 0) > CAND_HOY_MIN):
                continue
        except Exception:
            continue
        toca = bool((zonas.get(t) or {}).get("Toca_Demanda"))
        marcas = [m for m, ok in (("VCP", r.get("VCP_valido")), ("Squeeze", r.get("Squeeze_Comprimido")), ("Toca zona de demanda", toca)) if ok]
        if not marcas:
            continue
        out.append({"ticker": t, "subcategoria": r.get("Subcategoria"), "precio": r.get("Precio"), "hoy_pct": r.get("Var_dia_%"),
                    "ret_5d": r.get("Ret_5d_%"), "fr": r.get("RS_Score"), "rsi": r.get("RSI"), "radar_score": r.get("Radar_Score"),
                    "dist_max52w": r.get("Dist_Max52w_%"), "vol_rel": r.get("Vol_rel"), "marcas": marcas})
    out.sort(key=lambda c: (c["radar_score"] or 0, len(c["marcas"])), reverse=True)
    return out[:CAND_MAX]


def motivos_salida(item, fila, hoy_ny):
    """Razones objetivas por las que conviene revisar sacar un activo de la lista (lista vacía = sigue)."""
    m = []
    if item.get("cierres_bajo_invalidacion", 0) >= 1:
        m.append("Cerró bajo el nivel de invalidación: la idea de apoyo ya no vale.")
    if item.get("cierres_bajo_sma50", 0) >= SAL_CIERRES_BAJO_SMA50:
        m.append(f"{item['cierres_bajo_sma50']} cierres seguidos bajo la media de 50 ruedas.")
    if fila and fila.get("RS_Score") is not None and fila["RS_Score"] < SAL_FR_MIN:
        m.append(f"La fuerza relativa cayó a {fila['RS_Score']:.0f} (menos de {SAL_FR_MIN}).")
    try:
        dias = (datetime.strptime(hoy_ny, "%Y-%m-%d") - datetime.strptime(item.get("fecha_alta") or hoy_ny, "%Y-%m-%d")).days
        if dias >= SAL_DIAS_VENCIDA and item.get("cierres_sobre_confirmacion", 0) == 0:
            m.append(f"Lleva {dias} días en la lista sin confirmar.")
    except Exception:
        pass
    if item.get("cierres_sobre_confirmacion", 0) >= SAL_CIERRES_CONFIRMADA:
        m.append(f"Confirmó con {item['cierres_sobre_confirmacion']} cierres seguidos: el escenario se cumplió (pasarlo a Cartera o sacarlo de la lista).")
    return m


# Categoría de riesgo de la operación (por activo de la lista). Es una guía ordenada con datos del radar, NO un dato validado
# con backtest: los cortes de distancia a la invalidación y de relación recompensa/riesgo son criterio mío; los de volatilidad
# salen de los terciles del universo (BB_Bandwidth_%) para que se ajusten solos al mercado.
RIESGO_DIST = (3.0, 6.0, 10.0)   # % hasta la invalidación: <=3 -> 0 pts, <=6 -> 1, <=10 -> 2, >10 -> 3
RIESGO_BETA_ALTO = 2.0
CATEGORIAS_RIESGO = [(2, "Bajo"), (4, "Medio"), (6, "Alto"), (99, "Muy alto")]


def _percentil(vals, q):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    return v[min(len(v) - 1, int(q * (len(v) - 1) + 0.5))]


def calcular_riesgo(precio, inv, conf, fila, bw_p33, bw_p67):
    """Devuelve {categoria, puntos, detalle[...]}: suma de 4 factores, cada uno explicado."""
    pts, det = 0, []
    if inv is not None and precio:
        d = (precio - inv) / precio * 100
        p_d = 0 if d <= RIESGO_DIST[0] else 1 if d <= RIESGO_DIST[1] else 2 if d <= RIESGO_DIST[2] else 3
        pts += p_d
        det.append({"factor": "Distancia a la invalidación", "valor": f"{d:.1f}%", "puntos": p_d,
                    "lectura": "pérdida chica si falla" if p_d == 0 else "pérdida moderada" if p_d == 1 else "pérdida grande" if p_d == 2 else "pérdida muy grande"})
    bw = fila.get("BB_Bandwidth_%") if fila else None
    if bw is not None and bw_p33 is not None:
        p_v = 0 if bw <= bw_p33 else 1 if bw <= bw_p67 else 2
        pts += p_v
        det.append({"factor": "Volatilidad reciente (ancho de Bollinger)", "valor": f"{bw:.1f}%", "puntos": p_v,
                    "lectura": "baja frente al resto del universo" if p_v == 0 else "media" if p_v == 1 else "alta frente al resto del universo"})
    rr = None
    if conf is not None and inv is not None and precio and precio < conf and inv < precio:
        rr = (conf / precio - 1) / ((precio - inv) / precio)
        p_r = 0 if rr >= 2 else 1 if rr >= 1 else 2
        pts += p_r
        det.append({"factor": "Recompensa/riesgo hasta la confirmación", "valor": f"{rr:.1f} a 1", "puntos": p_r,
                    "lectura": "favorable" if p_r == 0 else "justa" if p_r == 1 else "desfavorable (se arriesga más de lo que falta para confirmar)"})
    beta = fila.get("Beta") if fila else None
    if beta is not None and abs(beta) >= RIESGO_BETA_ALTO:
        pts += 1
        det.append({"factor": "Sensibilidad al mercado (beta)", "valor": f"{beta:.1f}", "puntos": 1, "lectura": "se mueve más del doble que el mercado"})
    cat = next(n for tope, n in CATEGORIAS_RIESGO if pts <= tope)
    return {"categoria": cat, "puntos": pts, "detalle": det, "rr": round(rr, 2) if rr is not None else None}


def _dias(desde, hasta):
    try:
        return (datetime.strptime(hasta, "%Y-%m-%d") - datetime.strptime(desde, "%Y-%m-%d")).days
    except Exception:
        return 9999


def _msg_toque(t, nombre, piso, techo, inv, precio):
    return (f"👀 <b>{t}</b> llegó a su piso ({nombre}: {_num(piso)} a {_num(techo)}). Precio ahora: {_num(precio)}.\n"
            f"   Todavía NO es el escenario de entrada: se da si la rueda CIERRA por encima de {_num(techo)}.\n"
            f"   Si cierra por debajo de {_num(inv)}, la idea se invalida. (La rueda sigue abierta: puede revertirse.)")


def _msg_escenario(t, tipo, precio, nivel, inv, vol, detalle, riesgo=None):
    vol_txt = "" if vol is None else (f"Volumen del día: {vol * 100:.0f}% del promedio" + ("." if vol >= 1.0 else " (por debajo del promedio: sin respaldo de volumen)."))
    cab = "REBOTE en el piso" if tipo == "rebote" else "RUPTURA confirmada"
    riesgo_txt = (f"Riesgo de la operación: {riesgo['categoria']} (" + "; ".join(f"{d['factor'].lower()} {d['valor']}" for d in riesgo['detalle']) + ").\n   ") if riesgo else ""
    return (f"🟢 <b>ESCENARIO DE ENTRADA — {t}</b> ({cab})\n"
            f"   {detalle}\n"
            f"   Cerró en {_num(precio)}, por encima de {_num(nivel)}. {vol_txt}\n"
            f"   Se invalida con un cierre diario por debajo de {_num(inv)} ({(inv / precio - 1) * 100:+.1f}% desde el cierre).\n"
            f"   {riesgo_txt}"
            f"Es un escenario según los datos del radar, no una recomendación: verificá noticias y fecha de resultados antes de decidir.")


def procesar_entradas(modo, token=None, chat_id=None, ahora=None, ultimo=None, enviar=True):
    """Una pasada. Nunca lanza excepción hacia afuera. modo != 'produccion' => solo calcula."""
    ahora = ahora or datetime.now(timezone.utc)
    cfg = _cargar(RUTA_CONFIG, {"lista": []})
    lista = [i for i in cfg.get("lista", []) if i.get("ticker")]
    if not lista:
        return {"avisos": 0}
    ultimo = ultimo or _cargar(RUTA_ULTIMO, {})
    filas = {r["Ticker"]: r for r in ultimo.get("ranking", [])}
    zonas = {z["Ticker"]: z for z in ultimo.get("zonas", [])}
    ny = ahora.astimezone(NY)
    hoy_ny = ny.strftime("%Y-%m-%d")
    post_cierre = ny.weekday() < 5 and ny >= ny.replace(hour=16, minute=MINUTOS_POST_CIERRE, second=0, microsecond=0)
    prev = _cargar(RUTA_ESTADO, {})
    prev_items = {i["ticker"]: i for i in prev.get("items", [])} if isinstance(prev, dict) else {}
    ts = ahora.isoformat()
    items, eventos, mensajes = [], [], []
    _bws = [f_.get("BB_Bandwidth_%") for f_ in filas.values()]
    bw_p33, bw_p67 = _percentil(_bws, 0.33), _percentil(_bws, 0.67)

    for it in lista:
        t = it["ticker"]
        r = filas.get(t)
        antes = prev_items.get(t, {})
        if not r or r.get("Precio") is None:
            if antes:
                items.append({**antes, "sin_dato": True})
            continue
        precio = float(r["Precio"])
        fecha_dato = r.get("Fecha_dato")
        conf, inv = _nivel(it, "confirmacion", r), _nivel(it, "invalidacion", r)
        zt = (it.get("zona") or {}).get("techo")
        zt = float(zt) if zt is not None else None
        estado_vivo = calcular_estado_actual(precio, conf, inv, zt)
        cierre_hoy = post_cierre and fecha_dato == hoy_ny
        ya_cerrado_hoy = antes.get("ultimo_cierre_fecha") == hoy_ny
        precio_alta = antes.get("precio_alta") if antes.get("precio_alta") is not None else it.get("precio_alta", precio)
        fecha_alta = antes.get("fecha_alta") or it.get("fecha_alta") or hoy_ny
        cierres_conf = antes.get("cierres_sobre_confirmacion", 0)
        cierres_inv = antes.get("cierres_bajo_invalidacion", 0)
        cierres_sma = antes.get("cierres_bajo_sma50", 0)
        estado_cierre = antes.get("estado_cierre")      # estado fijado con el último cierre
        ultimo_cierre_fecha = antes.get("ultimo_cierre_fecha")
        min_c, max_c = antes.get("min_cierre"), antes.get("max_cierre")
        vol = r.get("Vol_rel")
        # --- pisos de rebote: la zona de demanda y (si está activada) la media de 50 ruedas ---
        pisos = []
        if (it.get("zona") or {}).get("piso") is not None and zt is not None:
            pisos.append(("zona de demanda", float(it["zona"]["piso"]), zt))
        if it.get("usar_sma50") and r.get("SMA50"):
            sma = float(r["SMA50"])
            pisos.append(("media de 50 ruedas", round(sma * (1 - BANDA_SMA50), 2), round(sma * (1 + BANDA_SMA50), 2)))
        toques = dict(antes.get("toques") or {})
        escenario = antes.get("escenario_entrada")

        if not antes:
            estado_cierre = "en_zona" if estado_vivo == "en_zona" else "esperando"   # punto de partida: el cambio se avisa con el primer cierre
            eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": t, "evento": "alta", "precio": round(precio, 2),
                            "confirmacion": conf, "invalidacion": inv, "motivo": it.get("motivo"),
                            "fr": r.get("RS_Score"), "rsi": r.get("RSI")})

        if cierre_hoy and not ya_cerrado_hoy:
            if conf is not None and precio >= conf:
                cierres_conf, cierres_inv = cierres_conf + 1, 0
            elif inv is not None and precio < inv:
                cierres_inv, cierres_conf = cierres_inv + 1, 0
            else:
                cierres_conf = cierres_inv = 0
            nuevo = ("confirmada" if cierres_conf > 0 else "invalidada" if cierres_inv > 0 else
                     "en_zona" if estado_vivo == "en_zona" else "esperando")
            cierres_sma = 0 if r.get("Sobre_SMA50") else cierres_sma + 1
            min_c = precio if min_c is None else min(min_c, precio)
            max_c = precio if max_c is None else max(max_c, precio)
            eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": t, "evento": "cierre", "precio": round(precio, 2),
                            "hoy_pct": r.get("Var_dia_%"), "vol_rel": vol, "rsi": r.get("RSI"), "fr": r.get("RS_Score"),
                            "estado": nuevo, "cierres_sobre_confirmacion": cierres_conf, "cierres_bajo_invalidacion": cierres_inv})
            if estado_cierre is not None and nuevo != estado_cierre:
                eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": t, "evento": "cambio_estado",
                                "de": estado_cierre, "a": nuevo, "precio": round(precio, 2)})
                if nuevo in ("invalidada", "en_zona"):
                    mensajes.append(_msg_cierre(it, nuevo, precio, {
                        "conf": conf, "inv": inv, "zona_techo": zt, "cierres": cierres_conf,
                        "vol": (f"{vol * 100:.0f}% del promedio" if vol is not None else "sin dato"),
                        "vol_ok": vol is not None and vol >= 1.0, "antes": estado_cierre}))
            estado_cierre, ultimo_cierre_fecha = nuevo, hoy_ny

        # toque de piso (durante la rueda o al cierre): se marca una vez; el aviso es solo si el activo ya estaba en seguimiento
        for nombre, p_s, t_s in pisos:
            if p_s <= precio <= t_s and fecha_dato == hoy_ny:
                vigente = toques.get(nombre) and _dias(toques[nombre], hoy_ny) <= DIAS_VALIDEZ_TOQUE
                if not vigente:
                    toques[nombre] = hoy_ny
                    eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": t, "evento": "toque_piso", "piso": nombre,
                                    "nivel": [p_s, t_s], "precio": round(precio, 2)})
                    if antes and not post_cierre:
                        mensajes.append(_msg_toque(t, nombre, p_s, t_s, inv if inv is not None else p_s, precio))
        # escenario de entrada: se evalúa SOLO con el cierre de la rueda
        if cierre_hoy and not ya_cerrado_hoy:
            nuevo_esc = None
            if conf is not None and precio >= conf:
                nuevo_esc = {"tipo": "ruptura", "nivel": conf, "detalle": f"Superó su nivel de confirmación ({_num(conf)}): {(it.get('confirmacion') or {}).get('texto', '')}"}
            else:
                for nombre, p_s, t_s in pisos:
                    tq = toques.get(nombre)
                    if tq and _dias(tq, hoy_ny) <= DIAS_VALIDEZ_TOQUE and precio > t_s and (inv is None or precio >= inv):
                        nuevo_esc = {"tipo": "rebote", "nivel": t_s, "piso": nombre,
                                     "inv": (p_s if nombre.startswith("media") else inv),
                                     "detalle": f"Llegó a su piso ({nombre}: {_num(p_s)} a {_num(t_s)}) el {tq[8:10]}/{tq[5:7]} y la rueda cerró por encima."}
                        break
            if nuevo_esc:
                nuevo_esc.update({"fecha": hoy_ny, "precio": round(precio, 2), "vol_rel": vol})
                if not (escenario and escenario.get("tipo") == nuevo_esc["tipo"]):
                    mensajes.append(_msg_escenario(t, nuevo_esc["tipo"], precio, nuevo_esc["nivel"], nuevo_esc.get("inv") or (inv if inv is not None else nuevo_esc["nivel"]), vol, nuevo_esc["detalle"],
                                                 calcular_riesgo(precio, nuevo_esc.get("inv") or inv, conf, r, bw_p33, bw_p67)))
                    eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": t, "evento": "escenario_entrada", "tipo": nuevo_esc["tipo"],
                                    "precio": round(precio, 2), "nivel": nuevo_esc["nivel"], "vol_rel": vol})
                escenario = nuevo_esc
            else:
                if escenario:
                    eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": t, "evento": "escenario_termina", "precio": round(precio, 2)})
                escenario = None
                if inv is not None and precio < inv:
                    toques = {}      # invalidado: se borran los toques; hay que volver a tocar el piso

        # estado que se muestra: el vivo (con el precio de la última corrida). Los cierres se cuentan aparte.
        mostrado = estado_vivo
        items.append({
            "ticker": t, "motivo": it.get("motivo"), "vigilar": it.get("vigilar", []), "nota": it.get("nota"),
            "confirmacion": {"nivel": conf, "texto": (it.get("confirmacion") or {}).get("texto")},
            "invalidacion": {"nivel": inv, "texto": (it.get("invalidacion") or {}).get("texto")},
            "zona": it.get("zona"), "fecha_alta": fecha_alta, "precio_alta": precio_alta,
            "precio": round(precio, 2), "fecha_dato": fecha_dato, "hoy_pct": r.get("Var_dia_%"),
            "desde_alta_pct": round((precio / precio_alta - 1) * 100, 2) if precio_alta else None,
            "dist_confirmacion_pct": round((conf / precio - 1) * 100, 2) if conf else None,
            "dist_invalidacion_pct": round((inv / precio - 1) * 100, 2) if inv else None,
            "rsi": r.get("RSI"), "fr": r.get("RS_Score"), "vol_rel": vol, "beta": r.get("Beta"),
            "estado": mostrado, "estado_etiqueta": ETIQUETA_ESTADO.get(mostrado, mostrado),
            "estado_cierre": estado_cierre, "ultimo_cierre_fecha": ultimo_cierre_fecha,
            "cierres_sobre_confirmacion": cierres_conf, "cierres_bajo_invalidacion": cierres_inv,
            "min_cierre": min_c, "max_cierre": max_c, "cierres_bajo_sma50": cierres_sma,
            "toques": toques, "escenario_entrada": escenario,
            "riesgo": calcular_riesgo(precio, inv, conf, r, bw_p33, bw_p67),
            "pisos": [{"nombre": n, "piso": a, "techo": b} for n, a, b in pisos],
            "salida_sugerida": motivos_salida({"cierres_bajo_invalidacion": cierres_inv, "cierres_bajo_sma50": cierres_sma,
                                               "cierres_sobre_confirmacion": cierres_conf, "fecha_alta": fecha_alta}, r, hoy_ny),
        })

    candidatos = buscar_candidatos(filas, zonas, {i["ticker"] for i in lista})
    # bitácora de candidatos y salidas sugeridas: una vez por día, con el primer cierre (para medirlos después)
    log_dia = prev.get("log_candidatos_fecha") if isinstance(prev, dict) else None
    hay_cierre = post_cierre and any(f.get("Fecha_dato") == hoy_ny for f in list(filas.values())[:5])
    if hay_cierre and log_dia != hoy_ny:
        for c in candidatos:
            eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": c["ticker"], "evento": "candidato", "precio": c["precio"],
                            "fr": c["fr"], "rsi": c["rsi"], "radar_score": c["radar_score"], "marcas": c["marcas"]})
        for i in items:
            if i.get("salida_sugerida"):
                eventos.append({"ts": ts, "fecha": hoy_ny, "ticker": i["ticker"], "evento": "salida_sugerida",
                                "precio": i["precio"], "motivos": i["salida_sugerida"]})
        log_dia = hoy_ny
    salida = {"actualizado": ts, "items": items, "candidatos": candidatos, "log_candidatos_fecha": log_dia}
    enviados = 0
    if modo == "produccion":
        if enviar:
            from telegram_bot import enviar_mensaje
            for m in mensajes:
                if enviar_mensaje(token, chat_id, m + "\n   (Información y escenarios, no una recomendación.)"):
                    enviados += 1
        if eventos:
            os.makedirs(os.path.dirname(RUTA_LOG), exist_ok=True)
            with open(RUTA_LOG, "a", encoding="utf-8") as f:   # solo agregar, nunca reescribir
                for e in eventos:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
        os.makedirs(os.path.dirname(RUTA_ESTADO), exist_ok=True)
        with open(RUTA_ESTADO, "w", encoding="utf-8") as f:
            json.dump(salida, f, ensure_ascii=False, indent=2)
        log.info(f"Entradas en seguimiento: {len(items)} activo(s), {len(eventos)} evento(s), {enviados} aviso(s) enviados")
    else:
        log.info(f"MODO=test -- entradas en seguimiento: {len(items)} activo(s), {len(mensajes)} aviso(s) NO enviados, no se guarda")
    return {"avisos": len(mensajes), "mensajes": mensajes, "eventos": eventos, "salida": salida}
