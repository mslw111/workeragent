"""
emailer.py
Sends the briefing report by email via SMTP (defaults to Gmail).
Credentials are read from environment variables.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")

try:
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
except (TypeError, ValueError):
    SMTP_PORT = 587


def send_report(to_address, subject, body):
    """
    Send a plain-text email containing the briefing report.

    Returns (success: bool, message: str).

    Required environment variables:
        SMTP_USER         - sender email address
        SMTP_APP_PASSWORD - app password (not your regular login password)
        SMTP_HOST         - SMTP server host  (default: smtp.gmail.com)
        SMTP_PORT         - SMTP server port  (default: 587)
    """
    if not SMTP_USER or not SMTP_APP_PASSWORD:
        return False, (
            "Email credentials are not configured.\n"
            "Set SMTP_USER and SMTP_APP_PASSWORD in your .env file.\n"
            "For Gmail, generate an App Password at:\n"
            "  https://myaccount.google.com/apppasswords"
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_address
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_APP_PASSWORD)
            server.sendmail(SMTP_USER, to_address, msg.as_string())
        return True, "Email sent successfully."

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Authentication failed.\n"
            "Make sure you are using an App Password, not your regular Gmail password.\n"
            "Generate one at: https://myaccount.google.com/apppasswords"
        )
    except smtplib.SMTPException as exc:
        return False, f"SMTP error: {exc}"
    except OSError as exc:
        return False, f"Connection error: {exc}"
