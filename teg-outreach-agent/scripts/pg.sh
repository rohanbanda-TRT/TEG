#!/usr/bin/env bash
# Local userspace Postgres 16 for development/tests (no root required).
# Usage: scripts/pg.sh {start|stop|status|psql}
set -euo pipefail

PGBIN=/usr/lib/postgresql/16/bin
PGDATA="${TEG_PGDATA:-$HOME/.local/share/teg-outreach-pg}"
SOCKDIR=/tmp/tegpg
PORT=5433
USER_NAME=teg

start() {
  mkdir -p "$SOCKDIR"
  if [ ! -d "$PGDATA/base" ]; then
    "$PGBIN/initdb" -D "$PGDATA" -U "$USER_NAME" --auth=trust -E UTF8 >/dev/null
  fi
  "$PGBIN/pg_ctl" -D "$PGDATA" \
    -o "-k $SOCKDIR -c listen_addresses='127.0.0.1' -p $PORT" \
    -l "$PGDATA/server.log" start
  sleep 2
  for db in teg_outreach teg_outreach_test; do
    "$PGBIN/psql" -h 127.0.0.1 -p $PORT -U "$USER_NAME" -d postgres -tc \
      "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 || \
      "$PGBIN/psql" -h 127.0.0.1 -p $PORT -U "$USER_NAME" -d postgres -c "CREATE DATABASE $db"
  done
  echo "postgres up on 127.0.0.1:$PORT (user $USER_NAME, dbs: teg_outreach, teg_outreach_test)"
}
stop()   { "$PGBIN/pg_ctl" -D "$PGDATA" stop; }
status() { "$PGBIN/pg_ctl" -D "$PGDATA" status; }
psql()   { "$PGBIN/psql" -h 127.0.0.1 -p $PORT -U "$USER_NAME" "${@:-teg_outreach_test}"; }

"${1:-status}"
