"""
Notificaciones a Telegram. Usa la API HTTP directa de Telegram (sin librerías
externas) -- un solo POST por mensaje, vía requests.

El disclaimer va INCORPORADO en cada mensaje (no depende de que alguien se
acuerde de aclararlo por fuera) -- ver el punto acordado en el diseño.
"""
import logging
import requests

log = logging.getLogger("radar.telegram")

API_BASE = "https://api.telegram.org/bot{token}/sendMessage"

DISCLAIMER = "\n\n⚠️ Señal técnica basada en reglas propias. No es recomendación de inversión."


def enviar_mensaje(token: str, chat_id: str, texto: str) -> bool:
    """Envía un mensaje de texto al chat indicado. Devuelve True/False según éxito.
    Nunca lanza excepción hacia afuera -- un fallo de Telegram no debe tumbar la corrida."""
    if not token or not chat_id or token == "pendiente" or chat_id == "pendiente":
        log.warning("Token o chat_id de Telegram no configurados -- no se envía nada")
        return False

    url = API_BASE.format(token=token)
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True
        log.error(f"Telegram respondió con error: {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        log.error(f"Fallo al enviar mensaje a Telegram: {e}")
        return False


def formatear_alerta(alerta: dict) -> str:
    """Arma el texto de una alerta individual para Telegram (HTML simple)."""
    ticker = alerta.get("Ticker", "?")
    sector = alerta.get("Sector", "?")
    estado = alerta.get("Estado", "")
    score = alerta.get("Score", "")
    recomendacion = alerta.get("Recomendación final", "")
    ajustado_por = alerta.get("Ajustado por", "")

    texto = (
        f"<b>{ticker}</b> ({sector})\n"
        f"{estado} — Score {score}\n"
        f"Recomendación: <b>{recomendacion}</b>"
    )
    if ajustado_por and ajustado_por != "sin ajustes":
        texto += f"\n<i>{ajustado_por}</i>"
    return texto


def notificar_alertas(token: str, chat_id: str, alertas: list, fecha: str) -> int:
    """Envía un mensaje por cada alerta relevante. Devuelve cuántos se enviaron OK."""
    if not alertas:
        return 0

    enviados = 0
    # "HyperTrade" y no "Radar de Mercado" a propósito: las dos apps
    # comparten el mismo bot de Telegram, así que si el encabezado dijera
    # lo mismo en las dos, sería imposible saber cuál app mandó cada
    # aviso una vez que llegan mezclados a la misma conversación.
    encabezado = f"📡 <b>HyperTrade</b> — {fecha}\n{len(alertas)} alerta(s) hoy\n"
    if enviar_mensaje(token, chat_id, encabezado + DISCLAIMER):
        enviados += 1

    for alerta in alertas:
        texto = formatear_alerta(alerta)
        if enviar_mensaje(token, chat_id, texto):
            enviados += 1

    return enviados


LIMITE_CHARS_MENSAJE = 3500  # margen por debajo del límite real de Telegram (4096) para dejar lugar al disclaimer


def _formatear_evento_cuadrante_sector(ev: dict) -> str:
    anterior = ev.get("cuadrante_anterior") or "sin cuadrante todavía"
    delta = ev.get("delta_7d")
    delta_txt = f"{delta:+.1f}" if delta is not None else "?"
    return f"• <b>{ev.get('sector', '?')}</b>: {anterior} → <b>{ev.get('cuadrante_nuevo', '?')}</b> (FR {ev.get('rs_sector', '?')}, 7d {delta_txt})"


def _formatear_evento_cuadrante_ticker(ev: dict) -> str:
    anterior = ev.get("cuadrante_anterior") or "sin cuadrante todavía"
    delta = ev.get("delta_rs_semana")
    delta_txt = f"{delta:+.1f}" if delta is not None else "?"
    return f"• <b>{ev.get('ticker', '?')}</b> ({ev.get('sector', '?')}): {anterior} → <b>{ev.get('cuadrante_nuevo', '?')}</b> (FR {ev.get('rs_score', '?')}, sem {delta_txt})"


def notificar_cambios_cuadrante(token: str, chat_id: str, eventos_sectoriales: list, eventos_ticker: list, fecha: str) -> int:
    """Avisa cuando un sector o un ticker CAMBIÓ de cuadrante de rotación
    (Líder/Mejorando/Debilitándose/Rezagado) en esta corrida -- mismo dato
    que ya se ve en el Cuadrante de Rotación del dashboard
    (rotacion_sectorial.py / rotacion_ticker.py), solo que avisado en el
    momento en que cambia en vez de depender de ir a mirar el gráfico. No
    es una señal de compra/venta nueva -- por eso lleva el mismo
    disclaimer que cualquier otro aviso.

    Se arma en el mínimo de mensajes posible (no uno por cambio) para no
    saturar el chat, partiendo en varios SOLO si no entra en un mensaje de
    Telegram (límite real: 4096 caracteres) -- nunca se recorta la lista
    de cambios, se reparte.

    Ojo (para tener en cuenta si se vuelve ruidoso con el tiempo): si un
    sector o ticker queda justo en el límite entre dos cuadrantes, puede
    cruzar la línea para un lado y para el otro entre corridas del mismo
    día y generar un aviso cada vez -- es el mismo comportamiento que ya
    tiene el registro en el log de transiciones, esto solo lo hace
    visible por Telegram también."""
    if not eventos_sectoriales and not eventos_ticker:
        return 0

    lineas = [f"🔄 <b>HyperTrade</b> — Cambios de cuadrante — {fecha}"]
    if eventos_sectoriales:
        lineas.append("")
        lineas.append("<b>Sectores:</b>")
        lineas.extend(_formatear_evento_cuadrante_sector(e) for e in eventos_sectoriales)
    if eventos_ticker:
        lineas.append("")
        lineas.append("<b>Tickers:</b>")
        lineas.extend(_formatear_evento_cuadrante_ticker(e) for e in eventos_ticker)

    mensajes, actual = [], ""
    for linea in lineas:
        candidato = (actual + "\n" + linea) if actual else linea
        if len(candidato) > LIMITE_CHARS_MENSAJE and actual:
            mensajes.append(actual)
            actual = linea
        else:
            actual = candidato
    if actual:
        mensajes.append(actual)

    enviados = 0
    total = len(mensajes)
    for i, msg in enumerate(mensajes, 1):
        texto = msg + (f"\n\n({i}/{total})" if total > 1 else "") + DISCLAIMER
        if enviar_mensaje(token, chat_id, texto):
            enviados += 1
    return enviados


def _formatear_evento_golden_cross(ev: dict) -> str:
    emoji = "🟢" if ev.get("tipo") == "Golden Cross" else "🔴"
    anterior = ev.get("estado_anterior_confirmado") or "sin estado previo"
    return (f"{emoji} <b>{ev.get('ticker', '?')}</b> ({ev.get('sector', '?')}): "
            f"<b>{ev.get('tipo', '?')}</b> confirmado (SMA50 {ev.get('sma50', '?')} / "
            f"SMA200 {ev.get('sma200', '?')}, venía de {anterior})")


def notificar_golden_cross(token: str, chat_id: str, eventos: list, fecha: str) -> int:
    """Avisa cuando un Golden Cross o Death Cross queda CONFIRMADO (ver
    golden_cross.py -- solo después de sostenerse DIAS_CONFIRMACION ruedas,
    para no avisar un cruce que la lateralización deshace al día siguiente).
    Mismo criterio anti-spam que notificar_cambios_cuadrante: un mensaje por
    corrida, partido solo si no entra en el límite de Telegram."""
    if not eventos:
        return 0

    lineas = [f"⚔️ <b>HyperTrade</b> — Golden/Death Cross confirmado — {fecha}"]
    lineas.append("")
    lineas.extend(_formatear_evento_golden_cross(e) for e in eventos)

    mensajes, actual = [], ""
    for linea in lineas:
        candidato = (actual + "\n" + linea) if actual else linea
        if len(candidato) > LIMITE_CHARS_MENSAJE and actual:
            mensajes.append(actual)
            actual = linea
        else:
            actual = candidato
    if actual:
        mensajes.append(actual)

    enviados = 0
    total = len(mensajes)
    for i, msg in enumerate(mensajes, 1):
        texto = msg + (f"\n\n({i}/{total})" if total > 1 else "") + DISCLAIMER
        if enviar_mensaje(token, chat_id, texto):
            enviados += 1
    return enviados


def _formatear_evento_squeeze(ev: dict) -> str:
    emoji = "🟢" if ev.get("direccion") == "alcista" else "🔴"
    vol_rel = ev.get("vol_rel")
    vol_txt = f"{vol_rel:.1f}x" if vol_rel is not None else "?"
    return (f"{emoji} <b>{ev.get('ticker', '?')}</b> ({ev.get('sector', '?')}): liberación de squeeze "
            f"<b>{ev.get('direccion', '?')}</b> (precio {ev.get('precio', '?')}, volumen {vol_txt} el promedio)")


def notificar_squeeze(token: str, chat_id: str, eventos: list, fecha: str) -> int:
    """Avisa cuando se confirma una liberación de squeeze de Bollinger
    (ver bollinger_squeeze.py -- ruptura de banda con volumen que confirma,
    viniendo de una compresión reciente). Mismo criterio anti-spam que las
    demás notificaciones de esta app."""
    if not eventos:
        return 0

    lineas = [f"🎯 <b>HyperTrade</b> — Liberación de squeeze — {fecha}"]
    lineas.append("")
    lineas.extend(_formatear_evento_squeeze(e) for e in eventos)

    mensajes, actual = [], ""
    for linea in lineas:
        candidato = (actual + "\n" + linea) if actual else linea
        if len(candidato) > LIMITE_CHARS_MENSAJE and actual:
            mensajes.append(actual)
            actual = linea
        else:
            actual = candidato
    if actual:
        mensajes.append(actual)

    enviados = 0
    total = len(mensajes)
    for i, msg in enumerate(mensajes, 1):
        texto = msg + (f"\n\n({i}/{total})" if total > 1 else "") + DISCLAIMER
        if enviar_mensaje(token, chat_id, texto):
            enviados += 1
    return enviados


def notificar_datos_desactualizados(token: str, chat_id: str, desactualizados: list, fecha: str) -> bool:
    """Un solo mensaje resumen cuando algún ticker quedó con dato viejo esta
    corrida (ver datos.py) -- así queda claro que esos tickers NO se
    evaluaron hoy, en vez de que parezca que simplemente no hubo novedades."""
    if not desactualizados:
        return False

    lista = ", ".join(sorted(d["ticker"] for d in desactualizados))
    texto = (
        f"⚠️ <b>Datos no actualizados</b> — {fecha}\n"
        f"{len(desactualizados)} ticker(s) no se evaluaron esta corrida porque su dato "
        f"seguía siendo el del día hábil anterior: {lista}.\n"
        f"Se reintenta solo(s) en la próxima corrida."
    )
    return enviar_mensaje(token, chat_id, texto)
