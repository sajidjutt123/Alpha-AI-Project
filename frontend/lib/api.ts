/**
 * Typed client for the Alpha AI backend.
 *
 * The browser only ever calls relative paths (`/api/backend/...`); the
 * Next.js server rewrites them to the FastAPI service (see `next.config.ts`),
 * so the backend URL never leaks to the client and CORS stays closed.
 * Authenticated calls attach the session bearer token (features/auth).
 */

import type {
  Agent,
  AgentMessage,
  AnalyticsOverview,
  HealthResponse,
  Lead,
  LeadDetail,
  LeadUpdate,
  Page,
  Property,
  Session,
} from "@/types/api";

const BASE_PATH = "/api/backend";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let tokenProvider: () => string | null = () => null;

/** Wire the session token source (called once by the SessionProvider). */
export function setTokenProvider(provider: () => string | null) {
  tokenProvider = provider;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  if (init?.body) headers["Content-Type"] = "application/json";

  const token = tokenProvider();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${BASE_PATH}${path}`, { ...init, headers });
  if (!response.ok) {
    let code = `http_${response.status}`;
    let message = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      // non-JSON error body — keep defaults
    }
    throw new ApiError(response.status, code, message);
  }
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

// --- System ------------------------------------------------------------------

export const healthApi = {
  check: () => apiFetch<HealthResponse>("/health"),
};

// --- Auth -------------------------------------------------------------------

export const authApi = {
  devLogin: (email: string) =>
    apiFetch<Session>("/auth/dev-login", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
};

// --- Agents ------------------------------------------------------------------

export const agentsApi = {
  me: () => apiFetch<Session["agent"]>("/agents/me"),
  list: () => apiFetch<Agent[]>("/agents"),
};

// --- Leads ---------------------------------------------------------------------

export const leadsApi = {
  list: (params: {
    status?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }) => apiFetch<Page<Lead>>(`/leads${query(params)}`),

  get: (id: string) => apiFetch<LeadDetail>(`/leads/${id}`),

  update: (id: string, patch: LeadUpdate) =>
    apiFetch<Lead>(`/leads/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),

  sendMessage: (id: string, content: string) =>
    apiFetch<AgentMessage>(`/leads/${id}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
};

// --- Properties --------------------------------------------------------------------

export const propertiesApi = {
  list: (params: {
    property_type?: string;
    location?: string;
    price_min?: number;
    price_max?: number;
    bedrooms_min?: number;
    limit?: number;
    offset?: number;
  }) => apiFetch<Page<Property>>(`/properties${query(params)}`),
};

// --- Analytics ------------------------------------------------------------------------

export const analyticsApi = {
  overview: () => apiFetch<AnalyticsOverview>("/analytics/overview"),
};
