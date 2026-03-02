"""
E-Mail-Versand mit Anhängen via Gmail SMTP.

Benötigt ein Gmail App-Passwort:
1. Google Account → Sicherheit → 2-Faktor-Authentifizierung aktivieren
2. Dann: App-Passwörter → Neues App-Passwort erstellen
3. Das 16-stellige Passwort in den Einstellungen eintragen
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


SENDER_EMAIL = "miroslav.mikulic@gmail.com"
SENDER_NAME = "Miroslav Mikulic"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def send_email_with_attachments(
    to_email: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]],
    gmail_app_password: str,
) -> tuple[bool, str]:
    """
    Send an email with PDF attachments via Gmail SMTP.

    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body text
        attachments: List of (filename, bytes) tuples
        gmail_app_password: Gmail App Password (16 chars, no spaces)

    Returns:
        (success: bool, message: str)
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        # Body
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attachments
        for filename, file_bytes in attachments:
            part = MIMEApplication(file_bytes, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

        # Send
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, gmail_app_password.replace(" ", ""))
            server.send_message(msg)

        return True, f"E-Mail an {to_email} gesendet"

    except smtplib.SMTPAuthenticationError:
        return False, "Gmail App-Passwort ungültig. Bitte überprüfen (16 Zeichen, ohne Leerzeichen)."
    except Exception as e:
        return False, str(e)
