.PHONY: infra up down migrate makemigrations shell collectstatic seed db-shell redis-cli \
        logs logs-django logs-worker logs-beat \
        test lint type-check format check \
        build rebuild clean prune help

COMPOSE     = docker compose -f docker/docker-compose.dev.yml
DJANGO      = $(COMPOSE) exec django
MANAGE      = $(DJANGO) python manage.py

# 인프라만 시작 (로컬 개발 시) ----------------------------------------------------
infra:
	$(COMPOSE) up -d postgres redis
	@echo ""
	@echo "DB & Redis 준비 완료. 별도 터미널에서 실행하세요: python manage.py runserver"
	@echo ""

# 전체 Docker 환경 ---------------------------------------------------------
up:
	$(COMPOSE) up -d
	@echo ""
	@echo "[ 전체 스택 시작 완료 ]"
	@echo " - API 문서(Swaggr):  http://localhost:8000/api/schema/swagger-ui/"
	@echo " - API 문서(ReDoc) :  http://localhost:8000/api/schema/redoc/"
	@echo " - 프론트엔드 주소 :  https://gechu-frontend.vercel.app/"
	@echo ""

down:
	$(COMPOSE) down

# Django 관리 명령어 -------------------------------------------------------
migrate:
	$(MANAGE) migrate

makemigrations:
	$(MANAGE) makemigrations

# 특정 앱만: make makemigrations-app APP=users
makemigrations-app:
	$(MANAGE) makemigrations $(APP)

shell:
	$(MANAGE) shell

collectstatic:
	$(MANAGE) collectstatic --noinput

seed:
	$(MANAGE) seed_users

# 테스트 -------------------------------------------------------------------
test:
	$(DJANGO) coverage run manage.py test --keepdb
	$(DJANGO) coverage report

# 특정 앱만: make test-app APP=users
test-app:
	$(DJANGO) coverage run manage.py test apps.$(APP) --keepdb
	$(DJANGO) coverage report

# 코드 품질 ----------------------------------------------------------------
check: format lint type-check

lint:
	$(DJANGO) ruff check .

format:
	$(DJANGO) ruff format .

type-check:
	$(DJANGO) mypy apps/

# 로그 ---------------------------------------------------------------------
logs:
	$(COMPOSE) logs -f

logs-django:
	$(COMPOSE) logs -f django

logs-worker:
	$(COMPOSE) logs -f celery-worker

logs-beat:
	$(COMPOSE) logs -f celery-beat

# DB / Redis 접속 ----------------------------------------------------------
db-shell:
	$(COMPOSE) exec postgres psql -U postgres game_db

redis-cli:
	$(COMPOSE) exec redis redis-cli

# 빌드 ---------------------------------------------------------------------
build:
	$(COMPOSE) build

rebuild:
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

# 정리 ---------------------------------------------------------------------
clean:
	$(COMPOSE) down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

# 미사용 Docker 리소스 전체 삭제 (EC2 용량 부족 시)
prune:
	docker system prune -a

# 도움말 -------------------------------------------------------------------
help:
	@echo ""
	@echo "Gechu Backend 개발 명령어"
	@echo ""
	@echo " [ Docker ] "
	@echo "  make infra            DB + Redis만 시작 (로컬 개발 권장)"
	@echo "  make up               전체 Docker 환경 시작"
	@echo "  make down             Docker 환경 중지"
	@echo "  make build            Docker 이미지 빌드"
	@echo "  make rebuild          캐시 없이 이미지 재빌드 후 시작"
	@echo ""
	@echo " [ Django ] "
	@echo "  make migrate          DB 마이그레이션 적용"
	@echo "  make makemigrations   마이그레이션 파일 생성"
	@echo "  make shell            Django 쉘 접속"
	@echo "  make collectstatic    정적 파일 수집"
	@echo "  make seed             유저 시드 데이터 삽입"
	@echo ""
	@echo " [ 테스트 ] "
	@echo "  make test             전체 테스트 + 커버리지"
	@echo "  make test-app APP=users  특정 앱 테스트"
	@echo ""
	@echo " [ 코드 품질 ] "
	@echo "  make check            전체 코드 품질 검사 (format + lint + type-check)"
	@echo "  make lint             Ruff 린트 검사"
	@echo "  make format           Ruff 코드 포맷"
	@echo "  make type-check       MyPy 타입 검사"
	@echo ""
	@echo " [ 로그 ] "
	@echo "  make logs             전체 로그 스트림"
	@echo "  make logs-django      Django 로그"
	@echo "  make logs-worker      Celery Worker 로그"
	@echo "  make logs-beat        Celery Beat 로그"
	@echo ""
	@echo " [ DB / Redis ] "
	@echo "  make db-shell         PostgreSQL 쉘 접속"
	@echo "  make redis-cli        Redis CLI 접속"
	@echo "  make clean            Docker 볼륨 + 캐시 완전 삭제"
	@echo "  make prune            미사용 Docker 리소스 전체 삭제 (EC2 용량 부족 시)"
	@echo ""
