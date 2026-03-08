#!/bin/bash
# Docker에서 CI와 동일한 검사 실행 (푸시 전 로컬 확인용)
set -e
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker/docker-compose.dev.yml"

echo ">>> Starting postgres & redis..."
$COMPOSE up -d postgres redis
echo ">>> Waiting for postgres..."
sleep 5

echo ">>> Ruff format & check..."
$COMPOSE run --rm django sh -c "cd /app && python -m ruff format . --check && python -m ruff check ."

echo ">>> Mypy..."
$COMPOSE run --rm django sh -c "cd /app && python -m mypy ."

echo ">>> Migrate & test..."
$COMPOSE run --rm django sh -c "cd /app && python manage.py migrate && python manage.py test"

echo ">>> CI checks passed."
