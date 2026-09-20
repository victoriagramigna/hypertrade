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
    encabezado = f"📡 <b>Radar de Mercado</b> — {fecha}\n{len(alertas)} alerta(s) hoy\n"
    if enviar_mensaje(token, chat_id, encabezado + DISCLAIMER):
        enviados += 1

    for alerta in alertas:
        texto = formatear_alerta(alerta)
        if enviar_mensaje(token, chat_id, texto):
            enviados += 1

    return enviados
