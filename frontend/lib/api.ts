/**
 * Typed client for the Alpha AI backend.
 *
 * The browser only ever calls relative paths (`/api/backend/...`); the
 * Next.js server rewrites them to the FastAPI service (see `next.config.ts`),
 * so the backend URL never leaks to the client and CORS stays closed.
 */

const BASE_PATH = "/api/backend";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_PATH}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}
