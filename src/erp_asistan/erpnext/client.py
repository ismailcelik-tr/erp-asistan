"""Frappe/ERPNext REST driver."""

import json
import os
import re
from typing import Any

import httpx

__all__ = ["ErpNextClient", "ErpNextError"]

_TIMEOUT_SECONDS = 60
_HTTP_OK = 200
_ALL_ROWS = 0  # Frappe: limit_page_length=0 means no limit (default is 20)
_TAGS = re.compile(r"<[^>]+>")


class ErpNextError(Exception):
    pass


class ErpNextClient:
    def __init__(self, url: str, site: str, api_key: str, api_secret: str) -> None:
        self.url = url.rstrip("/")
        # One server hosts the demo and test sites; nginx routes by Host.
        self._http = httpx.Client(
            base_url=self.url,
            headers={"Authorization": f"token {api_key}:{api_secret}", "Host": site},
            timeout=_TIMEOUT_SECONDS,
        )

    @classmethod
    def from_env(cls) -> "ErpNextClient":
        return cls(
            os.environ["ERPNEXT_URL"], os.environ["ERPNEXT_SITE"],
            os.environ["ERPNEXT_API_KEY"], os.environ["ERPNEXT_API_SECRET"],
        )

    def call(self, method: str, **params: Any) -> Any:
        resp = self._http.post(f"/api/method/{method}", json=params)
        if resp.status_code != _HTTP_OK:
            raise ErpNextError(_error_message(resp))

        return resp.json().get("message")

    def get_list(
        self,
        doctype: str,
        fields: list[str],
        filters: list | tuple = (),
        or_filters: list | tuple = (),
        limit: int | None = None,
        order_by: str | None = None,
        parent: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {
            "doctype": doctype,
            "fields": fields,
            "filters": list(filters),
            "limit_page_length": limit or _ALL_ROWS,
        }
        if or_filters:
            params["or_filters"] = list(or_filters)
        if order_by:
            params["order_by"] = order_by
        if parent:
            params["parent"] = parent

        return self.call("frappe.client.get_list", **params)

    def get_doc(self, doctype: str, name: str) -> dict:
        return self.call("frappe.client.get", doctype=doctype, name=name)

    def insert(self, doc: dict) -> dict:
        """docstatus=1 in doc inserts and submits in one step."""
        return self.call("frappe.client.insert", doc=doc)

    def set_value(self, doctype: str, name: str, vals: dict) -> dict:
        return self.call("frappe.client.set_value", doctype=doctype, name=name, fieldname=vals)

    def file(self, path: str) -> bytes:
        resp = self._http.get(path)
        if resp.status_code != _HTTP_OK:
            raise ErpNextError(_error_message(resp))

        return resp.content

    def upload(self, filename: str, content: bytes, doctype: str, name: str, field: str) -> str:
        resp = self._http.post(
            "/api/method/upload_file",
            files={"file": (filename, content)},
            data={"doctype": doctype, "docname": name, "fieldname": field, "is_private": "0"},
        )
        if resp.status_code != _HTTP_OK:
            raise ErpNextError(_error_message(resp))

        return resp.json()["message"]["file_url"]


def _error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text

    # _server_messages: JSON list of JSON objects, each with an HTML "message".
    try:
        messages = [json.loads(m).get("message", "") for m in json.loads(body.get("_server_messages") or "[]")]
    except (ValueError, AttributeError):
        messages = []

    text = " ".join(m for m in messages if m) or body.get("exception") or body.get("exc_type") or resp.text
    return _TAGS.sub("", str(text)).strip()
