# gechu-backend

Gechu 게임 추천 서비스 백엔드 (Django + DRF)  
개인화 게임 추천 API 서버입니다.

---

## 📌 프로젝트 개요

사용자 취향 기반 게임 추천 기능을 제공하는 REST API 서버입니다.  
Django + DRF 기반으로 개발하며 PostgreSQL을 사용합니다.

---

## 🌿 브랜치 전략

- `main` → 배포 브랜치 (안정 버전 유지)
- `develop` → 개발 통합 브랜치
- `feature/*` → 기능 개발 브랜치

### 🔄 개발 흐름

1. `develop` 브랜치에서 `feature/*` 브랜치 생성
2. 기능 개발 후 PR 생성 (develop 대상)
3. 팀원 1명 이상 승인 후 `develop` 머지
4. 팀원 2명 이상 동의 시 `main` 브랜치로 머지

> PR은 필수입니다. 직접 push 후 merge는 하지 않습니다.

---

## ⚙️ 개발 환경 설정

> 현재 의존성 관리 방식은 팀 협의 중입니다.  
> 아래 두 가지 방법 중 하나를 사용하세요.

---

### ✅ 방법 1️⃣ Poetry 사용 (권장, 협의 중)

> Windows에서는 `poetry shell` 대신 `poetry run ...` 사용 권장

```bash
# 의존성 설치
poetry install --no-root

# 서버 실행
poetry run python manage.py runserver
```

---

### ✅ 방법 2️⃣ 가상환경 + pip 사용

#### 1️⃣ 가상환경 생성

```bash
python -m venv venv
```

#### Git Bash (Windows)

```bash
source venv/Scripts/activate
```

#### PowerShell (Windows)

```powershell
venv\Scripts\activate
```

#### 2️⃣ 패키지 설치

```bash
# (requirements.txt 제공 시)
pip install -r requirements.txt
```

---

## 🗄 데이터베이스 정책

### ✅ 기본 팀 설정: 로컬 PostgreSQL 사용

프로젝트 루트에 `.env` 파일을 생성하고 아래 값을 설정합니다.

```
DB_NAME=gechu
DB_USER=postgres
DB_PASSWORD=본인비밀번호
DB_HOST=127.0.0.1
DB_PORT=5432
```

마이그레이션 실행:

```bash
python manage.py migrate
```

---

### 🐳 선택 사항: Docker PostgreSQL 사용 가능

로컬 PostgreSQL 사용이 어려운 경우 Docker 기반 DB 사용 가능:

```bash
docker compose -f docker-compose.dev-db.yml up -d
```

> Docker 사용은 개인 선택 사항이며 팀 기본 설정은 로컬 PostgreSQL입니다.

---

## ▶️ 개발 서버 실행

```bash
python manage.py runserver
```

(또는 Poetry 사용 시)

```bash
poetry run python manage.py runserver
```

---

## 🔐 환경 변수 규칙

- `.env` 파일은 Git에 커밋하지 않습니다.
- `.env.example` 파일만 저장소에 포함합니다.
- 데이터베이스 비밀번호 등 민감 정보는 반드시 `.env`에 작성합니다.

---

## 🧾 커밋 컨벤션

- `feat:` 기능 추가
- `fix:` 버그 수정
- `refactor:` 리팩토링
- `docs:` 문서 수정
- `chore:` 기타 작업