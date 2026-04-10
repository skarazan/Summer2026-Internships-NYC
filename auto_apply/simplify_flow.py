"""Simplify Copilot flow: navigate Simplify page, trigger extension autofill, submit."""

import asyncio
import logging
from typing import Any

from playwright.async_api import BrowserContext, ElementHandle, Page, TimeoutError as PWTimeout

from auto_apply.config import (
    CAPTCHA_SELECTORS,
    EXTENSION_SELECTORS,
    EXTENSION_WAIT_TIMEOUT,
    NEW_TAB_TIMEOUT,
    PAGE_LOAD_TIMEOUT,
    SIMPLIFY_APPLY_ANYWAY_BTN,
    SIMPLIFY_APPLY_BTN,
    SIMPLIFY_MODAL_DETECT,
    SUCCESS_TEXT_PATTERNS,
    SUCCESS_URL_PATTERNS,
)

logger = logging.getLogger("auto_apply.simplify")


async def apply_via_simplify(context: BrowserContext, listing: dict[str, Any]) -> str:
    """Full Simplify flow for one listing.

    Args:
        context: The Playwright browser context (from CDP connection).
        listing:  A pending application record with at least 'simplify_url'.

    Returns:
        Status string: 'applied' | 'failed' | 'needs_review'
    """
    simplify_url = listing.get("simplify_url")
    if not simplify_url:
        logger.warning(f"No Simplify URL for {listing['company_name']} — skipping to needs_review")
        return "needs_review"

    page = await context.new_page()
    try:
        # ── Step 1: Load the Simplify job profile page ────────────────────────
        logger.info(f"Opening: {simplify_url}")
        await page.goto(simplify_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        await page.wait_for_timeout(1500)  # let extension detection scripts run

        # ── Step 2: Click the Apply button ───────────────────────────────────
        try:
            await page.click(SIMPLIFY_APPLY_BTN, timeout=10_000)
        except PWTimeout:
            logger.warning(f"Apply button not found on {simplify_url}")
            return "failed"

        await page.wait_for_timeout(1500)

        # ── Step 3: Handle "Download Chrome Extension" modal if present ───────
        #   (appears when extension is not detected by Simplify)
        try:
            await page.wait_for_selector(SIMPLIFY_MODAL_DETECT, timeout=2_000)
            logger.debug("Extension-prompt modal detected — clicking Apply Anyway")
            await page.click(SIMPLIFY_APPLY_ANYWAY_BTN, timeout=5_000)
        except PWTimeout:
            # Modal didn't appear — extension was detected, ATS tab should open directly
            logger.debug("No modal — extension detected by Simplify, ATS opening directly")

        # ── Step 4: Wait for the ATS page to open in a new tab ───────────────
        ats_page = await _wait_for_new_tab(context, timeout=NEW_TAB_TIMEOUT)
        if ats_page is None:
            logger.warning(f"ATS tab never opened for {listing['company_name']}")
            return "failed"

        await ats_page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT)
        logger.info(f"ATS page: {ats_page.url}")

        # ── Step 5: Wait for extension autofill button ────────────────────────
        autofill_btn = await _wait_for_extension(ats_page)
        if autofill_btn is None:
            logger.warning(
                f"Simplify extension UI not detected on {ats_page.url} — "
                "leaving tab open for manual review"
            )
            # Don't close the tab — leave it open so the user can apply manually
            return "needs_review"

        # ── Step 6: Trigger autofill ──────────────────────────────────────────
        logger.info("Clicking Simplify autofill button")
        await autofill_btn.click()
        await ats_page.wait_for_timeout(3000)  # let extension populate fields

        # ── Step 7: Advance through multi-page form and submit ────────────────
        status = await _handle_form_pages(ats_page)
        logger.info(f"{listing['company_name']} — {listing['title']}: {status}")

        if status == "applied":
            await ats_page.close()

        return status

    except Exception as e:
        logger.error(f"Unexpected error for {listing['company_name']}: {e}")
        return "failed"
    finally:
        # Always close the Simplify profile tab
        try:
            await page.close()
        except Exception:
            pass


async def _wait_for_new_tab(context: BrowserContext, timeout: int) -> Page | None:
    """Wait up to `timeout` ms for a new page to appear in the context."""
    try:
        async with context.expect_page(timeout=timeout) as page_info:
            pass
        new_page = await page_info.value
        return new_page
    except PWTimeout:
        return None


async def _wait_for_extension(page: Page) -> ElementHandle | None:
    """Try each EXTENSION_SELECTORS until one becomes visible."""
    for selector in EXTENSION_SELECTORS:
        try:
            el = await page.wait_for_selector(selector, timeout=EXTENSION_WAIT_TIMEOUT)
            if el and await el.is_visible():
                logger.debug(f"Extension found with selector: {selector}")
                return el
        except PWTimeout:
            continue
        except Exception:
            continue
    return None


async def _handle_form_pages(page: Page, max_pages: int = 12) -> str:
    """Loop through form pages: autofill each, click Next, finally Submit."""
    for page_num in range(max_pages):
        logger.debug(f"Form page {page_num + 1}, URL: {page.url}")

        # CAPTCHA check
        if await _detect_captcha(page):
            logger.warning("CAPTCHA detected — needs manual review")
            return "needs_review"

        # Check for Submit button first
        submit = await _find_visible(page, [
            "button:has-text('Submit Application')",
            "button:has-text('Submit')",
            "input[type='submit']",
        ])
        if submit:
            logger.info("Clicking Submit")
            await submit.click()
            await asyncio.sleep(3)
            return "applied" if await _detect_success(page) else "needs_review"

        # Try to advance to next page
        nxt = await _find_visible(page, [
            "button:has-text('Next')",
            "button:has-text('Continue')",
            "button:has-text('Next Step')",
            "button[type='submit']:not(:has-text('Submit'))",
        ])
        if nxt:
            await nxt.click()
            await page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT)
            await page.wait_for_timeout(1500)

            # Re-trigger autofill on the new page if extension button reappears
            autofill = await _wait_for_extension(page)
            if autofill:
                await autofill.click()
                await page.wait_for_timeout(2000)
        else:
            logger.warning("No Next or Submit button found")
            break

    return "needs_review"


async def _find_visible(page: Page, selectors: list[str]) -> ElementHandle | None:
    """Return the first visible element matching any of the given selectors."""
    for selector in selectors:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                return el
        except Exception:
            continue
    return None


async def _detect_captcha(page: Page) -> bool:
    """Return True if a CAPTCHA challenge is visible on the page."""
    for selector in CAPTCHA_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el:
                return True
        except Exception:
            continue
    return False


async def _detect_success(page: Page) -> bool:
    """Return True if the page indicates a successful submission."""
    current_url = page.url.lower()
    if any(pattern in current_url for pattern in SUCCESS_URL_PATTERNS):
        return True
    try:
        content = (await page.content()).lower()
        if any(pattern in content for pattern in SUCCESS_TEXT_PATTERNS):
            return True
    except Exception:
        pass
    return False
