#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
forecast_date="${1:-2026-09-24}"
export RELEASE="${RELEASE:-run-$(date -u +%Y%m%d%H%M%S)}"
[[ "$forecast_date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo 'Date must be YYYY-MM-DD' >&2; exit 2; }
[[ "$RELEASE" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$ ]] || { echo 'Invalid RELEASE tag' >&2; exit 2; }
trap 'echo "Deployment failed. Inspect: docker compose logs --tail=100" >&2' ERR
docker info --format '{{.OSType}}'
docker compose version
docker compose config --quiet
if [[ "${2:-}" == '--check-only' ]]; then
    echo 'Prerequisites and Compose configuration OK. No build or deployment performed.'
    exit 0
fi
docker build --target test -f deploy/Dockerfile.api -t "gold-forecast-test:$RELEASE" .
docker run --rm "gold-forecast-test:$RELEASE"
docker compose build
docker compose run --rm --no-deps api python -m gold_service.run_daily --date "$forecast_date"
docker compose up -d --no-build --wait --wait-timeout 180
docker compose exec -T web wget -qO- http://127.0.0.1:8080/api/forecast/latest
printf '\nDeployment OK: release=%s forecast-request=%s\n' "$RELEASE" "$forecast_date"
echo 'Open http://localhost:8080 (unless WEB_PORT was overridden). AWS delivery requires separate configuration.'
