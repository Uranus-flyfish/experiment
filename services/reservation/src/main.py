"""
NekoCafe Reservation Service
=============================
猫咪主题咖啡馆桌位预约服务 — 实验三 PoC

基于 OpenTelemetry 实现端到端可观测性：
- Traces: OTLP → Tempo/Jaeger
- Metrics: Prometheus /metrics endpoint
- Logs: 结构化 JSON, trace_id 自动关联
"""

import os
import time
import uuid
import logging
import json
import sys
from datetime import datetime, timezone, timedelta

from flask import Flask, request, jsonify, g
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Logging — JSON structured, trace-aware
# ---------------------------------------------------------------------------
class TraceFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "reservation",
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
        }
        return json.dumps(log_obj, ensure_ascii=False)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(TraceFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("reservation")

# ---------------------------------------------------------------------------
# OpenTelemetry
# ---------------------------------------------------------------------------
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Resource
resource = Resource(attributes={
    "service.name": "reservation",
    "service.version": "0.1.0",
    "deployment.environment": os.environ.get("DEPLOY_ENV", "dev"),
})

# Tracer
provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(
    endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317"),
    insecure=True,
)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# Meter
metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(
        endpoint=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://tempo:4317"),
        insecure=True,
    )
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter(__name__)

# Custom metrics
reservation_counter = meter.create_counter(
    "reservation_requests_total",
    description="Total reservation create requests",
)
reservation_duration = meter.create_histogram(
    "reservation_duration_seconds",
    description="Reservation operation duration",
)

# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)
FlaskInstrumentor().instrument_app(app)


# ---------------------------------------------------------------------------
# Trace ID injection into logs
# ---------------------------------------------------------------------------
@app.before_request
def before_request():
    g.start_time = time.time()
    span = trace.get_current_span()
    ctx = span.get_span_context()
    g.trace_id = format(ctx.trace_id, "032x") if ctx.trace_id else None
    g.span_id = format(ctx.span_id, "016x") if ctx.span_id else None


@app.after_request
def after_request(response):
    duration = time.time() - g.start_time
    trace_id = getattr(g, "trace_id", None)
    log_data = {
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "duration_ms": round(duration * 1000, 2),
        "trace_id": trace_id,
    }
    logger.info("request", extra={
        "trace_id": trace_id,
        "span_id": getattr(g, "span_id", None),
    })
    response.headers["X-Trace-Id"] = trace_id or ""
    response.headers["X-Duration-Ms"] = str(round(duration * 1000, 2))
    return response


# ---------------------------------------------------------------------------
# In-memory data store (PoC — production would use PostgreSQL)
# ---------------------------------------------------------------------------
reservations_db = {}
tables_db = [
    {"id": "table-001", "name": "A1", "capacity": 2, "zone": "window", "storeId": "store-001"},
    {"id": "table-002", "name": "A2", "capacity": 2, "zone": "window", "storeId": "store-001"},
    {"id": "table-003", "name": "B1", "capacity": 4, "zone": "center", "storeId": "store-001"},
    {"id": "table-004", "name": "B2", "capacity": 4, "zone": "center", "storeId": "store-001"},
    {"id": "table-005", "name": "C1", "capacity": 6, "zone": "vip", "storeId": "store-001"},
    {"id": "table-006", "name": "A3", "capacity": 2, "zone": "window", "storeId": "store-002"},
    {"id": "table-007", "name": "B3", "capacity": 4, "zone": "center", "storeId": "store-002"},
    {"id": "table-008", "name": "C2", "capacity": 8, "zone": "vip", "storeId": "store-002"},
]

# Time slots (30-min intervals)
TIME_SLOTS = [
    f"{h:02d}:{m:02d}"
    for h in range(10, 22)
    for m in (0, 30)
]


# ---------------------------------------------------------------------------
# Health & Metrics
# ---------------------------------------------------------------------------
@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "service": "reservation", "version": "0.1.0"})


@app.route("/metrics", methods=["GET"])
def prometheus_metrics():
    from prometheus_client import generate_latest, REGISTRY
    return generate_latest(REGISTRY), 200, {"Content-Type": "text/plain"}


# ---------------------------------------------------------------------------
# Reservation API — matches OpenAPI 3.0 spec
# ---------------------------------------------------------------------------

