import path from "node:path";
import { defineConfig } from "vitest/config";

// Unit-test config for pure frontend logic (realtime SSE parsing, retry
// backoff). Component tests stay out of scope for Phase 9; the lint +
// tsc + build gates cover the rest.
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname),
    },
  },
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts", "features/**/*.test.ts"],
  },
});
