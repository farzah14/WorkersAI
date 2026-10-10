#!/usr/bin/env bash
# Production smoke test for the one-VPS worker/scheduler deployment.
# Prints only non-secret status. Live AI health checks are opt-in.
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-compose.production.yml}"

echo "==> Verifying worker and scheduler containers are running"
docker compose -f "$COMPOSE_FILE" ps --status running --format json \
  | grep -q '"worker"' || { echo "FAIL: worker container is not running"; exit 1; }
docker compose -f "$COMPOSE_FILE" ps --status running --format json \
  | grep -q '"scheduler"' || { echo "FAIL: scheduler container is not running"; exit 1; }
echo "OK: worker and scheduler containers are running"

echo "==> Checking database connectivity"
docker compose -f "$COMPOSE_FILE" exec -T worker uv run python - <<'PY'
import asyncio
import os

from psycopg import AsyncConnection


async def main() -> int:
    conn = await AsyncConnection.connect(os.environ["DATABASE_URL"])
    try:
        cur = await conn.execute("select 1")
        row = await cur.fetchone()
        if not row or row[0] != 1:
            print("FAIL: database query returned an unexpected result")
            return 1
        print("OK: database connectivity confirmed")
        return 0
    finally:
        await conn.close()


raise SystemExit(asyncio.run(main()))
PY

if [ "${SMOKE_LIVE_AI_CHECKS:-0}" = "1" ]; then
  echo "==> Optional live AI gateway reachability (no keys, no response bodies)"
  NINEROUTER_URL="${NINEROUTER_BASE_URL:-http://localhost:20128/v1}/models"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$NINEROUTER_URL" || echo "000")
  echo "9Router health: $NINEROUTER_URL -> HTTP $code"
else
  echo "==> Skipping live AI checks (set SMOKE_LIVE_AI_CHECKS=1 to enable)"
fi

echo "==> Smoke test passed"
