"""Resilient HTTP session management with proxy and anti-bot support."""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any

from solotono.config import USER_AGENT, HTTP_TIMEOUT, HTTP_RETRIES, HTTP_PROXY, HTTPS_PROXY

# Optional curl_cffi for Cloudflare TLS impersonation
try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False


def get_scraper_session() -> requests.Session:
    """Creates a configured requests.Session with retries and realistic headers."""
    session = requests.Session()
    
    retries = Retry(
        total=HTTP_RETRIES,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })

    if HTTP_PROXY or HTTPS_PROXY:
        proxies = {}
        if HTTP_PROXY:
            proxies["http"] = HTTP_PROXY
        if HTTPS_PROXY:
            proxies["https"] = HTTPS_PROXY
        session.proxies.update(proxies)

    return session


def fetch_url(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = HTTP_TIMEOUT, use_cffi: bool = False) -> Optional[str]:
    """Fetch URL with standard requests or curl_cffi if anti-bot TLS is needed."""
    if use_cffi and HAS_CURL_CFFI:
        try:
            r = cffi_requests.get(url, impersonate="chrome120", timeout=timeout)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass

    session = get_scraper_session()
    try:
        req_headers = headers or {}
        r = session.get(url, headers=req_headers, timeout=timeout)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass

    return None
