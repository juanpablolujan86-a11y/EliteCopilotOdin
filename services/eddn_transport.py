"""Transporte HTTP EDDN, desacoplado del bucle principal de ODIN."""

from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from services.eddn_outbox import EDDNOutbox


@dataclass(frozen=True, slots=True)
class EDDNDeliveryResult:
    accepted: bool
    retryable: bool
    status_code: int | None
    detail: str


class EDDNHTTPClient:
    ENDPOINT = "https://eddn.edcd.io:4430/upload/"

    def __init__(self, session=None) -> None:
        self.session = session or requests.Session()

    def send(self, envelope: dict) -> EDDNDeliveryResult:
        body = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        try:
            response = self.session.post(
                self.ENDPOINT,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=(5, 15),
            )
        except requests.RequestException as error:
            return EDDNDeliveryResult(False, True, None, str(error))
        status = int(response.status_code)
        detail = str(getattr(response, "text", "") or "")[:500]
        if status == 200 and detail.strip() == "OK":
            return EDDNDeliveryResult(True, False, status, detail)
        if status in {408, 413, 429} or status >= 500:
            return EDDNDeliveryResult(False, True, status, detail)
        return EDDNDeliveryResult(False, False, status, detail)


class EDDNDeliveryWorker:
    def __init__(self, outbox: EDDNOutbox, client: EDDNHTTPClient) -> None:
        self.outbox = outbox
        self.client = client

    def run_once(self, *, limit: int = 25, now=None) -> int:
        processed = 0
        for item in self.outbox.due(limit=limit, now=now):
            result = self.client.send(item.envelope)
            if result.accepted:
                self.outbox.mark_sent(item.message_key, now=now)
            elif result.retryable:
                self.outbox.mark_failed(item.message_key, result.detail, now=now)
            else:
                self.outbox.mark_rejected(item.message_key, result.detail, now=now)
            processed += 1
        return processed
