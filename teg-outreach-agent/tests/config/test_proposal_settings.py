from config.settings import Settings


def test_proposal_defaults(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    s = Settings()
    assert s.proposal_model == ""
    assert s.proposal_hard_timeout_s == 240  # raised for the Claude CLI proposal path
    assert s.proposal_dir == "./proposals"
    assert s.email_enabled is False
    assert s.smtp_port == 587
