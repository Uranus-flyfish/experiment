.PHONY: up down logs test clean lint up-reservation up-member test-reservation test-member

# ──────────── 一键启动 ────────────
up:
	docker compose up -d --build

# ──────────── 停止并清理 ────────────
down:
	docker compose down -v

# ──────────── 查看日志 ────────────
logs:
	docker compose logs -f

# ──────────── 清理 ────────────
clean:
	docker compose down -v --rmi local

# ──────────── 单独启动服务 ────────────
up-reservation:
	docker compose up -d --build reservation

up-member:
	docker compose up -d --build member

# ──────────── 测试 ────────────
test: test-reservation test-member

test-reservation:
	docker compose exec -T reservation python -m pytest tests/ -v

test-member:
	docker compose exec -T member node --test tests/*.test.js

# ──────────── 依赖安装 ────────────
install-reservation:
	cd services/reservation && pip install -r requirements.txt

install-member:
	cd services/member && npm install

install: install-reservation install-member

# ──────────── Linting ────────────
lint-reservation:
	cd services/reservation && python -m flake8 src/ --max-line-length=120

lint-member:
	cd services/member && npx eslint src/ --fix

lint: lint-reservation lint-member

# ──────────── 安全扫描 ────────────
scan-reservation:
	trivy image nekocafe-reservation:latest

scan-member:
	trivy image nekocafe-member:latest

scan: scan-reservation scan-member

# ──────────── 本地运行（不带Docker） ────────────
run-reservation:
	cd services/reservation && python src/main.py

run-member:
	cd services/member && node src/index.js
