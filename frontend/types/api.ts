/**
 * Shared API types — mirror of backend Pydantic schemas (`app/schemas/`).
 * Keep both sides in sync; domain types (Lead, Property, …) land with Phase 3.
 */

export type HealthStatus = "ok";

export interface HealthResponse {
  status: HealthStatus;
  version: string;
  environment: string;
  timestamp: string;
}
