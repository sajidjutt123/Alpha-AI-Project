"""Python enums mirroring the PostgreSQL enum types (database/migrations/001).

Member values are identical to the SQL labels (uppercase) so SQLAlchemy
persisted values match the database exactly. Do not rename members' values
without a migration.
"""

import enum


class LeadStatus(enum.StrEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    CONVERTED = "CONVERTED"
    LOST = "LOST"


class LeadIntent(enum.StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    RENT = "RENT"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"
    HUMAN_AGENT = "HUMAN_AGENT"
    UNKNOWN = "UNKNOWN"


class SenderType(enum.StrEnum):
    CUSTOMER = "CUSTOMER"
    AI = "AI"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class MessageChannel(enum.StrEnum):
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    DASHBOARD = "DASHBOARD"


class PropertyType(enum.StrEnum):
    HOUSE = "HOUSE"
    APARTMENT = "APARTMENT"
    PLOT = "PLOT"
    COMMERCIAL = "COMMERCIAL"


class PropertyAvailability(enum.StrEnum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    RENTED = "RENTED"


class AgentRole(enum.StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    AGENT = "AGENT"
