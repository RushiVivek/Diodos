import requests
import logging

from .wifi import is_correct_network
from . import http_client

logger = logging.getLogger(__name__)


def network_check(config: dict) -> bool:
    """
    Check if the network is behind a captive portal by making a request to a known URL.
    Returns True if a captive portal is detected, False otherwise.
    """
    network_check_config = config.get("network_check", {})
    SSID = config.get("network", {}).get("SSID")

    if SSID and not is_correct_network(SSID):
        logger.debug("Not connected to the expected network: %s. Skipping captive portal check.", SSID)
        return False
    
    test_url = network_check_config.get("url")
    test_msg = network_check_config.get("msg", "Success")

    if not test_url:
        logger.debug("No test URL provided for network check. Assuming no captive portal.")
        return True

    try:
        response = http_client.get(test_url, timeout=5)
        logger.debug("Network check response status code: %s", response.status_code)
        # Check if the response contains the expected message
        if test_msg in response.text:
            logger.debug("No captive portal detected.")
            return False
        else:
            logger.debug("Captive portal detected.")
            return True
    except requests.RequestException as e:
        logger.warning("Network check failed: %s", e)
        return True

def attempt_login(config: dict) -> bool:
    """
    Attempt to log in to the captive portal using the provided credentials or configuration.
    Returns True if login is successful, False otherwise.
    """
    login_config = config.get("login", {})
    login_url = login_config.get("url")
    credentials = login_config.get("credentials", {})

    if not login_url:
        logger.debug("No login URL provided.")
        return False

    try:
        response = http_client.post(
            login_url,
            data=credentials,
            timeout=5,
            allow_redirects=True,
        )
        logger.debug("Login response status code: %s", response.status_code)
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error("Error occurred while attempting login: %s", e)
        return False

def attempt_logout(config: dict) -> bool:
    """
    Attempt to log out from the captive portal using the provided configuration.
    Returns True if logout is successful, False otherwise.
    """
    logout_config = config.get("logout", {})
    logout_url = logout_config.get("url")

    if not logout_url:
        logger.debug("No logout URL provided.")
        return False

    try:
        response = http_client.get(
            logout_url,
            timeout=5,
            allow_redirects=True,
        )
        logger.debug("Logout response status code: %s", response.status_code)
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error("Error occurred while attempting logout: %s", e)
        return False