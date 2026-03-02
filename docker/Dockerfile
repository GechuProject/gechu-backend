FROM python:3.13-slim

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Poetry 설치
RUN pip install --upgrade pip && pip install poetry

# 가상환경 없이 시스템에 직접 설치
RUN poetry config virtualenvs.create false

# 의존성 파일 먼저 복사 (레이어 캐시 활용)
COPY pyproject.toml poetry.lock ./

# 의존성 설치
RUN poetry install --no-interaction --no-root

COPY . .