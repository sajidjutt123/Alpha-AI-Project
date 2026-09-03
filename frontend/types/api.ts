/**
 * Shared API types — mirror of backend Pydantic schemas (`app/schemas/`).
 * Keep both sides in sync.
 */

export type HealthStatus = "ok";

export interface HealthResponse {
  status: HealthStatus;
  version: string;
  environment: string;
  timestamp: string;
}

// --- Enums (uppercase strings, mirror database enums) -----------------------

export type LeadStatus =
  | "NEW"
  | "CONTACTED"
  | "QUALIFIED"
  | "CONVERTED"
  | "LOST";
export type LeadIntent =
  | "BUY"
  | "SELL"
  | "RENT"
  | "GENERAL_INQUIRY"
  | "HUMAN_AGENT"
  | "UNKNOWN";
export type PropertyType = "HOUSE" | "APARTMENT" | "PLOT" | "COMMERCIAL";
export type PropertyAvailability = "AVAILABLE" | "RESERVED" | "SOLD" | "RENTED";
export type SenderType = "CUSTOMER" | "AI" | "AGENT" | "SYSTEM";
export type MessageChannel = "WHATSAPP" | "SMS" | "DASHBOARD";
export type AgentRole = "OWNER" | "ADMIN" | "AGENT";

// --- Pagination ---------------------------------------------------------------

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// --- Agents / auth --------------------------------------------------------------

export interface Agent {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  role: AgentRole;
  is_active: boolean;
  created_at: string;
}

export interface Me extends Agent {
  organization_id: string;
}

export interface Session {
  token: string;
  agent: Me;
}

// --- Leads ------------------------------------------------------------------------

export interface Lead {
  id: string;
  name: string | null;
  phone: string;
  email: string | null;
  status: LeadStatus;
  intent: LeadIntent | null;
  budget_min: number | null;
  budget_max: number | null;
  preferred_location: string | null;
  property_type: PropertyType | null;
  bedrooms: number | null;
  urgency_score: number | null;
  qualification_score: number | null;
  summary: string | null;
  assigned_agent_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface TranscriptMessage {
  id: string;
  sender_type: SenderType;
  content: string;
  channel: MessageChannel;
  created_at: string;
}

export interface MatchedProperty {
  property_id: string;
  title: string;
  price: number;
  location: string;
  property_type: PropertyType;
  bedrooms: number | null;
  match_score: number;
  reason: string | null;
}

export interface LeadDetail extends Lead {
  messages: TranscriptMessage[];
  matched_properties: MatchedProperty[];
}

export interface LeadUpdate {
  name?: string | null;
  email?: string | null;
  status?: LeadStatus;
  intent?: LeadIntent | null;
  budget_min?: number | null;
  budget_max?: number | null;
  preferred_location?: string | null;
  property_type?: PropertyType | null;
  bedrooms?: number | null;
  summary?: string | null;
  assigned_agent_id?: string | null;
}

// --- Properties ----------------------------------------------------------------------

export interface Property {
  id: string;
  title: string;
  description: string | null;
  price: number;
  location: string;
  property_type: PropertyType;
  bedrooms: number | null;
  bathrooms: number | null;
  area: number | null;
  availability: PropertyAvailability;
  image_url: string | null;
  created_at: string;
}

// --- Analytics ------------------------------------------------------------------------

export interface AnalyticsOverview {
  total_leads: number;
  by_status: Record<LeadStatus, number>;
  hot_leads: number;
  warm_leads: number;
  cold_leads: number;
  conversion_rate: number;
  avg_qualification_score: number | null;
  new_leads_7d: number;
  total_properties: number;
}

// --- Messages ---------------------------------------------------------------------------

export interface AgentMessage {
  id: string;
  lead_id: string;
  sender_type: SenderType;
  content: string;
  channel: MessageChannel;
  external_message_id: string | null;
  created_at: string;
}

// --- Notifications (Phase 8 realtime) ---------------------------------------------------

export type NotificationType = "NEW_LEAD" | "HOT_LEAD" | "HANDOFF";

export interface NotificationItem {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  lead_id: string | null;
  /** Computed per agent server-side (read_by array membership). */
  read: boolean;
  created_at: string;
}

export interface NotificationList {
  items: NotificationItem[];
  unread_count: number;
}

export interface MarkReadResponse {
  marked: number;
}
