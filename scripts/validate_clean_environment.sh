#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: scripts/validate_clean_environment.sh [--reset]"
  echo "  --reset  Removes only this Compose project's containers and declared local volume before validation."
}

reset_requested=false
case "${1:-}" in
  "") ;;
  --reset) reset_requested=true ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then
  usage >&2
  exit 2
fi

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_root"

for command_name in docker git python3; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing prerequisite: $command_name." >&2
    exit 1
  fi
done
if ! docker compose version >/dev/null 2>&1; then
  echo "Missing prerequisite: Docker Compose plugin." >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example and replace every placeholder with local test values." >&2
  exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Repository must be clean before clean-environment validation." >&2
  exit 1
fi

if [[ "$reset_requested" == true ]]; then
  echo "Reset requested: removing only containers and declared volumes owned by this Compose project."
  docker compose down --volumes --remove-orphans
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --requirement requirements.txt

docker compose up -d
database_ready=false
for _attempt in {1..30}; do
  if docker compose exec -T postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1; then
    database_ready=true
    break
  fi
  sleep 2
done
if [[ "$database_ready" != true ]]; then
  echo "PostgreSQL did not become ready within 60 seconds." >&2
  exit 1
fi

for sql_path in sql/*.sql; do
  sql_name="$(basename "$sql_path")"
  docker compose exec -T postgres sh -c \
    'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f "/docker-entrypoint-initdb.d/$1"' \
    sh "$sql_name"
done

.venv/bin/python -m src.cli all
.venv/bin/python -m pytest -q
.venv/bin/python scripts/check_repository_safety.py
git diff --check
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Validation changed tracked repository content." >&2
  git status --short
  exit 1
fi

echo "Clean-environment validation passed: CLI, tests, safety and repository checks succeeded."
