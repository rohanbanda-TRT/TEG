import os

# Tests use a local userspace Postgres 16 instance (no root needed).
# See teg-outreach-agent/scripts/pg.sh for start/stop; the instance lives in
# the session scratchpad and listens on 127.0.0.1:5433 with trust auth, user "teg".
# Override with DATABASE_URL in the environment to point elsewhere.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://teg@127.0.0.1:5433/teg_outreach_test",
)
