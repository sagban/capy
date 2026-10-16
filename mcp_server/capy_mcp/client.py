"""HTTP client for Firebase Callable functions (Bearer auth)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

DEFAULT_PROJECT = "capy-dogfood"
DEFAULT_REGION = "us-central1"


class CallableClient:
    def __init__(
        self,
        *,
        access_token: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        emulator_host: str | None = None,
    ) -> None:
        self._token = (access_token or os.environ.get("CAPY_ACCESS_TOKEN") or "").strip()
        if not self._token:
            self._token = (os.environ.get("CAPY_FIREBASE_ID_TOKEN") or "").strip()
        if not self._token:
            raise ValueError("Set CAPY_ACCESS_TOKEN or CAPY_FIREBASE_ID_TOKEN")
        self._project = (project_id or os.environ.get("CAPY_PROJECT_ID") or DEFAULT_PROJECT).strip()
        self._region = (region or os.environ.get("CAPY_FUNCTIONS_REGION") or DEFAULT_REGION).strip()
        self._emulator = (emulator_host or os.environ.get("CAPY_FUNCTIONS_EMULATOR_HOST") or "").strip()

    def _url(self, name: str) -> str:
        if self._emulator:
            host = self._emulator if self._emulator.startswith("http") else f"http://{self._emulator}"
            base = host.rstrip("/")
            return f"{base}/{self._project}/{self._region}/{name}"
        return f"https://{self._region}-{self._project}.cloudfunctions.net/{name}"

    async def call(self, name: str, data: dict[str, Any], *, timeout: float = 120.0) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        body = {"data": data}
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self._url(name), headers=headers, json=body)
            response.raise_for_status()
            envelope = response.json()
        if isinstance(envelope, dict) and envelope.get("error"):
            raise RuntimeError(json.dumps(envelope["error"]))
        if isinstance(envelope, dict) and "result" in envelope:
            result = envelope["result"]
            if isinstance(result, dict):
                return result
            return {"result": result}
        if isinstance(envelope, dict):
            return envelope
        raise RuntimeError("Unexpected callable response")

    async def exchange_access_token(self, firebase_id_token: str) -> dict[str, Any]:
        return await self.call(
            "exchange_access_token",
            {"firebaseIdToken": firebase_id_token},
            timeout=30.0,
        )
