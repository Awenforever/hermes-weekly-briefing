"""Weekly Briefing v4 plugin registration."""

from __future__ import annotations

from .plugin_cli import register_cli, weekly_briefing_command


def register(ctx) -> None:
    ctx.register_cli_command(
        name="weekly-briefing",
        help="Generate and inspect the email-only academic weekly report",
        setup_fn=register_cli,
        handler_fn=weekly_briefing_command,
        description="Academic report generation with PDF and email-only delivery.",
    )
