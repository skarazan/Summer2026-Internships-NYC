"""Core Playwright apply loop: connect to Chrome via CDP and apply to listings."""

import asyncio
import logging
import socket
from typing import Any

from auto_apply.config import (
    BETWEEN_APPS_DELAY,
    CDP_PORT,
    CHROME_PATH,
    USER_DATA_DIR,
)
from auto_apply.simplify_flow import apply_via_simplify
from auto_apply.state import (
    load_applied_state,
    load_pending,
    mark_applied,
    mark_failed,
    save_applied_state,
)

logger = logging.getLogger("auto_apply.applier")


def _cdp_available() -> bool:
    """Check if Chrome is running with --remote-debugging-port."""
    try:
        s = socket.create_connection(("localhost", CDP_PORT), timeout=1)
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def _print_chrome_launch_hint() -> None:
    print(
        "\n[ERROR] Chrome is not running with remote debugging enabled.\n"
        "Please close Chrome completely, then run:\n\n"
        f'  "{CHROME_PATH}" \\\n'
        f"    --remote-debugging-port={CDP_PORT} \\\n"
        f'    --user-data-dir="{USER_DATA_DIR}"\n\n'
        "Then re-run: uv run main.py auto-apply run\n"
    )


async def _run(
    listings: list[dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, int]:
    """Internal async apply loop."""
    from playwright.async_api import async_playwright

    results: dict[str, int] = {
        "applied": 0,
        "failed": 0,
        "needs_review": 0,
        "skipped": 0,
    }
    state = load_applied_state()

    # Dry run: no browser needed — just print what would be applied
    if dry_run:
        for listing in listings:
            company = listing.get("company_name", "?")
            title = listing.get("title", "?")
            simplify_url = listing.get("simplify_url") or listing.get("url")
            print(f"  [DRY RUN] {company} — {title}")
            print(f"            {simplify_url}")
            results["skipped"] += 1
        return results

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()

        for listing in listings:
            company = listing.get("company_name", "?")
            title = listing.get("title", "?")

            logger.info(f"Applying: {company} — {title}")
            try:
                if listing.get("simplify_url"):
                    status = await apply_via_simplify(context, listing)
                else:
                    # No Simplify link — open the direct ATS URL for manual review
                    logger.info(f"No Simplify URL, opening directly: {listing['url']}")
                    page = await context.new_page()
                    await page.goto(listing["url"], timeout=30_000)
                    status = "needs_review"

                results[status] = results.get(status, 0) + 1

                if status == "applied":
                    mark_applied(state, listing)
                    print(f"  ✓ Applied: {company} — {title}")
                elif status == "needs_review":
                    mark_failed(state, listing, "needs_review")
                    print(f"  ~ Needs review: {company} — {title}")
                else:
                    mark_failed(state, listing, "application flow failed")
                    print(f"  ✗ Failed: {company} — {title}")

                await asyncio.sleep(BETWEEN_APPS_DELAY)

            except Exception as e:
                logger.error(f"Error applying to {company}: {e}")
                mark_failed(state, listing, str(e))
                results["failed"] = results.get("failed", 0) + 1
                print(f"  ✗ Error: {company} — {e}")

    from datetime import datetime
    state["stats"]["last_run"] = int(datetime.now().timestamp())
    save_applied_state(state)

    return results


def cmd_run(
    dry_run: bool = False,
    limit: int = 10,
    listing_id: str | None = None,
) -> None:
    """Apply to pending listings using the user's real Chrome + Simplify extension."""
    if not dry_run and not _cdp_available():
        _print_chrome_launch_hint()
        return

    pending = load_pending()

    if not pending:
        print("No pending applications. Run 'git pull' first to get the latest listings.")
        return

    if listing_id:
        pending = [p for p in pending if p["listing_id"] == listing_id]
        if not pending:
            print(f"No pending listing found with ID: {listing_id}")
            return

    pending = pending[:limit]
    print(f"{'[DRY RUN] ' if dry_run else ''}Applying to {len(pending)} listing(s)...\n")

    results = asyncio.run(_run(pending, dry_run=dry_run))

    print(f"\nResults: {results}")


def cmd_retry(limit: int = 5) -> None:
    """Retry failed listings (those with status='failed', attempts < MAX_RETRIES)."""
    from auto_apply.config import MAX_RETRIES

    state = load_applied_state()
    retryable = [
        {
            "listing_id": e["listing_id"],
            "company_name": e["company_name"],
            "title": e["title"],
            "url": e["url"],
            "simplify_url": e["simplify_url"],
        }
        for e in state.get("applied", [])
        if e.get("status") == "failed" and e.get("attempts", 0) < MAX_RETRIES
    ]

    if not retryable:
        print("No retryable failed listings.")
        return

    retryable = retryable[:limit]
    print(f"Retrying {len(retryable)} listing(s)...\n")

    if not _cdp_available():
        _print_chrome_launch_hint()
        return

    results = asyncio.run(_run(retryable))
    print(f"\nRetry results: {results}")
