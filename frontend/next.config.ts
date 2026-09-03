import type { NextConfig } from "next";

const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

// OWASP baseline headers for the dashboard (Phase 9). The CSP is applied to
// production builds only — Next's dev server (HMR/Turbopack) needs eval and
// inline scripts, so a strict CSP there would break the developer loop.
const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];
const PRODUCTION_CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "connect-src 'self'",
  "font-src 'self' data:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

const nextConfig: NextConfig = {
  // Server-side proxy: the browser calls `/api/backend/...` and the Next.js
  // server forwards to FastAPI. Keeps the backend URL off the client and
  // avoids CORS entirely (see `lib/api.ts`).
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${BACKEND_INTERNAL_URL}/api/v1/:path*`,
      },
    ];
  },
  async headers() {
    const headers = SECURITY_HEADERS.map(({ key, value }) => ({
      key,
      value,
    }));
    if (process.env.NODE_ENV === "production") {
      headers.push({ key: "Content-Security-Policy", value: PRODUCTION_CSP });
    }
    return [{ source: "/:path*", headers }];
  },
};

export default nextConfig;
