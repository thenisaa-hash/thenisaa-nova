#!/usr/bin/env python3
"""
shopify_api.py
──────────────
Thin Shopify Admin REST API client used by the migration scripts.
Handles products, custom collections, pages, and navigation menus.

Requires:
  SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN set in migration/config.py
  (copy config.example.py → config.py and fill in your credentials).
"""

import time
from typing import Any

import requests


class ShopifyAPIError(Exception):
    pass


class ShopifyClient:
    """Minimal Shopify Admin REST API v2024-04 client."""

    API_VERSION = "2024-04"

    def __init__(self, store_url: str, access_token: str):
        # Normalise store URL – strip protocol if present
        store_url = store_url.replace("https://", "").replace("http://", "").rstrip("/")
        self._base = f"https://{store_url}/admin/api/{self.API_VERSION}"
        self._session = requests.Session()
        self._session.headers.update({
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        })

    # ── Internal request helper ───────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Send a request with automatic retry on 429 (rate limit)."""
        url = f"{self._base}{path}"
        for attempt in range(5):
            response = self._session.request(method, url, **kwargs)

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", 2))
                print(f"  [rate-limit] sleeping {retry_after}s …")
                time.sleep(retry_after)
                continue

            if not response.ok:
                raise ShopifyAPIError(
                    f"{method} {path} → {response.status_code}: {response.text[:300]}"
                )
            return response.json()

        raise ShopifyAPIError(f"Exceeded retries for {method} {path}")

    def _get_all(self, path: str, resource_key: str,
                  params: dict | None = None) -> list[dict]:
        """Paginate through all pages and return all items."""
        params = params or {}
        params.setdefault("limit", 250)
        items: list[dict] = []
        url = f"{self._base}{path}"

        while url:
            response = self._session.get(url, params=params)
            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", 2)))
                continue
            response.raise_for_status()
            data = response.json()
            items.extend(data.get(resource_key, []))

            # Cursor-based pagination (Link header)
            link_header = response.headers.get("Link", "")
            next_url = None
            for part in link_header.split(","):
                if 'rel="next"' in part:
                    next_url = part.split(";")[0].strip().strip("<>")
            url = next_url
            params = {}  # Params are already encoded in the next URL

        return items

    # ── Products ──────────────────────────────────────────────────────────────

    def list_products(self, fields: str = "id,title,variants") -> list[dict]:
        return self._get_all("/products.json", "products",
                              params={"fields": fields})

    def create_product(self, payload: dict) -> dict:
        data = self._request("POST", "/products.json", json={"product": payload})
        return data["product"]

    def update_product(self, product_id: int, payload: dict) -> dict:
        data = self._request("PUT", f"/products/{product_id}.json",
                              json={"product": payload})
        return data["product"]

    def find_product_by_sku(self, sku: str) -> dict | None:
        """Search for an existing product that has a variant with the given SKU."""
        products = self._get_all(
            "/products.json", "products",
            params={"fields": "id,variants"}
        )
        for product in products:
            for variant in product.get("variants", []):
                if variant.get("sku", "").strip() == sku.strip():
                    return product
        return None

    # ── Custom Collections ────────────────────────────────────────────────────

    def list_custom_collections(self) -> list[dict]:
        return self._get_all("/custom_collections.json", "custom_collections")

    def create_custom_collection(self, title: str,
                                  image_src: str = "") -> dict:
        payload: dict[str, Any] = {"title": title}
        if image_src:
            payload["image"] = {"src": image_src}
        data = self._request("POST", "/custom_collections.json",
                              json={"custom_collection": payload})
        return data["custom_collection"]

    def add_product_to_collection(self, collection_id: int,
                                   product_id: int) -> dict:
        data = self._request("POST", "/collects.json", json={
            "collect": {
                "product_id": product_id,
                "collection_id": collection_id,
            }
        })
        return data["collect"]

    # ── Pages ─────────────────────────────────────────────────────────────────

    def list_pages(self) -> list[dict]:
        return self._get_all("/pages.json", "pages")

    def create_page(self, title: str, body_html: str = "",
                    handle: str = "") -> dict:
        payload: dict[str, Any] = {"title": title, "body_html": body_html}
        if handle:
            payload["handle"] = handle
        data = self._request("POST", "/pages.json", json={"page": payload})
        return data["page"]

    # ── Navigation Menus ──────────────────────────────────────────────────────

    def list_menus(self) -> list[dict]:
        """List all menus (navigation links groups)."""
        data = self._request("GET", "/menus.json")
        return data.get("menus", [])

    def create_menu(self, title: str, handle: str,
                    items: list[dict]) -> dict:
        """
        Create a navigation menu.
        items format: [{"title": str, "type": "collection_link"|"page_link"|"http_link",
                         "subject_id": int|None, "url": str|None}]
        """
        data = self._request("POST", "/menus.json", json={
            "menu": {"title": title, "handle": handle, "items": items}
        })
        return data["menu"]

    # ── Theme helpers ─────────────────────────────────────────────────────────

    def list_themes(self) -> list[dict]:
        data = self._request("GET", "/themes.json")
        return data.get("themes", [])

    def get_active_theme(self) -> dict | None:
        for theme in self.list_themes():
            if theme.get("role") == "main":
                return theme
        return None

    def get_asset(self, theme_id: int, key: str) -> dict:
        data = self._request("GET", f"/themes/{theme_id}/assets.json",
                              params={"asset[key]": key})
        return data.get("asset", {})

    def put_asset(self, theme_id: int, key: str, value: str) -> dict:
        """Upload or overwrite a theme asset (file)."""
        data = self._request("PUT", f"/themes/{theme_id}/assets.json", json={
            "asset": {"key": key, "value": value}
        })
        return data.get("asset", {})
