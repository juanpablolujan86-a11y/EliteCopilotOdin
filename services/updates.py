"""Consulta pública de versiones; no envía datos del comandante."""
import re
from dataclasses import dataclass
import requests
from core.version import VERSION

REPOSITORY = "juanpablolujan86-a11y/EliteCopilotOdin"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"


def version_key(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)(?:[.-]?(\d+))?(?:-pre-IA)?)?", value)
    if not match:
        return None
    major, minor, patch, stage, number = match.groups()
    return (int(major), int(minor), int(patch), {"beta": 0, "rc": 1, None: 2}[stage], int(number or 0))


@dataclass(frozen=True)
class Update:
    version: str
    url: str


def check_for_update(current=VERSION, session=None):
    client = session or requests
    response = client.get(
        f"https://api.github.com/repos/{REPOSITORY}/releases",
        params={"per_page": 100}, timeout=8,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ODIN-update-check"},
    )
    response.raise_for_status()
    releases = response.json()
    current_key = version_key(current)
    if not isinstance(releases, list) or current_key is None:
        raise ValueError("Respuesta de versiones inválida")
    candidates = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag = release.get("tag_name", "")
        key = version_key(tag)
        url = release.get("html_url", "")
        if (key is not None and key > current_key
                and ("-" in current or not release.get("prerelease"))
                and url.startswith(RELEASES_URL + "/tag/")):
            candidates.append((key, Update(tag, url)))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None
