import requests
from django.core.cache import cache

import logging

logger = logging.getLogger(__name__)


def get_access_token(access_token_url, consumer_key, consumer_secret):
    # Check cache first
    cache_key = "mpesa_access_token"
    access_token = cache.get(cache_key)
    if access_token:
        logger.info("Using cached M-Pesa access token")
        return access_token

    try:
        response = requests.get(
            access_token_url, auth=(consumer_key, consumer_secret), timeout=10
        )
        response.raise_for_status()
        auth_data = response.json()
        access_token = auth_data.get("access_token")

        if not access_token:
            logger.error(f"No access token in response: {auth_data}")
            raise ValueError("No access token returned by M-Pesa API")

        # Cache token for 50 minutes (less than 1 hour to avoid expiry)
        cache.set(cache_key, access_token, timeout=50 * 60)
        logger.info("Successfully obtained and cached M-Pesa access token")
        return access_token

    except requests.RequestException as e:
        logger.error(
            f"Failed to obtain M-Pesa access token: {str(e)}, Response: {response.text if 'response' in locals() else 'No response'}"
        )
        raise ValueError(f"Failed to obtain access token: {str(e)}")
