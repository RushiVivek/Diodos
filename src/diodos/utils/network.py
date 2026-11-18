import logging
import time
from enum import Enum

import requests

from . import http_client
from .wifi import current_ssid

logger = logging.getLogger(__name__)

# Seconds to wait for the portal to start letting traffic through after it
# accepted the login form.
LOGIN_SETTLE_SECONDS = 3


def is_online(check: dict) -> bool:
    """
    Return True if the internet is reachable without a captive portal.

    By default this asks a "generate_204" endpoint, the same probe Android and
    ChromeOS use: it answers an empty 204 when the internet is reachable, while
    a captive portal intercepts the plain-HTTP request and answers with its own
    page or a redirect instead. With `expect` set, the page body must contain
    that text instead.
    """
    expect = check.get("expect")

    try:
        # The check stays out of the shared cookie jar: it is not the portal.
        # Redirects are left unfollowed in 204 mode, since following one
        # would land on the portal's 200 page and hide the interception.
        response = requests.get(check["url"], timeout=5, allow_redirects=bool(expect))
    except requests.RequestException as e:
        logger.info("Connectivity check failed: %s", e)
        return False

    logger.debug("Connectivity check answered %s.", response.status_code)

    if expect:
        return expect in response.text

    return response.status_code == 204


def select_network(networks: list[dict], ssid: str | None) -> dict | None:
    """
    Pick the configured network for the Wi-Fi network we are on.

    A network lists the SSIDs it serves, and one with no SSIDs serves any
    network. If the current SSID cannot be read, only such a wildcard network
    is used: a network restricted to some SSIDs never gets its credentials
    sent on a network that could be any other.
    """
    if ssid is not None:
        for network in networks:
            if ssid in network["ssids"]:
                return network

    for network in networks:
        if not network["ssids"]:
            return network

    if ssid is None:
        logger.warning(
            "Could not read the Wi-Fi name, and every network is limited to "
            "specific SSIDs. Not logging in. Use ssids = [] to allow any network."
        )

    return None


class LoginResult(Enum):
    ONLINE = "already online"
    UNKNOWN_NETWORK = "not on a configured network"
    LOGGED_IN = "logged in"
    FAILED = "login failed"


def ensure_logged_in(config: dict) -> tuple[LoginResult, dict | None, str | None]:
    """
    Log in through the right portal if the internet is not reachable.

    Returns the result, the network used (if any) and the current SSID.
    """
    if is_online(config["check"]):
        logger.debug("Online. Nothing to do.")
        return LoginResult.ONLINE, None, None

    ssid = current_ssid()
    network = select_network(config["networks"], ssid)

    if network is None:
        logger.info("Offline, but no configured network matches SSID %r.", ssid)
        return LoginResult.UNKNOWN_NETWORK, None, ssid

    logger.info("Captive portal suspected on %r. Logging in to %s.", ssid, network["name"])

    if attempt_login(network, config["check"]):
        logger.info("Logged in to %s.", network["name"])
        return LoginResult.LOGGED_IN, network, ssid

    logger.error("Login to %s failed.", network["name"])
    return LoginResult.FAILED, network, ssid


def attempt_login(network: dict, check: dict) -> bool:
    """
    Submit the login form, then confirm the internet is actually reachable.

    Many portals answer 200 even when they reject the credentials, so the
    status code alone does not prove the login worked.
    """
    login = network["login"]

    try:
        response = http_client.post(login["url"], data=login["form"], timeout=10)
    except requests.RequestException as e:
        logger.error("Could not reach the login page %s: %s", login["url"], e)
        return False

    logger.debug("Login response status code: %s", response.status_code)

    if not response.ok:
        return False

    deadline = time.monotonic() + LOGIN_SETTLE_SECONDS
    while True:
        if is_online(check):
            return True
        if time.monotonic() >= deadline:
            logger.warning("The portal accepted the form, but the internet is still unreachable.")
            return False
        time.sleep(1)


def attempt_logout(network: dict) -> bool:
    """
    Log out of the portal: a POST if the logout has form fields, else a GET.
    Returns True if the portal accepted the request.
    """
    logout = network["logout"]

    try:
        if logout["form"]:
            response = http_client.post(logout["url"], data=logout["form"], timeout=10)
        else:
            response = http_client.get(logout["url"], timeout=10)
    except requests.RequestException as e:
        logger.error("Error occurred while attempting logout: %s", e)
        return False

    logger.debug("Logout response status code: %s", response.status_code)
    return response.ok
