import type { NextConfig } from "next";

const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Server-side proxy: the browser calls `/api/backend/*` and the Next.js
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
};

export default nextConfig;
