# syntax=docker/dockerfile:1.6
# ──────────── Stage 1: Build ────────────
FROM node:20-alpine AS build
WORKDIR /app

COPY services/member/package.json services/member/package-lock.json* ./
RUN npm ci --only=production --ignore-scripts 2>/dev/null || npm install --production --ignore-scripts

# ──────────── Stage 2: Runtime ────────────
FROM node:20-alpine AS runtime

# Create non-root user
RUN addgroup -S appuser && adduser -S -G appuser -h /app appuser

# Copy production dependencies from build stage
COPY --from=build /app/node_modules /app/node_modules

# Copy application code
COPY services/member/src/ /app/src/
COPY services/member/package.json /app/

# Set ownership
RUN chown -R appuser:appuser /app

# Drop to non-root
USER appuser
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/healthz || exit 1

CMD ["node", "src/index.js"]
