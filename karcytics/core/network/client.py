"""Centralized HTTP client for Karcytics."""

import logging
from collections.abc import Mapping

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Retry strategy: up to 3 attempts with exponential backoff (0.5 s, 1 s, 2 s).
# Retries on connection errors (incl. DNS NameResolutionError which macOS can
# raise transiently at startup before the DNS subsystem is fully ready).
_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
_HTTP_ADAPTER = HTTPAdapter(max_retries=_RETRY_STRATEGY)


def _build_session() -> requests.Session:
    """Return a requests.Session pre-mounted with the standard retry adapter."""
    session = requests.Session()
    session.mount("https://", _HTTP_ADAPTER)
    session.mount("http://", _HTTP_ADAPTER)
    return session


class NetworkClient:
    """A centralized HTTP client with standardized headers, timeouts, and SSL handling."""

    DEFAULT_TIMEOUT = 15
    DEFAULT_HEADERS = {
        "User-Agent": "Karcytics-App",
        "Cache-Control": "no-cache, no-store",
        "Pragma": "no-cache",
    }

    @classmethod
    def get(
        cls,
        url: str,
        stream: bool = False,
        timeout: int = DEFAULT_TIMEOUT,
        extra_headers: Mapping[str, str] | None = None,
    ) -> requests.Response:  # noqa: E501
        """Perform an HTTP GET request using Karcytics's standard headers and TLS verification.

        Parameters:
                url (str): The URL to request.
                stream (bool): Whether to stream the response content.
                timeout (int): Maximum time in seconds to wait for the request.
                extra_headers (Mapping[str, str] | None): Optional headers that override
                    the standard headers.

        Returns:
                requests.Response: The HTTP response.
        """
        headers = cls.DEFAULT_HEADERS.copy()
        if extra_headers:
            headers.update(extra_headers)

        session = _build_session()
        return session.get(
            url, stream=stream, timeout=timeout, headers=headers, verify=certifi.where()
        )
