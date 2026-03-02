set -eo pipefail

COLOR_GREEN=`tput setaf 2;`
COLOR_BLUE=`tput setaf 4;`
COLOR_NC=`tput sgr0;` # No Color

cd "$(dirname "$0")/../.."

echo "${COLOR_BLUE}Running Ruff (Format & Isort)${COLOR_NC}"
# Ruff 하나로 black(포맷팅) + isort(정렬)를 동시에 수행합니다.
poetry run ruff format .
echo ""


echo "${COLOR_BLUE}Running Ruff (Lint & Auto-fix)${COLOR_NC}"
# 자동 수정 가능한 린트 에러를 고치고 불필요한 import를 제거합니다.
poetry run ruff check . --fix
echo ""

echo "${COLOR_GREEN}Code Formatting & Linting Successfully!${COLOR_NC}"