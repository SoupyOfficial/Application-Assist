"""
helpers.py — Browser-level utilities for handling real-world ATS quirks.

Covers: page readiness detection, iframe handling, login wall / CAPTCHA
detection, shadow DOM traversal, SPA navigation waits, and
dynamic content stabilization.

All functions are stateless and operate on Playwright Page objects.
"""

import sys
import time


# ---------------------------------------------------------------------------
# Page readiness
# ---------------------------------------------------------------------------

def wait_for_page_ready(page, timeout: int = 15_000):
    """
    Wait for a page to be genuinely interactive — not just load-event done.

    Handles SPAs that render after initial load (React hydration, Angular
    bootstrapping, etc.) by waiting for network idle *and* a stable DOM.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        # networkidle may never fire on heavy SPAs; fall back to domcontentloaded
        try:
            page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except Exception:
            pass

    # Extra: wait for the body to have meaningful content (guards against spinners)
    try:
        page.wait_for_function(
            "() => document.body && document.body.innerText.length > 50",
            timeout=timeout,
        )
    except Exception:
        pass


def wait_for_navigation_settle(page, timeout: int = 10_000):
    """
    After a SPA page transition (e.g. Workday step change), wait for the new
    content to be stable.  Checks that no loaders/spinners are visible and
    that form inputs exist.
    """
    # Wait for common loaders to disappear
    loader_selectors = [
        ".loading", ".spinner", "[role='progressbar']",
        "[data-automation-id='loadingSpinner']",  # Workday
        ".wd-spinner",                             # Workday
    ]
    for sel in loader_selectors:
        try:
            loader = page.locator(sel)
            if loader.count() > 0 and loader.first.is_visible():
                loader.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass

    # Brief settle for SPA re-renders
    page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# Login wall & CAPTCHA detection
# ---------------------------------------------------------------------------

_LOGIN_INDICATORS = [
    'input[type="password"]',
    'button:has-text("Sign In")',
    'button:has-text("Log In")',
    'button:has-text("Create Account")',
    'a:has-text("Sign In")',
    '[data-automation-id="signInLink"]',        # Workday
    '[data-automation-id="createAccountLink"]',  # Workday
]

_CAPTCHA_INDICATORS = [
    'iframe[src*="recaptcha"]',
    'iframe[src*="hcaptcha"]',
    'iframe[src*="turnstile"]',
    '.g-recaptcha',
    '.h-captcha',
    '#captcha',
    '[data-sitekey]',
]


def detect_login_wall(page) -> bool:
    """Return True if the page appears to require sign-in before the actual application form."""
    for sel in _LOGIN_INDICATORS:
        try:
            el = page.locator(sel)
            if el.count() > 0 and el.first.is_visible():
                return True
        except Exception:
            continue
    return False


def detect_captcha(page) -> bool:
    """Return True if a CAPTCHA challenge is visible on the page."""
    for sel in _CAPTCHA_INDICATORS:
        try:
            el = page.locator(sel)
            if el.count() > 0:
                return True
        except Exception:
            continue
    return False


def wait_for_user_to_clear_blocker(page, blocker_type: str = "login wall"):
    """
    Pause automation and prompt the user to manually handle a blocker
    (login wall, CAPTCHA, etc.), then wait for the form to appear.
    """
    print(f"\n[action required] A {blocker_type} was detected on this page.", file=sys.stderr)
    print("[action required] Please complete it manually in the browser.", file=sys.stderr)
    input("[prompt] Press Enter when you're past the blocker and can see the application form... ")
    wait_for_page_ready(page)


# ---------------------------------------------------------------------------
# Iframe handling
# ---------------------------------------------------------------------------

def get_form_frame(page):
    """
    Check whether the application form is inside an iframe and return
    the correct Frame/Page object to operate on.

    Many ATS platforms (Greenhouse embed, iCIMS, BambooHR) render their
    form inside an <iframe>.  If we detect that, we return the inner frame;
    otherwise we return the page itself.
    """
    form_iframe_selectors = [
        'iframe#grnhse_iframe',         # Greenhouse embedded iframe
        'iframe[src*="greenhouse"]',
        'iframe[src*="lever.co"]',
        'iframe[src*="icims"]',
        'iframe[src*="bamboohr"]',
        'iframe[src*="jobvite"]',
        'iframe[src*="myworkday"]',
        'iframe[src*="ashby"]',
    ]

    for sel in form_iframe_selectors:
        try:
            iframe_el = page.locator(sel)
            if iframe_el.count() > 0:
                frame = iframe_el.first.content_frame()
                if frame:
                    print(f"[info] Application form detected inside iframe ({sel})")
                    return frame
        except Exception:
            continue

    # Fallback: check all iframes for one that contains a <form>
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            if frame.locator("form").count() > 0:
                print("[info] Application form detected inside an iframe (heuristic)")
                return frame
        except Exception:
            continue

    return page


# ---------------------------------------------------------------------------
# Shadow DOM
# ---------------------------------------------------------------------------

def discover_fields_with_shadow_dom(page) -> list:
    """
    Secondary-pass field discovery that pierces shadow DOMs.

    Uses Playwright's >> css= combinator to reach into shadow roots.
    Only called if the primary discover_fields() returns suspiciously
    few results.
    """
    from src.engine.filler import get_label_for_input

    fields = []
    # Playwright's locator() pierces shadow DOMs by default
    shadow_inputs = []
    for selector in ["input:visible", "textarea:visible", "select:visible"]:
        try:
            shadow_inputs.extend(page.locator(selector).all())
        except Exception:
            continue

    for el in shadow_inputs:
        try:
            tag = el.evaluate("el => el.tagName.toLowerCase()")
        except Exception:
            continue
        label = get_label_for_input(page, el)
        raw_type = (el.get_attribute("type") or "text").lower()

        field_type = "text"
        options = None
        if tag == "select":
            field_type = "select"
            options = el.locator("option").all_text_contents()
        elif tag == "textarea":
            field_type = "textarea"
        else:
            type_map = {"checkbox": "checkbox", "radio": "radio", "date": "date", "file": "file"}
            field_type = type_map.get(raw_type, "text")

        fields.append({
            "locator": el,
            "label": label,
            "field_type": field_type,
            "name": el.get_attribute("name") or el.get_attribute("id") or "",
            "required": el.get_attribute("required") is not None or el.get_attribute("aria-required") == "true",
            "section": "custom",
            "options": options,
            "placeholder": el.get_attribute("placeholder"),
        })

    return fields


# ---------------------------------------------------------------------------
# Multi-page / pagination detection
# ---------------------------------------------------------------------------

_NEXT_BUTTON_SELECTORS = [
    '[data-automation-id="bottom-navigation-next-button"]',  # Workday
    'button:has-text("Next")',
    'button:has-text("Continue")',
    'button:has-text("Save and Continue")',
    'button:has-text("Save & Continue")',
    'a:has-text("Next")',
    'a:has-text("Continue")',
    'input[type="submit"][value*="Next"]',
    'input[type="submit"][value*="Continue"]',
]

_SUBMIT_BUTTON_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Submit Application")',
    'button:has-text("Submit")',
    'button:has-text("Apply")',
    'button:has-text("Send Application")',
    '#submit_app',
    '[data-automation-id="submit"]',
]


def detect_multi_page(page) -> bool:
    """Return True if the form appears to have multiple pages/steps."""
    # Step indicators
    step_selectors = [
        "[class*='step-indicator']", "[class*='progress-bar']",
        "[class*='wizard']", "[class*='stepper']",
        "[role='progressbar']",
        "[data-automation-id*='step']",
        "ol.steps", "ul.steps",
    ]
    for sel in step_selectors:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            continue

    # Has a next/continue button (but no visible submit yet)
    has_next = False
    has_submit = False
    for sel in _NEXT_BUTTON_SELECTORS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                has_next = True
                break
        except Exception:
            continue
    for sel in _SUBMIT_BUTTON_SELECTORS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                has_submit = True
                break
        except Exception:
            continue

    if has_next and not has_submit:
        return True

    return False


def try_next_page(page) -> bool:
    """
    Attempt to navigate to the next page/step of a multi-page form.

    Returns True if navigation succeeded, False if no next button found
    or navigation didn't change the page content.
    """
    for sel in _NEXT_BUTTON_SELECTORS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                # Record current URL and content hash to detect actual navigation
                old_url = page.url
                btn.first.click()
                wait_for_navigation_settle(page)
                return True
        except Exception:
            continue
    return False


def is_final_step(page) -> bool:
    """Check if the current page is the final review/submit step."""
    # Check headings for review/submit keywords
    for sel in ["h1", "h2", "h3", "[role='heading']"]:
        try:
            headings = page.locator(sel).all()
            for h in headings:
                text = (h.text_content() or "").lower()
                if any(kw in text for kw in ["review", "summary", "submit", "confirm", "final"]):
                    return True
        except Exception:
            continue

    # Check if submit is visible but next is not
    has_submit = False
    has_next = False
    for sel in _SUBMIT_BUTTON_SELECTORS:
        try:
            if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                has_submit = True
                break
        except Exception:
            continue
    for sel in _NEXT_BUTTON_SELECTORS:
        try:
            if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                has_next = True
                break
        except Exception:
            continue

    return has_submit and not has_next


def find_and_click_submit(page) -> bool:
    """Find the submit button and click it.  Returns True if a button was found and clicked."""
    for sel in _SUBMIT_BUTTON_SELECTORS:
        try:
            btn = page.locator(sel)
            if btn.count() > 0 and btn.first.is_visible():
                btn.first.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass
                return True
        except Exception:
            continue
    return False
