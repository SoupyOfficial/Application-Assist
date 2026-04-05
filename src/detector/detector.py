"""
detector.py — Main ATS platform detection orchestrator.

Detection priority order:
  1. URL pattern matching  (fast, no browser needed)
  2. DOM marker inspection (requires Playwright page)

Returns a platform name string: greenhouse | lever | ashby | workday | generic
"""

from src.detector.platforms import greenhouse, lever, ashby, workday, generic


PLATFORMS = [greenhouse, lever, ashby, workday]  # generic is the fallback


def detect(url: str, page=None) -> str:
    """
    Detect the ATS platform for the given job application URL.

    Args:
        url:  The job application URL string.
        page: Optional Playwright Page object. If provided, enables DOM-based
              detection methods (markers, form signatures, meta tags).

    Returns:
        Platform name string: 'greenhouse', 'lever', 'ashby', 'workday', or 'generic'.
    """
    # --- Step 1: URL pattern matching (no browser required) ---
    for platform_module in PLATFORMS:
        if platform_module.matches_url(url):
            return platform_module.PLATFORM_NAME

    # --- Step 2: DOM-based detection (requires live Playwright page) ---
    if page is not None:
        for platform_module in PLATFORMS:
            if hasattr(platform_module, "detect_from_dom"):
                if platform_module.detect_from_dom(page):
                    return platform_module.PLATFORM_NAME

    # --- Fallback: generic ---
    return generic.PLATFORM_NAME
