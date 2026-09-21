"""
Envío de mails vía Gmail (SMTP + contraseña de aplicación).

Requiere 3 variables de entorno (cargadas como Secrets en GitHub):
  EMAIL_USER      -- tu cuenta de Gmail (ej: victoria@gmail.com)
  EMAIL_PASSWORD  -- la CONTRASEÑA DE APLICACIÓN de 16 caracteres
                     (NO tu contraseña normal de Gmail -- se genera en
                     myaccount.google.com/apppasswords, requiere tener
                     la verificación en dos pasos activada)
  EMAIL_TO        -- a qué dirección mandar los avisos (puede ser la
                     misma cuenta, para mandarte mail a vos misma)

Por qué Gmail y no otro servicio: es gratis, no tiene límite de tasa
raro para este volumen de uso, y no depende de un bot externo (a
diferencia de Telegram, que venía fallando).
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

log = logging.getLogger("radar.email")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL


def enviar_email(asunto: str, cuerpo: str, email_user: str, email_password: str, email_to: str) -> bool:
    """
    Manda un mail de texto plano. Devuelve True si se envió sin
    excepciones, False si algo falló (queda logueado el motivo, pero
    nunca frena el resto de la corrida -- un mail que falla no debe
    tirar abajo el pipeline completo).
    """
    if not email_user or not email_password or not email_to:
        log.warning("Faltan credenciales de email (EMAIL_USER/EMAIL_PASSWORD/EMAIL_TO) -- se omite el envío")
        return False

    msg = MIMEMultipart()
    msg["From"] = email_user
    msg["To"] = email_to
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(email_user, email_password)
            server.sendmail(email_user, [email_to], msg.as_string())
        log.info(f"Mail enviado: '{asunto}'")
        return True
    except Exception as e:
        log.error(f"No se pudo enviar el mail '{asunto}': {e}")
        return False
