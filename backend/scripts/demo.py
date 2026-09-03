"""Alpha AI demo tools — one script, two subcommands (Phase 11).

Run from `backend/` with the project venv:

    # 1) restore the demo database to its curated state
    python scripts/demo.py reset

    # 2) the live "money moment": a new WhatsApp lead arrives while the
    #    dashboard is open (board auto-refresh, toast, unread badge)
    python scripts/demo.py flow

`reset` is idempotent and only touches the demo org (default slug
`alpha-estates`): it removes leads created by ad-hoc webhook tests and
normalizes the board to a full, realistic funnel spread. `flow` posts a
scripted 4-turn customer conversation to the local webhook and narrates
what the audience sees on screen.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

# Allow `python scripts/demo.py` from backend/ (sys.path[0] would be scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Test leads created by manual webhook runs / demo flows (never part of the
# curated seed board).
TEST_LEAD_PHONES = [
    "+923339988776",
    "+923339988777",
    "+923331112223",
    "+923345550199",  # `demo.py flow` default number — reset removes it
]

# Canonical demo board: phone -> (status, note). The seed data carries the
# full story; this normalizes statuses so every Kanban column is populated.
BOARD_STATE = {
    "+923457776688": ("NEW", "fresh inbound, AI has not qualified yet"),
    "+923001234567": ("CONTACTED", "Ali Hassan — HOT 82, the star lead"),
    "+923331112222": ("CONTACTED", "Urgent Buyer — 76, warm and accelerating"),
    "+923221234567": ("CONTACTED", "Match Demo — 80 with property matches"),
    "+923217654321": ("QUALIFIED", "Sara Ahmed — 61, mid-funnel"),
    "+923451112233": ("CONVERTED", "Ayesha Malik — 91, the success story"),
    "+923339998877": ("LOST", "Bilal Cheema — 45, went cold"),
}

# The scripted live conversation (money moment). Turns arrive ~3s apart so
# the narrator can point at each realtime update.
CONVERSATION = [
    "Salam! I saw your DHA Phase 6 listing. Is it still available?",
    "My budget is around 3.5 crore, cash in hand, no loan needed.",
    "We need to move fast — my father wants to finalize before Eid.",
    "Can your agent call me today? Preferably after Asr.",
]


def _engines():
    from app.core.config import get_settings

    settings = get_settings()
    return settings


async def reset(demo_slug: str) -> int:
    """Prune test leads + normalize the demo board. Returns rows changed."""
    from sqlalchemy.ext.asyncio import create_async_engine

    settings = _engines()
    engine = create_async_engine(settings.database_url)
    changed = 0
    try:
        async with engine.connect() as conn:
            # RLS hides organizations before a tenant GUC exists — use the
            # SECURITY DEFINER lookup the webhook router uses (migration 004).
            org = await conn.execute(
                text("select organization_id from app_org_id_by_slug(:slug)"),
                {"slug": demo_slug},
            )
            org_id = org.scalar_one_or_none()
            if org_id is None:
                print(f"error: demo org '{demo_slug}' not found", file=sys.stderr)
                return 1
            org_id = UUID(str(org_id))
            await conn.execute(
                text("select set_config('app.current_organization_id', :o, false)"),
                {"o": str(org_id)},
            )

            # 1) drop ad-hoc test leads (cascades to messages/matches/ai_runs)
            removed = await conn.execute(
                text("delete from leads where phone = any(:phones)"),
                {"phones": TEST_LEAD_PHONES},
            )
            changed += removed.rowcount or 0
            print(f"pruned {removed.rowcount or 0} test lead(s)")

            # 2) normalize the board so every column has a story
            for phone, (status, note) in BOARD_STATE.items():
                result = await conn.execute(
                    text("update leads set status = :status where phone = :phone"),
                    {"status": status, "phone": phone},
                )
                changed += result.rowcount or 0
                print(
                    f"  {phone} -> {status:9} ({note})"
                    if result.rowcount
                    else f"  {phone} not found (skip)"
                )

            # 3) clean slate for the notification bell demo
            await conn.execute(text("delete from notifications"))
            print("notifications cleared (the flow re-creates the live one)")
            await conn.commit()
    finally:
        await engine.dispose()
    print(f"demo board ready — {changed} row(s) touched")
    return 0


def _post_webhook(base_url: str, to: str, phone: str, turn: int, body: str) -> int:
    form = urllib.parse.urlencode(
        {
            "MessageSid": f"SMdemo{int(time.time())}{turn}",
            "From": f"whatsapp:{phone}",
            "To": to,
            "Body": body,
        }
    ).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1/webhooks/twilio",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


def flow(base_url: str, to: str, phone: str) -> int:
    """Post the scripted conversation; narrate each realtime beat."""
    print("live demo conversation")
    print(f"  webhook : {base_url}/api/v1/webhooks/twilio")
    print(f"  customer: {phone} -> {to}")
    print("  keep the dashboard open — watch the board, toast and bell\n")
    for index, body in enumerate(CONVERSATION, start=1):
        status = _post_webhook(base_url, to, phone, index, body)
        print(f"turn {index}/4 [{status}] {body}")
        if index == 1:
            print("   >> NEW LEAD toast + unread badge + board column NEW (realtime)")
        else:
            print("   >> message bubble appears in the open transcript (SSE)")
        if index < len(CONVERSATION):
            time.sleep(3)
    print(
        "\ndone. with OPENAI_API_KEY configured the AI also replies each turn,"
        "\nand score/matches update live on the lead screen."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_reset = sub.add_parser("reset", help="restore the curated demo board")
    p_reset.add_argument("--slug", default="alpha-estates")

    p_flow = sub.add_parser("flow", help="post the scripted live conversation")
    p_flow.add_argument("--base-url", default="http://localhost:8000")
    p_flow.add_argument("--to", default="whatsapp:+14155238886")
    p_flow.add_argument("--phone", default="+923345550199")

    args = parser.parse_args(argv)
    if args.command == "reset":
        return asyncio.run(reset(args.slug))
    return flow(args.base_url, args.to, args.phone)


if __name__ == "__main__":
    sys.exit(main())
