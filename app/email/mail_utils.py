# app/email/mail_utils.py
import os
import ssl
import smtplib
import imaplib
import email
import re
from html import unescape
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

# =========================
# Config .env
# =========================
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")

# CC opcional para verificación de entrega (dejar vacío si no se desea)
CC_ME = (os.getenv("CC_ME", "") or "").strip()


# =========================
# Utilidades
# =========================
def html_to_text(html: str) -> str:
    """
    Conversión simple HTML -> texto plano (sin dependencias).
    """
    if not html:
        return ""
    # quita scripts/estilos
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    # quita tags
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    # entidades
    text = unescape(text)
    # normaliza espacios
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


# =========================
# IMAP: conexión y lectura
# =========================
def connect_imap():
    """
    Conecta a IMAP, hace login y selecciona INBOX. Retorna el cliente imaplib.IMAP4_SSL.
    """
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        raise RuntimeError("Faltan EMAIL_ADDRESS o EMAIL_APP_PASSWORD para IMAP")

    client = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    client.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
    client.select("INBOX")  # INBOX por defecto
    return client


def fetch_unseen(client):
    """
    Itera sobre correos NO LEÍDOS (UNSEEN) en INBOX.
    Yields: (uid:int, msg:email.message.Message)
    """
    typ, data = client.uid("search", None, "UNSEEN")
    if typ != "OK":
        return

    uids = data[0].split() if data and data[0] else []
    for uid in uids:
        typ, msg_data = client.uid("fetch", uid, "(RFC822)")
        if typ != "OK" or not msg_data or not msg_data[0]:
            continue
        # msg_data[0] es una tupla (b'UID (RFC822 {bytes})', raw_bytes)
        raw_bytes = msg_data[0][1]
        try:
            msg = email.message_from_bytes(raw_bytes)
        except Exception:
            # fallback por si hay caracteres raros
            msg = email.message_from_string(raw_bytes.decode(errors="ignore"))
        yield int(uid), msg


def mark_seen(client, uid: int):
    """
    Marca el mensaje como leído (\\Seen) por UID.
    """
    client.uid("store", str(uid), "+FLAGS", "(\\Seen)")


# =========================
# SMTP: envío
# =========================
def send_mail(to_addr: str, subject: str, body: str) -> dict:
    """
    Envía el correo y devuelve el dict de sendmail():
      - {}  => éxito en todos los destinatarios
      - { 'destinatario': (codigo, b'motivo') } => fallos por destinatario
    """
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        raise RuntimeError("Faltan EMAIL_ADDRESS o EMAIL_APP_PASSWORD para SMTP")

    msg = EmailMessage()
    # Desde SIEMPRE tu cuenta autenticada (para SPF/DKIM correctos)
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_addr
    if CC_ME:
        msg["Cc"] = CC_ME
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-Id"] = make_msgid("biblioteca")
    msg["X-Mailer"] = "biblioteca-bot"
    msg.set_content(body)

    recipients = [to_addr] + ([CC_ME] if CC_ME else [])

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)

        result = server.sendmail(EMAIL_ADDRESS, recipients, msg.as_string())
        print(
            f"[SMTP] From={EMAIL_ADDRESS} To={to_addr} Cc={CC_ME or '-'} Subject={subject}",
            flush=True,
        )
        print(f"[SMTP] sendmail result: {result}", flush=True)  # {} = OK
        return result
