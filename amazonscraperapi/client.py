"""Amazon Scraper API client implementation."""
from __future__ import annotations

import hmac
import hashlib
from typing import Any, Iterable, Mapping, Optional

import httpx


class AmazonScraperAPIError(Exception):
    """Raised when the API returns a non-2xx response."""

    def __init__(self, status_code: int, body: Any, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AmazonScraperAPI:
    """Synchronous client. For async, use :class:`AsyncAmazonScraperAPI`."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.amazonscraperapi.com",
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "amazonscraperapi-python/0.1.0",
            },
        )

    # ---------- Sync endpoints ----------

    def product(
        self,
        *,
        query: str,
        domain: str = "com",
        language: Optional[str] = None,
        add_html: bool = False,
    ) -> dict:
        """Scrape a single Amazon product by ASIN."""
        params: dict = {"query": query, "domain": domain}
        if language:
            params["language"] = language
        if add_html:
            params["add_html"] = "true"
        return self._request("GET", "/api/v1/amazon/product", params=params)

    def search(
        self,
        *,
        query: str,
        domain: str = "com",
        sort_by: str = "best_match",
        start_page: int = 1,
        pages: int = 1,
    ) -> dict:
        """Amazon keyword search. Returns ranked product listings."""
        params = {
            "query": query,
            "domain": domain,
            "sort_by": sort_by,
            "start_page": start_page,
            "pages": pages,
        }
        return self._request("GET", "/api/v1/amazon/search", params=params)

    # ---------- Async batch ----------

    def create_batch(
        self,
        *,
        endpoint: str,
        items: Iterable[Mapping[str, Any]],
        webhook_url: Optional[str] = None,
    ) -> dict:
        """Create an async batch. Save the returned webhook_signature_secret immediately."""
        body: dict = {"endpoint": endpoint, "items": list(items)}
        if webhook_url:
            body["webhook_url"] = webhook_url
        return self._request("POST", "/api/v1/amazon/batch", json=body)

    def get_batch(self, batch_id: str) -> dict:
        """Poll current status + results of a batch."""
        return self._request("GET", f"/api/v1/amazon/batch/{batch_id}")

    def list_batches(self, *, limit: int = 20) -> dict:
        """List your recent batches."""
        return self._request("GET", "/api/v1/amazon/batch", params={"limit": limit})

    # ---------- Internal ----------

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Any = None,
    ) -> dict:
        url = self._base_url + path
        resp = self._client.request(method, url, params=params, json=json)
        try:
            body = resp.json()
        except ValueError:
            body = None
        if not resp.is_success:
            err = (body or {}).get("error", "request failed") if isinstance(body, dict) else "request failed"
            raise AmazonScraperAPIError(resp.status_code, body, f"HTTP {resp.status_code}: {err}")
        return body if isinstance(body, dict) else {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AmazonScraperAPI":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def verify_webhook_signature(signature_header: Optional[str], raw_body: bytes, secret: str) -> bool:
    """Verify an inbound webhook signature from Amazon Scraper API.

    Pass ``request.headers.get('X-ASA-Signature')`` and the raw body bytes.
    Returns True if the signature matches.
    """
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header, expected)
