# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import quote
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .types import SecretStr


class ApiError(RuntimeError):
    """Wikiwiki API error."""


@dataclass(frozen=True)
class WikiAuth:
    """Wikiwiki authentication."""
    api_key_id: SecretStr = field(repr=False)
    secret: SecretStr = field(repr=False)

    def __repr__(self) -> str:
        return "<WikiAuth: hidden>"


@dataclass(frozen=True)
class WikiApiConfig:
    """Wikiwiki API configuration."""
    wiki_id: str
    base_url: str = "https://api.wikiwiki.jp"
    timeout_sec: int = 10


class WikiClient:
    """Wikiwiki client."""
    def __init__(self, cfg: WikiApiConfig, auth: WikiAuth):
        self._cfg = cfg
        self._auth = auth
        self._session = requests.Session()

        retries = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries,
                              pool_connections=10,
                              pool_maxsize=10
                              )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._token: Optional[SecretStr] = None

    def list_pages(self) -> Dict[str, Any]:
        """
        List all pages in the wiki.

        GET /{wiki_id}/pages

        Returns:
            Dict[str, Any]: A dictionary containing the list of pages.
        """
        token = self._get_token()
        url = self._url(f"/{self._cfg.wiki_id}/pages")
        return self._request_json("GET", url, token=token)

    def get_page(self, page_name: str) -> Dict[str, Any]:
        """
        Get a page by name.

        GET /{wiki_id}/page/{page_name}

        Returns:
            Dict[str, Any]: A dictionary containing the page.
        """
        token = self._get_token()
        encoded_page_name = quote(page_name, safe="")
        url = self._url(f"/{self._cfg.wiki_id}/page/{encoded_page_name}")
        return self._request_json("GET", url, token=token)

    def _url(self, path: str) -> str:
        return self._cfg.base_url.rstrip("/") + path

    def _get_token(self) -> str:
        """
        Get a token for the API.

        Returns:
            str: A token for the API.
        """
        if self._token:
            return self._token
        self._token = self._auth_token()
        return self._token

    def _auth_token(self) -> str:
        """
        Authenticate and get a token for the API.

        Returns:
            str: A token for the API.
        """
        url = self._url(f"/{self._cfg.wiki_id}/auth")
        payload = {
            "api_key_id": self._auth.api_key_id,
            "secret": self._auth.secret
        }
        data = self._request_json(
                                  "POST", url, json=payload,
                                  token=None, allow_auth_post=True
                                  )
        token = data.get("token")
        status = data.get("status")
        if status not in (None, "ok") or not token:
            raise ApiError(status, data)

        return str(token)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        token: Optional[str],
        json: Optional[Dict[str, Any]] = None,
        allow_auth_post: bool = False,
        allow_write: bool = False
    ) -> Dict[str, Any]:
        """
        Request JSON data from the API.

        Returns:
            Dict[str, Any]: A dictionary containing the JSON data.
        """
        self._guard(method, url, allow_auth_post, allow_write)
        headers = {
            "User-Agent": "uro-dreamwatcher",
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = self._session.request(
            method,
            url,
            headers=headers,
            json=json,
            timeout=self._cfg.timeout_sec,
        )

        # If token expired/invalid, refresh once and retry
        if resp.status_code in (401, 403) and token:
            self._token = None
            new_token = self._get_token()
            headers["Authorization"] = f"Bearer {new_token}"
            resp = self._session.request(
                method,
                url,
                headers=headers,
                json=json,
                timeout=self._cfg.timeout_sec,
            )

        if resp.status_code >= 400:
            body = (resp.text or "")[:300]
            raise ApiError(f"HTTP {resp.status_code}: {body}")

        try:
            data = resp.json()
        except Exception as e:
            raise ApiError(f"Invalid JSON: {e}") from e

        if not isinstance(data, dict):
            raise ApiError(f"Unexpected JSON type: {type(data).__name__}")

        return data

    def _guard(
        self,
        method: str,
        url: str,
        allow_auth_post: bool = True,
        allow_write: bool = False
    ) -> None:
        """
        Guard the request.

        Raises:
            ValueError: If the request is blocked.
        """
        method_upper = method.strip().upper()
        if not url.startswith(self._cfg.base_url.rstrip("/") + "/"):
            raise ValueError(f"Invalid URL: {url}")

        if method_upper == "GET":
            return

        if method_upper == "POST":
            auth_suffix = f"{self._cfg.wiki_id}/auth"
            if allow_auth_post and url.endswith(auth_suffix):
                return
            raise ValueError(f"Blocked method: {method}")

        if not allow_write:
            raise ValueError(f"Blocked method: {method}")
