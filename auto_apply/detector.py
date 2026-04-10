"""Detect new NYC internship listings by diffing old vs new listings.json."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from list_updater.listings import filter_active, filter_nyc, filter_summer, get_listings_from_json
from auto_apply.config import (
    APPLIED_PATH,
    LISTINGS_PATH,
    OLD_LISTINGS_PATH,
    PENDING_PATH,
    SUMMER_2026_EARLIEST_DATE,
)
from auto_apply.state import get_applied_ids, load_applied_state


def detect_new_listings(limit_recent: int | None = None, category: str | None = None) -> list[dict[str, Any]]:
    """Find active NYC Summer 2026 listings not previously seen or already applied to.

    Args:
        limit_recent: If set, only include the N most recently posted listings (safety for first run).
                     Example: limit_recent=50 will only include 50 newest listings.
                     Recommended for first run to avoid applying to old listings.
        category: If set, only include listings matching this category (case-insensitive).
                 Example: category="Software" will match "Software Engineering", "Software", etc.

    Returns:
        List of new listing dicts ready to be written to pending_applications.json.
    """
    # Load current listings
    listings = get_listings_from_json(LISTINGS_PATH)

    # Get IDs from the previous sync (saved before the curl overwrote listings.json)
    old_ids: set[str] = set()
    old_path = Path(OLD_LISTINGS_PATH)
    if old_path.exists():
        with open(old_path) as f:
            old_listings = json.load(f)
        old_ids = {l["id"] for l in old_listings}
        print(f"Loaded {len(old_ids)} IDs from previous listings snapshot")
    else:
        print("No previous listings snapshot found — treating all active NYC listings as new")

    # Apply the same pipeline the README uses
    filtered = filter_summer(listings, "2026", SUMMER_2026_EARLIEST_DATE)
    filtered = filter_nyc(filtered)
    filtered = filter_active(filtered)
    print(f"Active NYC Summer 2026 listings: {len(filtered)}")

    # Filter by category if requested
    if category:
        category_lower = category.lower()
        filtered = [l for l in filtered if category_lower in l.get("category", "").lower()]
        print(f"Filtered to {category} category: {len(filtered)}")

    # Diff: keep only listings not seen before
    new_only = [l for l in filtered if l["id"] not in old_ids]
    print(f"New listings since last sync: {len(new_only)}")

    # Limit to most recent if requested (first run protection)
    if limit_recent is not None:
        # Sort by date_posted descending (newest first)
        new_only_sorted = sorted(new_only, key=lambda x: x.get("date_posted", 0), reverse=True)
        limited = new_only_sorted[:limit_recent]
        print(f"Limited to {limit_recent} most recent listings: {len(limited)} (filtered from {len(new_only)})")
        new_only = limited

    # Exclude already-applied/skipped listings
    state = load_applied_state()
    applied_ids = get_applied_ids(state)
    pending = [l for l in new_only if l["id"] not in applied_ids]
    print(f"Pending (not yet applied): {len(pending)}")

    return pending


def build_pending_record(listing: dict[str, Any]) -> dict[str, Any]:
    """Convert a listing dict into a pending application record."""
    simplify_url = None
    if listing.get("source") == "Simplify":
        simplify_url = f"https://simplify.jobs/p/{listing['id']}"

    return {
        "listing_id": listing["id"],
        "company_name": listing["company_name"],
        "title": listing["title"],
        "url": listing["url"],
        "simplify_url": simplify_url,
        "locations": listing.get("locations", []),
        "source": listing.get("source", ""),
        "category": listing.get("category", ""),
        "date_detected": int(datetime.now().timestamp()),
    }


def write_pending(pending: list[dict[str, Any]]) -> None:
    """Write the pending application records to pending_applications.json."""
    records = [build_pending_record(l) for l in pending]
    Path(PENDING_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_PATH, "w") as f:
        json.dump({"pending": records}, f, indent=2)
    print(f"Wrote {len(records)} pending applications to {PENDING_PATH}")


def cmd_detect(limit_recent: int | None = None, category: str | None = None) -> None:
    """Detect new NYC listings and write them to pending_applications.json.

    Args:
        limit_recent: If set, only include the N most recent listings (safety for first run).
        category: If set, only include listings matching this category.
    """
    pending = detect_new_listings(limit_recent=limit_recent, category=category)
    write_pending(pending)
