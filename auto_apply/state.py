"""State management: load/save applied.json and pending_applications.json."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from auto_apply.config import APPLIED_PATH, PENDING_PATH, MAX_RETRIES

type Listing = dict[str, Any]

_EMPTY_STATE: dict[str, Any] = {
    "applied": [],
    "stats": {
        "total_applied": 0,
        "total_failed": 0,
        "total_skipped": 0,
        "last_run": 0,
    },
}


def load_applied_state() -> dict[str, Any]:
    """Load the applied.json state file. Returns empty state if file doesn't exist."""
    path = Path(APPLIED_PATH)
    if not path.exists():
        return json.loads(json.dumps(_EMPTY_STATE))
    with open(path) as f:
        return json.load(f)


def save_applied_state(state: dict[str, Any]) -> None:
    """Write state back to applied.json."""
    Path(APPLIED_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(APPLIED_PATH, "w") as f:
        json.dump(state, f, indent=2)


def load_pending() -> list[dict[str, Any]]:
    """Load pending_applications.json. Returns empty list if file doesn't exist."""
    path = Path(PENDING_PATH)
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("pending", [])


def get_applied_ids(state: dict[str, Any]) -> set[str]:
    """Return IDs of all listings that are applied, skipped, or needs_review."""
    terminal_statuses = {"applied", "skipped"}
    return {
        entry["listing_id"]
        for entry in state.get("applied", [])
        if entry.get("status") in terminal_statuses
    }


def _find_or_create_entry(state: dict[str, Any], listing: dict[str, Any]) -> dict[str, Any]:
    """Find existing entry for this listing or create a new one."""
    for entry in state["applied"]:
        if entry["listing_id"] == listing["listing_id"]:
            return entry
    entry: dict[str, Any] = {
        "listing_id": listing["listing_id"],
        "company_name": listing.get("company_name", ""),
        "title": listing.get("title", ""),
        "url": listing.get("url", ""),
        "simplify_url": listing.get("simplify_url"),
        "applied_at": None,
        "status": "pending",
        "attempts": 0,
        "last_error": None,
    }
    state["applied"].append(entry)
    return entry


def mark_applied(state: dict[str, Any], listing: dict[str, Any]) -> None:
    """Mark a listing as successfully applied."""
    entry = _find_or_create_entry(state, listing)
    entry["status"] = "applied"
    entry["applied_at"] = int(datetime.now().timestamp())
    entry["attempts"] = entry.get("attempts", 0) + 1
    entry["last_error"] = None
    state["stats"]["total_applied"] = state["stats"].get("total_applied", 0) + 1


def mark_failed(state: dict[str, Any], listing: dict[str, Any], error: str) -> None:
    """Increment attempt count. Auto-skip after MAX_RETRIES failures."""
    entry = _find_or_create_entry(state, listing)
    entry["attempts"] = entry.get("attempts", 0) + 1
    entry["last_error"] = error

    if entry["attempts"] >= MAX_RETRIES:
        entry["status"] = "skipped"
        state["stats"]["total_skipped"] = state["stats"].get("total_skipped", 0) + 1
    else:
        entry["status"] = "failed"
        state["stats"]["total_failed"] = state["stats"].get("total_failed", 0) + 1


def mark_skipped(state: dict[str, Any], listing_id: str) -> None:
    """Manually skip a listing by ID."""
    for entry in state["applied"]:
        if entry["listing_id"] == listing_id:
            entry["status"] = "skipped"
            return
    state["applied"].append({
        "listing_id": listing_id,
        "company_name": "",
        "title": "",
        "url": "",
        "simplify_url": None,
        "applied_at": None,
        "status": "skipped",
        "attempts": 0,
        "last_error": "manually skipped",
    })
