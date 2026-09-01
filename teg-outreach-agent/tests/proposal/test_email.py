from unittest.mock import MagicMock, patch

from app.proposal.email import send_proposal_email


async def test_returns_false_when_disabled(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("EMAIL_ENABLED", "false")
    from config.settings import get_settings
    get_settings.cache_clear()
    ok = await send_proposal_email(to="x@y.com", pdf_bytes=b"%PDF-x", filename="p.pdf", company="Acme")
    assert ok is False
    get_settings.cache_clear()


async def test_sends_when_enabled(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    monkeypatch.setenv("SMTP_FROM", "teg@example")
    from config.settings import get_settings
    get_settings.cache_clear()
    with patch("app.proposal.email.smtplib.SMTP") as m:
        srv = MagicMock()
        m.return_value.__enter__.return_value = srv
        ok = await send_proposal_email(to="x@y.com", pdf_bytes=b"%PDF-x", filename="p.pdf", company="Acme")
    assert ok is True
    srv.send_message.assert_called_once()
    get_settings.cache_clear()


async def test_returns_false_on_smtp_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example")
    from config.settings import get_settings
    get_settings.cache_clear()
    with patch("app.proposal.email.smtplib.SMTP", side_effect=OSError("no route")):
        ok = await send_proposal_email(to="x@y.com", pdf_bytes=b"%PDF-x", filename="p.pdf", company="Acme")
    assert ok is False
    get_settings.cache_clear()
