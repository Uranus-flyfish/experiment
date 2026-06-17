# Rollback — 一键回滚手册

> NekoCafé 服务回滚操作指南

---

## Helm 回滚（推荐）

```bash
# 查看部署历史
helm history nekocafe-reservation -n prod
helm history nekocafe-member -n prod

# 回滚到上一个版本
helm rollback nekocafe-reservation -n prod
helm rollback nekocafe-member -n prod

# 回滚到指定版本
helm rollback nekocafe-reservation 3 -n prod
```

## 蓝绿部署回滚（生产环境）

```bash
# 切回 Blue 环境
kubectl patch svc nekocafe-reservation -n prod \
  -p '{"spec":{"selector":{"color":"blue","app":"nekocafe-reservation"}}}'

kubectl patch svc nekocafe-member -n prod \
  -p '{"spec":{"selector":{"color":"blue","app":"nekocafe-member"}}}'

# 验证切换
kubectl get svc -n prod nekocafe-reservation -o jsonpath='{.spec.selector.color}'

# 清理失败版本
helm uninstall nekocafe-green -n prod
```

## 金丝雀部署回滚（Staging 环境）

```bash
# 撤销金丝雀
helm rollback nekocafe -n staging

# 或直接切换回稳定版本
helm upgrade --install nekocafe ./infra/helm \
  --namespace staging \
  -f ./infra/helm/values-staging.yaml \
  --set image.tag=<previous-stable-tag> \
  --set canary.enabled=false
```

## Docker Compose 回滚（本地/Dev）

```bash
# 切换到上一个 tag
git checkout <previous-tag>
docker compose up -d --build
```

## 自动回滚触发条件

CD 流水线在以下条件自动触发回滚：

| 条件 | 阈值 | 操作 |
|------|------|------|
| P95 延迟 | > 500ms | 自动回滚 |
| 错误率 | > 1% | 自动回滚 |
| 健康检查 | 连续 3 次失败 | 自动回滚 |
| 部署超时 | > 5 分钟 | 自动回滚 |

## 回滚后操作

1. 通知团队回滚已完成
2. 在 Grafana 确认指标恢复正常
3. 在 Loki/Tempo 排查根因
4. 修复后重新部署
5. 更新 Post-Mortem 文档
