from __future__ import annotations

import time
from typing import Any

import requests


class ApifyClient:
    def __init__(self, token: str, timeout_seconds: int = 30):
        self.token = token
        self.timeout_seconds = timeout_seconds
        self.base_url = "https://api.apify.com/v2"

    def run_actor(self, actor_id: str, actor_input: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.token:
            raise RuntimeError("Missing APIFY_TOKEN")

        run_url = f"{self.base_url}/acts/{actor_id}/runs"
        run_resp = requests.post(
            run_url,
            params={"token": self.token},
            json=actor_input,
            timeout=self.timeout_seconds,
        )
        run_resp.raise_for_status()
        run_id = (run_resp.json().get("data") or {}).get("id")
        if not run_id:
            raise RuntimeError("Apify run id not found")

        for _ in range(40):
            status_resp = requests.get(
                f"{self.base_url}/actor-runs/{run_id}",
                params={"token": self.token},
                timeout=self.timeout_seconds,
            )
            status_resp.raise_for_status()
            data = status_resp.json().get("data") or {}
            status = data.get("status")
            if status == "SUCCEEDED":
                dataset_id = data.get("defaultDatasetId")
                if not dataset_id:
                    return []
                items_resp = requests.get(
                    f"{self.base_url}/datasets/{dataset_id}/items",
                    params={"token": self.token, "clean": "true"},
                    timeout=self.timeout_seconds,
                )
                items_resp.raise_for_status()
                payload = items_resp.json()
                if isinstance(payload, list):
                    return payload
                return []
            if status in {"FAILED", "ABORTED", "TIMED-OUT"}:
                raise RuntimeError(f"Apify actor failed: {status}")
            time.sleep(1.5)

        raise RuntimeError("Apify actor polling timeout")