@app.route("/api/reservations", methods=["POST"])
def create_reservation():
    """
    创建预约 — POST /api/reservations
    请求体: { storeId, date, timeSlot, guestCount, tableId, note }
    """
    start = time.time()
    with tracer.start_as_current_span("create_reservation") as span:
        try:
            body = request.get_json(force=True) or {}
            store_id = body.get("storeId", "")
            date = body.get("date", "")
            time_slot = body.get("timeSlot", "")
            guest_count = body.get("guestCount", 1)
            table_id = body.get("tableId", "")
            note = body.get("note", "")

            # Validate table availability
            table = next((t for t in tables_db if t["id"] == table_id and t["storeId"] == store_id), None)
            if not table:
                return jsonify({"code": 404, "message": "Table not found"}), 404
            if guest_count > table["capacity"]:
                return jsonify({"code": 400, "message": f"Guest count exceeds table capacity ({table['capacity']})"}), 400

            # Check conflicts
            for r in reservations_db.values():
                if r["tableId"] == table_id and r["date"] == date and r["timeSlot"] == time_slot and r["status"] not in ("CANCELLED",):
                    return jsonify({"code": 409, "message": "Time slot conflict"}), 409

            res_id = f"res-{uuid.uuid4().hex[:12]}"
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            reservation = {
                "id": res_id,
                "storeId": store_id,
                "userId": request.headers.get("X-User-Id", "anonymous"),
                "tableId": table_id,
                "tableName": table["name"],
                "date": date,
                "timeSlot": time_slot,
                "guestCount": guest_count,
                "note": note,
                "status": "PENDING",
                "createdAt": now,
                "updatedAt": now,
            }
            reservations_db[res_id] = reservation
            reservation_counter.add(1, {"status": "success"})
            span.set_attribute("reservation.id", res_id)
            span.set_attribute("reservation.table", table_id)
            logger.info("reservation_created", extra={"reservation_id": res_id, "table_id": table_id})
            return jsonify({"code": 0, "data": reservation}), 201
        except Exception as e:
            reservation_counter.add(1, {"status": "error"})
            span.record_exception(e)
            logger.error("create_reservation_failed", extra={"error": str(e)})
            return jsonify({"code": 500, "message": "Internal server error"}), 500
        finally:
            reservation_duration.record(time.time() - start)


@app.route("/api/reservations", methods=["GET"])
def list_reservations():
    """查询预约列表 — GET /api/reservations?storeId=&date=&status=&page=1&size=20"""
    with tracer.start_as_current_span("list_reservations"):
        store_id = request.args.get("storeId")
        date = request.args.get("date")
        status = request.args.get("status")
        page = int(request.args.get("page", 1))
        size = int(request.args.get("size", 20))

        result = list(reservations_db.values())
        if store_id:
            result = [r for r in result if r["storeId"] == store_id]
        if date:
            result = [r for r in result if r["date"] == date]
        if status:
            result = [r for r in result if r["status"].upper() == status.upper()]

        # Pagination
        total = len(result)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        page_data = result[start_idx:end_idx]

        return jsonify({
            "code": 0,
            "data": {
                "list": page_data,
                "total": total,
                "page": page,
                "size": size,
            },
        })


@app.route("/api/reservations/my", methods=["GET"])
def list_my_reservations():
    """查询本人预约 — GET /api/reservations/my"""
    with tracer.start_as_current_span("list_my_reservations"):
        user_id = request.headers.get("X-User-Id", "anonymous")
        status = request.args.get("status")
        result = [r for r in reservations_db.values() if r["userId"] == user_id]
        if status:
            result = [r for r in result if r["status"].upper() == status.upper()]
        return jsonify({"code": 0, "data": {"list": result, "total": len(result)}})


