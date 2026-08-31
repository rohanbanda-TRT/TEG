import os

os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+psycopg://{os.environ.get('USER', 'postgres')}@localhost:5432/teg_outreach_test",
)
