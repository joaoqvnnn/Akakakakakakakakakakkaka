import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    async def send(
        session: AsyncSession,
        to_email: str,
        subject: str,
        body_text: str,
    ) -> bool:
        enabled = await SettingsService.get_bool(session, "smtp_enabled")
        if not enabled:
            logger.warning("SMTP desabilitado")
            return False

        host = await SettingsService.get(session, "smtp_host")
        port = await SettingsService.get_int(session, "smtp_port") or 587
        user = await SettingsService.get(session, "smtp_user")
        password = await SettingsService.get(session, "smtp_password")
        from_addr = await SettingsService.get(session, "smtp_from") or user
        use_tls = await SettingsService.get_bool(session, "smtp_use_tls")

        if not host or not from_addr:
            logger.error("SMTP sem host/from")
            return False

        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        try:
            with smtplib.SMTP(host, port, timeout=30) as server:
                if use_tls:
                    server.starttls()
                if user and password:
                    server.login(user, password)
                server.sendmail(from_addr, [to_email], msg.as_string())
            return True
        except Exception:
            logger.exception("Falha SMTP")
            return False
