from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from config.settings import get_settings

_log = logging.getLogger(__name__)


def _send_sync(to: str, pdf_bytes: bytes, filename: str, company: str) -> bool:
    s = get_settings()
    msg = EmailMessage()
    msg["Subject"] = f"Your Tech Expo Gujarat 2026 proposal — {company}"
    msg["From"] = s.smtp_from or s.smtp_user
    msg["To"] = to
    msg.set_content(
        f"Hi,\n\nAttached is your personalized Tech Expo Gujarat 2026 proposal for {company}.\n"
        "All figures are indicative and subject to confirmation at booking.\n\n— The TEG team"
    )
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=filename)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as srv:
            srv.ehlo()
            if s.smtp_user:
                srv.starttls()
                srv.login(s.smtp_user, s.smtp_pass)
            srv.send_message(msg)
        return True
    except (OSError, smtplib.SMTPException) as exc:
        _log.warning("proposal email to %s failed: %s", to, exc)
        return False


async def send_proposal_email(*, to: str, pdf_bytes: bytes, filename: str, company: str) -> bool:
    if not get_settings().email_enabled:
        return False
    return await asyncio.to_thread(_send_sync, to, pdf_bytes, filename, company)
