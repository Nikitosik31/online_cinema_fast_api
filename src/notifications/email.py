"""Sending emails through an SMTP server."""

import aiosmtplib
from email.message import EmailMessage

from config.config import get_settings

settings = get_settings()


async def send_email(to: str, subject: str, body: str) -> None:
    """
    Send a plain-text email.

    The sender is fixed to `noreply@onlinecinema.com`. The SMTP server comes
    from the settings (MailHog in development, no authentication or TLS).
    In tests this function is replaced with a mock.

    Args:
        to (str): Recipient email address.
        subject (str): Email subject.
        body (str): Plain-text body.
    """

    message = EmailMessage()
    message["From"] = "noreply@onlinecinema.com"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
    )