@app.route("/api/reservations/<res_id>/accept", methods=["POST"])
def accept_reservation(res_id):
    """接受预约: PENDING → CONFIRMED"""
    with tracer.start_as_current_span("accept_reservation"):
        r = reservations_db.get(res_id)
        if not r:
            return jsonify({"code": 404, "message": "Reservation not found"}), 404
        if r["status"] != "PENDING":
            return jsonify({"code": 400, "message": f"Cannot accept status {r['status']}"}), 400
        r["status"] = "CONFIRMED"
        r["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info("reservation_accepted", extra={"reservation_id": res_id})
        return jsonify({"code": 0, "data": r})


@app.route("/api/reservations/<res_id>/arrive", methods=["POST"])
def confirm_arrival(res_id):
    """确认到店: CONFIRMED → ARRIVED"""
    with tracer.start_as_current_span("confirm_arrival"):
        r = reservations_db.get(res_id)
        if not r:
            return jsonify({"code": 404, "message": "Reservation not found"}), 404
        if r["status"] != "CONFIRMED":
            return jsonify({"code": 400, "message": f"Cannot arrive status {r['status']}"}), 400
        r["status"] = "ARRIVED"
        r["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info("reservation_arrived", extra={"reservation_id": res_id})
        return jsonify({"code": 0, "data": r})


@app.route("/api/reservations/<res_id>/complete", methods=["POST"])
def complete_reservation(res_id):
    """完成预约: ARRIVED → COMPLETED"""
    with tracer.start_as_current_span("complete_reservation"):
        r = reservations_db.get(res_id)
        if not r:
            return jsonify({"code": 404, "message": "Reservation not found"}), 404
        if r["status"] != "ARRIVED":
            return jsonify({"code": 400, "message": f"Cannot complete status {r['status']}"}), 400
        r["status"] = "COMPLETED"
        r["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info("reservation_completed", extra={"reservation_id": res_id})
        return jsonify({"code": 0, "data": r})


@app.route("/api/reservations/<res_id>/cancel", methods=["POST"])
def cancel_reservation(res_id):
    """取消预约: PENDING/CONFIRMED → CANCELLED"""
    with tracer.start_as_current_span("cancel_reservation"):
        r = reservations_db.get(res_id)
        if not r:
            return jsonify({"code": 404, "message": "Reservation not found"}), 404
        if r["status"] not in ("PENDING", "CONFIRMED"):
            return jsonify({"code": 400, "message": f"Cannot cancel status {r['status']}"}), 400
        r["status"] = "CANCELLED"
        r["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info("reservation_cancelled", extra={"reservation_id": res_id})
        return jsonify({"code": 0, "data": r})


@app.route("/api/reservations/<res_id>/adjust-table", methods=["POST"])
def adjust_table(res_id):
    """调换桌位: ARRIVED 状态下可调换"""
    with tracer.start_as_current_span("adjust_table"):
        r = reservations_db.get(res_id)
        if not r:
            return jsonify({"code": 404, "message": "Reservation not found"}), 404
        if r["status"] != "ARRIVED":
            return jsonify({"code": 400, "message": "Only ARRIVED reservations can adjust table"}), 400
        body = request.get_json(force=True) or {}
        new_table_id = body.get("newTableId")
        new_table = next((t for t in tables_db if t["id"] == new_table_id), None)
        if not new_table:
            return jsonify({"code": 404, "message": "Target table not found"}), 404
        old_table = r["tableId"]
        r["tableId"] = new_table_id
        r["tableName"] = new_table["name"]
        r["updatedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info("table_adjusted", extra={"reservation_id": res_id, "from": old_table, "to": new_table_id})
        return jsonify({"code": 0, "data": r})


# ---------------------------------------------------------------------------
# Tables & Time Slots API
# ---------------------------------------------------------------------------
@app.route("/api/tables", methods=["GET"])
def list_tables():
    """查询桌位列表"""
    store_id = request.args.get("storeId")
    result = [t for t in tables_db if not store_id or t["storeId"] == store_id]
    return jsonify({"code": 0, "data": {"list": result, "total": len(result)}})


@app.route("/api/timeslots", methods=["GET"])
def list_time_slots():
    """查询时段列表"""
    date = request.args.get("date", "")
    store_id = request.args.get("storeId", "")
    taken = set()
    for r in reservations_db.values():
        if r["date"] == date and r["storeId"] == store_id and r["status"] not in ("CANCELLED",):
            taken.add(r["timeSlot"])
    slots = [{"time": ts, "available": ts not in taken} for ts in TIME_SLOTS]
    return jsonify({"code": 0, "data": {"date": date, "slots": slots}})


@app.route("/api/tables/inventory", methods=["GET"])
def list_table_inventory():
    """查询门店桌位库存（含可用时段）"""
    date = request.args.get("date", "")
    store_id = request.args.get("storeId", "")
    store_tables = [t for t in tables_db if not store_id or t["storeId"] == store_id]
    taken_map = {}
    for r in reservations_db.values():
        if r["date"] == date and r["status"] not in ("CANCELLED",):
            taken_map[r["tableId"]] = taken_map.get(r["tableId"], 0) + 1
    inventory = []
    for t in store_tables:
        total_slots = len(TIME_SLOTS)
        used = taken_map.get(t["id"], 0)
        inventory.append({
            "tableId": t["id"],
            "tableName": t["name"],
            "capacity": t["capacity"],
            "zone": t["zone"],
            "totalSlots": total_slots,
            "usedSlots": min(used, total_slots),
            "availableSlots": total_slots - min(used, total_slots),
        })
    return jsonify({"code": 0, "data": {"date": date, "storeId": store_id, "inventory": inventory}})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    logger.info("reservation_service_starting", extra={"port": port})
    app.run(host="0.0.0.0", port=port, debug=debug)
