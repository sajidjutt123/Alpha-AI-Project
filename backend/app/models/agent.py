"""Agent model — organization team member.

Authentication credentials live in Supabase Auth; `auth_user_id` links the
auth user to this row. No passwords are ever stored in this table.
"""

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UuidPkMixin
from app.models.enums import AgentRole


class Agent(UuidPkMixin, CreatedAtMixin, Base):
    __tablename__ = "agents"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String)
    role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, name="agent_role", create_type=False, native_enum=True),
        default=AgentRole.AGENT,
        nullable=False,
    )
    auth_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"Agent(id={self.id!r}, email={self.email!r}, role={self.role!r})"
