"""First-run provisioning for a fresh production deployment.

Creates the first organization and its OWNER agent, linked to a Supabase
Auth user. Run once after migrations, from an environment carrying the
runtime `DATABASE_URL` (the RLS-bound `alpha_app` role):

    python -m app.db.bootstrap_org \
        --name "Alpha Estates" \
        --slug alpha-estates \
        --owner-name "Ahmed Raza" \
        --owner-email ahmed@example.com \
        --auth-user-id 00000000-0000-0000-0000-000000000000 \
        [--twilio-whatsapp-from whatsapp:+14155238886]

The `--auth-user-id` is the Supabase Auth user's `uid` (auth.users) — the
dashboard signs in through Supabase Auth and the API resolves the token's
`sub` claim to this agent.

Uniqueness is enforced by the database (slug, auth user id and Twilio
numbers have global unique constraints; agent email is unique per org — RLS cannot see other tenants' rows, so those
constraints are the source of truth). A violation exits with a clear
message instead of a traceback; nothing is written (single transaction).
"""

import argparse
import asyncio
import sys
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import with_tenant
from app.models import Agent, Organization
from app.models.enums import AgentRole
from app.repositories import AgentRepository, OrganizationRepository


async def bootstrap(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    owner_name: str,
    owner_email: str,
    auth_user_id: UUID,
    twilio_whatsapp_from: str | None,
) -> Organization:
    """Create org + OWNER agent inside one tenant-bound transaction."""
    organization_id = uuid4()
    try:
        async with with_tenant(session, organization_id):
            organization = await OrganizationRepository(session).create(
                name=name,
                slug=slug,
                organization_id=organization_id,
                twilio_whatsapp_from=twilio_whatsapp_from,
            )
            owner = await AgentRepository(session).add(
                Agent(
                    organization_id=organization_id,
                    name=owner_name,
                    email=owner_email,
                    role=AgentRole.OWNER,
                    auth_user_id=auth_user_id,
                )
            )
            # with_tenant commits on exit
    except IntegrityError as exc:
        diag = getattr(getattr(exc, "orig", None), "diag", None)
        constraint = getattr(diag, "constraint_name", None) or "unique constraint"
        raise SystemExit(
            f"error: uniqueness violated ({constraint}) — "
            "slug / owner email / Twilio number already used; nothing was written"
        ) from exc
    print("organization created:")
    print(f"  id            = {organization.id}")
    print(f"  name          = {organization.name}")
    print(f"  slug          = {organization.slug}")
    print(f"  owner agent   = {owner.name} <{owner.email}> ({owner.role.value})")
    print(f"  auth_user_id  = {owner.auth_user_id}")
    print("next: sign in through Supabase Auth with that user and open the dashboard.")
    return organization


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="Organization display name")
    parser.add_argument("--slug", required=True, help="Unique slug (routing fallback)")
    parser.add_argument("--owner-name", required=True)
    parser.add_argument("--owner-email", required=True)
    parser.add_argument(
        "--auth-user-id",
        required=True,
        type=UUID,
        help="Supabase Auth user uid — must match the JWT `sub` the dashboard sends",
    )
    parser.add_argument("--twilio-whatsapp-from", default=None)
    args = parser.parse_args(argv)

    from app.core.config import get_settings

    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        asyncio.run(
            bootstrap(
                async_sessionmaker(engine, expire_on_commit=False)(),
                name=args.name,
                slug=args.slug,
                owner_name=args.owner_name,
                owner_email=args.owner_email.lower(),
                auth_user_id=args.auth_user_id,
                twilio_whatsapp_from=args.twilio_whatsapp_from,
            )
        )
    finally:
        # asyncio.run closed the session; the engine still needs disposing.
        asyncio.run(engine.dispose())
    return 0


if __name__ == "__main__":
    sys.exit(main())
