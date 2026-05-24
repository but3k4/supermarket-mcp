"""
Shared FlareSolverr client used by the store scrapers.

FlareSolverr drives a real browser to clear the bot protection that fronts the
store sites. Stores use it in one of two ways: cookie-reuse stores (Dunnes,
SuperValu, Aldi) harvest cookies once and reuse them with plain requests, while
per-request stores (Tesco, Lidl) fetch every page through FlareSolverr because
the page can't be reproduced from cookies alone.
"""

from __future__ import annotations

import os

import requests

FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://127.0.0.1:8191/v1")


def request(cmd: str, **kwargs: str | int) -> dict:
    """
    Send a command to FlareSolverr and return the decoded JSON response.

    Args:
        cmd: FlareSolverr command, e.g. "request.get" or "sessions.create".
        **kwargs: Extra fields merged into the request body (session, url, ...).

    Returns:
        The parsed JSON response body.
    """

    response = requests.post(
        FLARESOLVERR_URL,
        json={"cmd": cmd, **kwargs},
        timeout=120,
    )
    response.raise_for_status()

    return response.json()


def create_session(name: str) -> dict:
    """Create a named FlareSolverr browser session."""

    return request("sessions.create", session=name)


def destroy_session(name: str) -> dict:
    """Destroy a named FlareSolverr browser session."""

    return request("sessions.destroy", session=name)


def list_sessions() -> list[str]:
    """Return the names of the currently active FlareSolverr sessions."""

    return request("sessions.list").get("sessions", [])


def solve(name: str, url: str) -> tuple[str, dict[str, str], str]:
    """
    Load a URL through FlareSolverr and harvest the resulting session state.

    Args:
        name: FlareSolverr session to use.
        url: Page to fetch through the headless browser.

    Returns:
        A tuple of (html, cookies, user_agent) where cookies maps name to value.
    """

    result = request("request.get", session=name, url=url, maxTimeout=60000)
    solution = result.get("solution", {})
    html = solution.get("response", "")
    cookies = {c["name"]: c["value"] for c in solution.get("cookies", [])}
    user_agent = solution.get("userAgent", "")

    return html, cookies, user_agent


def is_blocked_page(html: str) -> bool:
    """
    Report whether HTML is a bot-protection challenge rather than real content.

    Args:
        html: Raw page HTML.

    Returns:
        True if the page looks like a challenge, CAPTCHA, or access-denied page.
    """

    lower = html.lower()
    blocked_signals = [
        "<title>just a moment",
        "verify you are human",
        "checking if the site connection is secure",
        "cf-turnstile",
        "g-recaptcha",
        "h-captcha",
        "access denied",
    ]

    return any(signal in lower for signal in blocked_signals)
