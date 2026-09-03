# Frontend image — production (multi-stage, standalone output).
#
# Build from `frontend/` (context = this directory):
#   docker build -t alpha-ai-frontend .
#   docker run -p 3000:3000 \
#     -e BACKEND_INTERNAL_URL=http://api.example.internal:8000 \
#     alpha-ai-frontend
#
# BACKEND_INTERNAL_URL is read by the standalone server at boot (see
# next.config.ts rewrites) — the same image targets any backend.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runtime
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S nextjs && adduser -S nextjs -G nextjs
WORKDIR /app
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
