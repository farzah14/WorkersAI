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
  echo "==> Optional live AI provider reachability (no keys, no response bodies)"
  for url in \
    "https://integrate.api.nvidia.com/v1" \
    "https://openrouter.ai/api/v1" \
    "https://ollama.com/api"; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$url" || echo "000")
    echo "OK: $url -> HTTP $code"
  done
else
  echo "==> Skipping live AI checks (set SMOKE_LIVE_AI_CHECKS=1 to enable)"
fi

echo "==> Smoke test passed"
