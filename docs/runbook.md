# Runbook — 运维应急处置手册

> 适用：NekoCafé Reservation & Member 服务

---

## 告警触发时快速排查

当收到 Grafana AlertManager 告警时，按以下顺序排查：

### 1. 查看 Grafana Dashboard

在 Grafana 中打开 **NekoCafé Service Dashboard**，依次检查：

1. **QPS 面板** — 是否有流量突增？
2. **P99 延迟面板** — P99 延迟是否 > 500ms？
3. **错误率面板** — 5xx 错误率是否 > 1%？
4. **资源使用面板** — CPU/Memory 是否超过 limits？

### 2. 检索日志 (Loki)

```bash
# 检索近 5 分钟 ERROR 日志
{service="reservation"} |= "ERROR" | json | line_format "{{.message}}"

# 按 trace_id 检索
{service="reservation"} |= "<trace_id>"
```

关键日志字段：`timestamp`, `level`, `message`, `trace_id`, `span_id`

### 3. 链路追踪 (Tempo/Jaeger)

```bash
# 在 Tempo UI 中搜索 trace_id
# 找出涉事 span，查看调用链最慢的环节
```

关键词搜索：
- `status.code=Error`
- `duration > 2s`
- `http.status_code=500`

### 4. 检查 Pod 状态 (K8s)

```bash
kubectl get pods -n <env>
kubectl describe pod <pod-name> -n <env>
kubectl logs <pod-name> -n <env> --tail=100
```

### 5. 资源检查

```bash
kubectl top pods -n <env>
kubectl top nodes
kubectl describe hpa -n <env>
```

## 常见问题处置

### 问题：P99 延迟突增

- **可能原因**: 缓存失效、DB 慢查询、GC 停顿
- **处置**: 检查 Redis 连通性、查看慢查询日志、适当扩容

### 问题：错误率 > 1%

- **可能原因**: 下游服务不可用、数据库连接池耗尽
- **处置**: 检查依赖服务健康状态、重启故障 Pod

### 问题：OOMKilled

- **可能原因**: 内存泄漏、流量突增
- **处置**: 增加 memory limits、重启 + 排查内存泄漏

## 告警升级

| 严重级别 | 条件 | 通知通道 |
|----------|------|----------|
| P1-Critical | 错误率 > 5%, P99 > 2s | 电话 + 企业微信 |
| P2-Warning | 错误率 > 1%, P99 > 500ms | 企业微信 |
| P3-Info | 资源使用 > 80% | 邮件 |
