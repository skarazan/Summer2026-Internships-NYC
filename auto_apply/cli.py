"""CLI commands for the auto-apply system."""

from datetime import datetime

import typer

from auto_apply.applier import cmd_retry, cmd_run
from auto_apply.detector import cmd_detect
from auto_apply.state import load_applied_state, load_pending, mark_skipped, save_applied_state

apply_app = typer.Typer(help="Auto-apply to NYC internships via Simplify Copilot")


@apply_app.command("detect")
def detect(
    limit: int | None = typer.Option(None, "--limit", help="Only include N most recent listings (safety for first run)"),
) -> None:
    """Detect new NYC listings and write them to pending_applications.json.

    Run automatically by GitHub Actions after each sync.
    Use --limit 50 on first run to avoid applying to all old listings.
    """
    cmd_detect(limit_recent=limit)


@apply_app.command("run")
def run(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without applying"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max applications per run"),
    listing_id: str | None = typer.Option(None, "--id", help="Apply to one specific listing ID"),
) -> None:
    """Apply to pending NYC listings using your Chrome + Simplify Copilot extension.

    Chrome must be running with --remote-debugging-port=9222.
    Run 'git pull' first to get the latest pending_applications.json.
    """
    cmd_run(dry_run=dry_run, limit=limit, listing_id=listing_id)


@apply_app.command("status")
def status() -> None:
    """Show auto-apply statistics and pending/applied counts."""
    state = load_applied_state()
    pending = load_pending()
    entries = state.get("applied", [])
    stats = state.get("stats", {})

    applied = [e for e in entries if e.get("status") == "applied"]
    failed = [e for e in entries if e.get("status") == "failed"]
    skipped = [e for e in entries if e.get("status") == "skipped"]
    needs_review = [e for e in entries if e.get("status") == "needs_review"]

    last_run = stats.get("last_run", 0)
    last_run_str = datetime.fromtimestamp(last_run).strftime("%Y-%m-%d %H:%M") if last_run else "never"

    print(f"\n{'─' * 40}")
    print(f"  Auto-Apply Status")
    print(f"{'─' * 40}")
    print(f"  Pending:      {len(pending)}")
    print(f"  Applied:      {len(applied)}")
    print(f"  Failed:       {len(failed)}")
    print(f"  Needs review: {len(needs_review)}")
    print(f"  Skipped:      {len(skipped)}")
    print(f"  Last run:     {last_run_str}")
    print(f"{'─' * 40}\n")

    if pending:
        print("Pending applications:")
        for p in pending[:10]:
            simplify = "✓" if p.get("simplify_url") else "✗"
            print(f"  [{simplify}] {p['company_name']} — {p['title']}")
        if len(pending) > 10:
            print(f"  ... and {len(pending) - 10} more")
        print()

    if failed:
        print("Failed (will retry):")
        for e in failed[:5]:
            print(f"  {e['company_name']} — {e['title']} (attempts: {e.get('attempts', 0)})")
        print()


@apply_app.command("retry")
def retry(
    limit: int = typer.Option(5, "--limit", "-n", help="Max retries per run"),
) -> None:
    """Retry listings that previously failed."""
    cmd_retry(limit=limit)


@apply_app.command("skip")
def skip(
    listing_id: str = typer.Argument(..., help="Listing ID to mark as skipped"),
) -> None:
    """Manually skip a listing (won't be retried or applied to)."""
    state = load_applied_state()
    mark_skipped(state, listing_id)
    save_applied_state(state)
    print(f"Skipped listing: {listing_id}")
