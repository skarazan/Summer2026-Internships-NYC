"""Configuration constants for the auto-apply system."""

from pathlib import Path

# Chrome / CDP configuration
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CDP_PORT = 9222
USER_DATA_DIR = str(Path.home() / "Library/Application Support/Google/Chrome")

# File paths (relative to repo root)
APPLIED_PATH = ".github/scripts/applied.json"
PENDING_PATH = ".github/scripts/pending_applications.json"
LISTINGS_PATH = ".github/scripts/listings.json"
OLD_LISTINGS_PATH = ".github/scripts/listings_old.json"

# Filter constants (must match commands.py)
SUMMER_2026_EARLIEST_DATE = 1748761200

# Timeouts in milliseconds
PAGE_LOAD_TIMEOUT = 30_000
EXTENSION_WAIT_TIMEOUT = 15_000
NEW_TAB_TIMEOUT = 15_000

# Delays in seconds
BETWEEN_APPS_DELAY = 5

# Retry limit per listing before auto-skip
MAX_RETRIES = 3

# ── Simplify page selectors (confirmed via live browser inspection) ──────────
# On simplify.jobs/p/{id}
SIMPLIFY_APPLY_BTN = "button:has-text('Apply')"
SIMPLIFY_APPLY_ANYWAY_BTN = "button:has-text('Apply Anyway')"
SIMPLIFY_MODAL_DETECT = "text=Download Chrome Extension"

# ── Simplify Copilot extension selectors ─────────────────────────────────────
# The extension injects a floating autofill button into the ATS page.
# These are tried in order — update once confirmed on first real run.
EXTENSION_SELECTORS = [
    "[data-simplify-autofill]",
    "#simplify-copilot",
    "#simplify-copilot-root",
    ".simplify-autofill-btn",
    "[class*='simplify'][class*='autofill']",
    "button:has-text('Autofill')",
    "button:has-text('Fill with Simplify')",
    "button:has-text('Simplify')",
]

# ── Submission success indicators (URL or page text patterns) ─────────────────
SUCCESS_URL_PATTERNS = [
    "confirmation",
    "success",
    "submitted",
    "thank-you",
    "thankyou",
]
SUCCESS_TEXT_PATTERNS = [
    "application submitted",
    "application received",
    "thank you for applying",
    "successfully submitted",
    "we've received your application",
]

# ── CAPTCHA detection selectors ───────────────────────────────────────────────
CAPTCHA_SELECTORS = [
    'iframe[src*="recaptcha"]',
    'iframe[src*="hcaptcha"]',
    ".g-recaptcha",
    "#captcha",
    "[data-captcha]",
    'iframe[title*="captcha"]',
]
