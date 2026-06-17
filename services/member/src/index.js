/**
 * NekoCafe Member Service
 * ========================
 * 猫咪主题咖啡馆会员服务 — 实验三 PoC
 *
 * 基于 Express 实现会员档案、积分、优惠券、等级权益 API
 * 日志输出结构化 JSON，traceId 贯穿请求链
 */

const express = require("express");
const cors = require("cors");
const { v4: uuidv4 } = require("uuid");

const app = express();
const PORT = process.env.PORT || 8080;

app.use(cors());
app.use(express.json());

// ---------------------------------------------------------------------------
// Structured JSON logger
// ---------------------------------------------------------------------------
function logger(level, msg, extra = {}) {
  const logObj = {
    timestamp: new Date().toISOString(),
    level,
    logger: "member",
    message: msg,
    service: "member",
    ...extra,
  };
  const out = level === "error" ? process.stderr : process.stdout;
  out.write(JSON.stringify(logObj) + "\n");
}

// ---------------------------------------------------------------------------
// Trace ID middleware
// ---------------------------------------------------------------------------
app.use((req, res, next) => {
  req.traceId = req.headers["x-trace-id"] || uuidv4();
  req.startTime = Date.now();
  res.setHeader("X-Trace-Id", req.traceId);
  res.on("finish", () => {
    const duration = Date.now() - req.startTime;
    logger("info", "request", {
      trace_id: req.traceId,
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration_ms: duration,
    });
  });
  next();
});

// ---------------------------------------------------------------------------
// In-memory data store (PoC)
// ---------------------------------------------------------------------------
const memberLevels = [
  { code: "SILVER", name: "银卡会员", minPoints: 0, maxPoints: 499, discount: 1.0 },
  { code: "GOLD", name: "金卡会员", minPoints: 500, maxPoints: 1999, discount: 0.95 },
  { code: "PLATINUM", name: "铂金会员", minPoints: 2000, maxPoints: Infinity, discount: 0.9 },
];

const benefits = [
  { levelCode: "SILVER", benefitCode: "birthday_gift", name: "生日专属礼品", description: "生日当月到店享专属猫咪小礼品一份" },
  { levelCode: "SILVER", benefitCode: "wifi", name: "免费WiFi", description: "门店免费高速WiFi" },
  { levelCode: "GOLD", benefitCode: "birthday_gift", name: "生日专属礼品", description: "生日当月到店享专属猫咪小礼品一份" },
  { levelCode: "GOLD", benefitCode: "priority_queue", name: "优先排队", description: "高峰时段优先排队权益" },
  { levelCode: "GOLD", benefitCode: "monthly_coupon", name: "月度优惠券", description: "每月可领取1张满减优惠券" },
  { levelCode: "PLATINUM", benefitCode: "birthday_gift", name: "生日专属盛宴", description: "生日当月到店享猫咪主题盛宴" },
  { levelCode: "PLATINUM", benefitCode: "priority_queue", name: "VIP优先通道", description: "无需排队，专属VIP通道" },
  { levelCode: "PLATINUM", benefitCode: "monthly_coupon", name: "月度优惠券×2", description: "每月可领取2张满减优惠券" },
  { levelCode: "PLATINUM", benefitCode: "exclusive_events", name: "专属猫咪活动", description: "优先参与限定猫咪主题活动" },
  { levelCode: "PLATINUM", benefitCode: "cat_naming", name: "猫咪命名权", description: "可为新到店猫咪提名" },
];

const membersDb = {};
const pointsDb = {};
const couponsDb = {};
const preferenceTagsDb = {};

// Seed: default member
membersDb["user-001"] = {
  userId: "user-001",
  nickname: "猫咪爱好者小明",
  avatar: "https://cdn.nekocafe.dev/avatars/default.png",
  phone: "138****1234",
  points: 680,
  levelCode: "GOLD",
  levelName: "金卡会员",
  createdAt: "2026-01-15T00:00:00Z",
};
pointsDb["user-001"] = [
  { id: "pt-001", sceneType: "ORDER", sceneName: "消费积分", points: 120, balance: 680, bizId: "order-1001", createdAt: "2026-06-15T12:00:00Z" },
  { id: "pt-002", sceneType: "CHECKIN", sceneName: "到店积分", points: 20, balance: 560, bizId: "res-5001", createdAt: "2026-06-14T14:30:00Z" },
  { id: "pt-003", sceneType: "ORDER", sceneName: "消费积分", points: 89, balance: 540, bizId: "order-0987", createdAt: "2026-06-13T18:20:00Z" },
  { id: "pt-004", sceneType: "ORDER", sceneName: "消费积分", points: 250, balance: 451, bizId: "order-0888", createdAt: "2026-06-10T11:15:00Z" },
  { id: "pt-005", sceneType: "CHECKIN", sceneName: "到店积分", points: 20, balance: 201, bizId: "res-4800", createdAt: "2026-06-08T15:00:00Z" },
];
couponsDb["user-001"] = [
  { id: "cpn-001", name: "满100减20优惠券", type: "FULL_REDUCTION", threshold: 100, value: 20, status: "AVAILABLE", expireAt: "2026-07-31T23:59:59Z" },
  { id: "cpn-002", name: "猫咪冰淇淋免费券", type: "FREE_ITEM", threshold: 0, value: 0, status: "AVAILABLE", expireAt: "2026-08-15T23:59:59Z" },
  { id: "cpn-003", name: "满200减50优惠券", type: "FULL_REDUCTION", threshold: 200, value: 50, status: "USED", expireAt: "2026-05-31T23:59:59Z" },
];
preferenceTagsDb["user-001"] = ["布偶猫", "美短", "安静角落"];

