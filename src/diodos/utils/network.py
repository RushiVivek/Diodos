import requests

from .wifi import is_correct_network
from . import http_client

def network_check(config: dict) -> bool:
    """
    Check if the network is behind a captive portal by making a request to a known URL.
    Returns True if a captive portal is detected, False otherwise.
    """
    network_check_config = config.get("network_check", {})
    SSID = config.get("network", {}).get("SSID")

    if SSID and is_correct_network(SSID):
        return False
    
    test_url = network_check_config.get("url")
    test_msg = network_check_config.get("msg", "Success")

    if not test_url:
        return True

    try:
        response = http_client.get(test_url, timeout=5)
        # Check if the response contains the expected message
        if test_msg in response.text:
            return False
        else:
            return True
    except requests.RequestException as e:
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
        return False

    try:
        response = http_client.post(
            login_url,
            data=credentials,
            timeout=5,
            allow_redirects=True,
        )

        return response.status_code == 200
    except requests.RequestException:
        return False

def attempt_logout(config: dict) -> bool:
    """
    Attempt to log out from the captive portal using the provided configuration.
    Returns True if logout is successful, False otherwise.
    """
    logout_config = config.get("logout", {})
    logout_url = logout_config.get("url")

    if not logout_url:
        return False

    try:
        response = http_client.get(
            logout_url,
            timeout=5,
            allow_redirects=True,
        )
        return response.status_code == 200
    except requests.RequestException:
        return False