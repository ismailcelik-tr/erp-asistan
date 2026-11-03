"""Odoo 19 JSON-2 API driver."""

import os
from typing import Any

import httpx

__all__ = ["OdooClient", "OdooError"]

_TIMEOUT_SECONDS = 30
_HTTP_OK = 200


class OdooError(Exception):
    pass


class OdooClient:
    def __init__(self, url: str, db: str, api_key: str) -> None:
        self._http = httpx.Client(
            base_url=f"{url.rstrip('/')}/json/2",
            headers={
                "Authorization": f"bearer {api_key}",
                "X-Odoo-Database": db,
            },
            timeout=_TIMEOUT_SECONDS,
        )

    @classmethod
    def from_env(cls) -> "OdooClient":
        return cls(os.environ["ODOO_URL"], os.environ["ODOO_DB"], os.environ["ODOO_API_KEY"])

    def call(self, model: str, method: str, **params: Any) -> Any:
        resp = self._http.post(f"/{model}/{method}", json=params)
        if resp.status_code != _HTTP_OK:
            raise OdooError(_error_message(resp))

        return resp.json()

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str],
        limit: int | None = None,
        order: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {"domain": domain, "fields": fields}
        if limit is not None:
            params["limit"] = limit
        if order is not None:
            params["order"] = order

        return self.call(model, "search_read", **params)

    def create(self, model: str, vals_list: list[dict]) -> list[int]:
        return self.call(model, "create", vals_list=vals_list)

    def write(self, model: str, ids: list[int], vals: dict) -> None:
        self.call(model, "write", ids=ids, vals=vals)


def _error_message(resp: httpx.Response) -> str:
    try:
        return resp.json().get("message") or resp.text
    except ValueError:
        return resp.text