function getLevel(points) {
  for (let i = memberLevels.length - 1; i >= 0; i--) {
    if (points >= memberLevels[i].minPoints) return memberLevels[i];
  }
  return memberLevels[0];
}

function getOrCreateMember(userId) {
  if (!membersDb[userId]) {
    membersDb[userId] = {
      userId,
      nickname: "新会员",
      avatar: "https://cdn.nekocafe.dev/avatars/default.png",
      phone: "未绑定",
      points: 0,
      levelCode: "SILVER",
      levelName: "银卡会员",
      createdAt: new Date().toISOString(),
    };
    pointsDb[userId] = [];
    couponsDb[userId] = [];
    preferenceTagsDb[userId] = [];
  }
  return membersDb[userId];
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------
app.get("/healthz", (req, res) => {
  res.json({ status: "ok", service: "member", version: "0.1.0" });
});

// ---------------------------------------------------------------------------
// Member API
// ---------------------------------------------------------------------------

// GET /api/members/me/overview
app.get("/api/members/me/overview", (req, res) => {
  const userId = req.headers["x-user-id"] || "user-001";
  const member = getOrCreateMember(userId);
  const level = getLevel(member.points);
  const nextLevel = memberLevels.find(l => l.minPoints > member.points);

  // Growth progress
  let growthPct = 100;
  let pointsToNext = 0;
  if (nextLevel) {
    const currentFloor = level.minPoints;
    const nextFloor = nextLevel.minPoints;
    growthPct = Math.min(100, Math.round(((member.points - currentFloor) / (nextFloor - currentFloor)) * 100));
    pointsToNext = nextFloor - member.points;
  }

  const coupons = couponsDb[userId] || [];
  const points = pointsDb[userId] || [];
  const levelBenefits = benefits.filter(b => b.levelCode === level.code);

  res.json({
    code: 0,
    data: {
      profile: { userId: member.userId, nickname: member.nickname, avatar: member.avatar, phone: member.phone, levelCode: member.levelCode, levelName: level.name },
      growth: { currentLevel: level.name, nextLevel: nextLevel ? nextLevel.name : null, currentPoints: member.points, pointsToNext, growthPercentage: growthPct },
      couponSummary: { available: coupons.filter(c => c.status === "AVAILABLE").length, used: coupons.filter(c => c.status === "USED").length, expired: coupons.filter(c => c.status === "EXPIRED").length },
      recentPoints: points.slice(0, 5).map(p => ({ sceneType: p.sceneType, sceneName: p.sceneName, points: p.points, createdAt: p.createdAt })),
      benefits: levelBenefits,
    },
  });
});

// GET /api/members/me/points?page=1&size=10
app.get("/api/members/me/points", (req, res) => {
  const userId = req.headers["x-user-id"] || "user-001";
  const page = parseInt(req.query.page) || 1;
  const size = parseInt(req.query.size) || 10;
  const all = pointsDb[userId] || [];
  const offset = (page - 1) * size;
  const pageData = all.slice(offset, offset + size);
  res.json({ code: 0, data: { list: pageData, total: all.length, page, size } });
});

// GET /api/members/me/benefits
app.get("/api/members/me/benefits", (req, res) => {
  const userId = req.headers["x-user-id"] || "user-001";
  const member = getOrCreateMember(userId);
  const level = getLevel(member.points);
  const levelBenefits = benefits.filter(b => b.levelCode === level.code);
  res.json({ code: 0, data: { levelCode: level.code, levelName: level.name, benefits: levelBenefits } });
});

// GET /api/members/me/coupons?status=AVAILABLE
app.get("/api/members/me/coupons", (req, res) => {
  const userId = req.headers["x-user-id"] || "user-001";
  const status = req.query.status;
  let result = couponsDb[userId] || [];
  if (status) result = result.filter(c => c.status === status.toUpperCase());
  res.json({ code: 0, data: { list: result, total: result.length } });
});

// GET /api/members/levels
app.get("/api/members/levels", (req, res) => {
  const levels = memberLevels.map(l => ({
    code: l.code,
    name: l.name,
    minPoints: l.minPoints,
    maxPoints: l.maxPoints === Infinity ? null : l.maxPoints,
    discount: l.discount,
  }));
  res.json({ code: 0, data: { list: levels, total: levels.length } });
});

// GET /api/members/me/tags
app.get("/api/members/me/tags", (req, res) => {
  const userId = req.headers["x-user-id"] || "user-001";
  const tags = preferenceTagsDb[userId] || [];
  res.json({ code: 0, data: { tags } });
});

// PUT /api/members/me/tags
app.put("/api/members/me/tags", (req, res) => {
  const userId = req.headers["x-user-id"] || "user-001";
  const { tags } = req.body || {};
  if (!Array.isArray(tags)) {
    return res.status(400).json({ code: 400, message: "tags must be an array" });
  }
  preferenceTagsDb[userId] = tags;
  logger("info", "tags_updated", { user_id: userId, tags });
  res.json({ code: 0, data: { tags } });
});

// GET /api/member-badge/:userId (Simple badge endpoint for testing)
app.get("/api/member-badge/:userId", (req, res) => {
  const member = getOrCreateMember(req.params.userId);
  const level = getLevel(member.points);
  res.json({
    code: 0,
    data: {
      userId: member.userId,
      nickname: member.nickname,
      levelCode: level.code,
      levelName: level.name,
      points: member.points,
    },
  });
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  logger("info", "member_service_starting", { port: PORT });
});
