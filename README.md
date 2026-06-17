# NekoCafé — DevOps PoC 仓库

> NekoCafé 智慧餐饮预约平台 — 实验三 PoC 仓库
>
> 选取实验二的 **预约服务（Reservation）** + **会员服务（Member）** 作为 PoC 核心服务。
>
> **仓库结构选择**: Monorepo，所有服务、基础设施、CI/CD 配置统一管理，降低协作摩擦。

---

## 一键启动

```bash
git clone <repo-url> && cd nekocafe
make up   # docker compose up -d --build
```

**30 分钟内即可完整运行！**

## 验证

```bash
# Reservation Service
curl http://localhost:8081/healthz
# → {"status":"ok","service":"reservation"}

# Member Service
curl http://localhost:8082/healthz
# → {"status":"ok","service":"member"}

# 创建预约
curl -X POST http://localhost:8081/api/reservations \
  -H 'Content-Type: application/json' \
  -d '{"storeId":"store-001","date":"2026-07-01","timeSlot":"12:00","guestCount":2,"tableId":"table-001"}'

# 查看会员概览
curl http://localhost:8082/api/members/me/overview \
  -H 'X-User-Id: user-001'
```

## 项目结构

```
nekocafe/
├── README.md                    # 本文件
├── docker-compose.yml           # 本地一键起栈
├── Makefile                     # 便捷命令集
├── .editorconfig                # 编码规范
├── .pre-commit-config.yaml      # Pre-commit 钩子
├── .github/workflows/
│   ├── ci.yml                   # CI: Lint → Test → SAST → Build → Scan → Integration
│   └── cd.yml                   # CD: BuildPush → Dev → Canary(Staging) → BlueGreen(Prod)
├── services/
│   ├── reservation/             # 预约服务 (Python/Flask)
│   │   ├── Dockerfile           # 多阶段构建, 非root用户, HEALTHCHECK
│   │   ├── requirements.txt     # 依赖锁文件
│   │   ├── src/main.py          # Flask 应用 + OpenTelemetry 埋点
│   │   └── tests/test_smoke.py  # 冒烟测试
│   └── member/                  # 会员服务 (Node.js/Express)
│       ├── Dockerfile           # 多阶段构建, 非root用户, HEALTHCHECK
│       ├── package.json         # 依赖声明
│       ├── src/index.js         # Express 应用
│       └── tests/test_smoke.test.js
├── infra/
│   ├── helm/                    # Helm Chart (D3-5)
│   └── observability/           # Grafana Dashboards JSON
└── docs/
    ├── runbook.md               # 运维手册
    └── rollback.md              # 回滚手册
```

## 技术决策

| 维度 | 决策 | 理由 |
|------|------|------|
| 仓库策略 | Monorepo | PoC 阶段服务少，统一管理 CI/CD/基础设施 |
| 预约服务 | Python/Flask + Gunicorn | 快速原型，与 OpenAPI 契约对齐 |
| 会员服务 | Node.js/Express | 异步友好，生态丰富 |
| 容器化 | 多阶段 Docker 构建 | 镜像最小化（< 200 MB），安全（非 root） |
| 编排 | Docker Compose (本地) + K8s/Helm (环境) | 本地开发体验 + 生产级部署 |
| CI/CD | GitHub Actions | 原生集成，免费额度满足实验要求 |
| 安全 | Trivy 扫描 + CodeQL SAST | 无 HIGH/CRITICAL 漏洞 |
| 可观测性 | OpenTelemetry + Prometheus + 结构化日志 | 三信号齐全 |

## 常用命令

```bash
make up               # 启动全部服务
make down             # 停止并清理
make logs             # 查看日志
make test             # 运行测试
make lint             # 代码检查
make scan             # Trivy 安全扫描
make up-reservation   # 仅启动预约服务
make up-member        # 仅启动会员服务
```

## 环境变量

所有敏感配置通过环境变量注入，**严禁硬编码**。

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PORT` | 服务端口 | 8080 |
| `DEPLOY_ENV` | 部署环境 | dev |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry 导出端点 | http://jaeger:4317 |
| `NODE_ENV` | Node 环境 | production |

## 团队

- **北京林业大学 · 信息学院**
- **《软件工程》课程 · 实验三**
- **案例**: NekoCafé 猫咪主题餐饮预约平台
