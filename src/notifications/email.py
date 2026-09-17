import aiosmtplib
from email.message import EmailMessage

from config.config import get_settings

settings = get_settings()


async def send_email(to: str, subject: str, body: str) -> None:
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
