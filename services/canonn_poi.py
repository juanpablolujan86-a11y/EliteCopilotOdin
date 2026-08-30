"""Catálogos POI compatibles con Canonn, con caché local y límites seguros."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from math import sqrt
from pathlib import Path
from urllib.parse import urlparse

import requests


class CanonnPOIError(RuntimeError):
    """La fuente POI no pudo validarse sin comprometer la caché anterior."""


@dataclass(frozen=True, slots=True)
class CanonnPOI:
    category: str
    system: str
    x: float
    y: float
    z: float
    instructions: str = ""
    url: str = ""

    def distance_from(self, position: tuple[float, float, float]) -> float:
        return sqrt(sum((a - b) ** 2 for a, b in zip((self.x, self.y, self.z), position)))


class CanonnPOICatalog:
    """Carga fuentes pequeñas sólo por acción explícita y conserva la última válida."""

    MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024
    MAX_ENTRIES = 10_000
    CACHE_NAME = "canonn_poi_cache.json"

    def __init__(self, data_root: Path, session=None) -> None:
        self.cache_path = Path(data_root) / "canonn" / self.CACHE_NAME
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "ODIN-EliteCopilot/0.7 (Canonn POI reader)",
            "Accept": "application/json, text/tab-separated-values, text/plain",
        })
        self._items = self._load_cache()

    @property
    def items(self) -> tuple[CanonnPOI, ...]:
        return self._items

    def refresh(self, source: str | Path) -> tuple[CanonnPOI, ...]:
        """Actualiza una fuente; un fallo nunca reemplaza la caché válida."""

        text, hint = self._read_source(source)
        parsed = self._parse(text, hint)
        if not parsed:
            raise CanonnPOIError("El catálogo POI no contiene registros válidos.")
        self._save_cache(parsed)
        self._items = parsed
        return parsed

    def nearest(
        self, position: tuple[float, float, float], *, category: str = "",
        limit: int = 3,
    ) -> tuple[CanonnPOI, ...]:
        if len(position) != 3 or limit <= 0:
            return ()
        wanted = category.strip().casefold()
        candidates = (
            item for item in self._items
            if not wanted or item.category.casefold() == wanted
        )
        return tuple(sorted(candidates, key=lambda item: item.distance_from(position))[:limit])

    def nearest_matching(
        self, position: tuple[float, float, float], keywords, *, limit: int = 3,
    ) -> tuple[CanonnPOI, ...]:
        """Busca categorías por palabras sin exigir un nombre de catálogo exacto."""

        if len(position) != 3 or limit <= 0:
            return ()
        wanted = tuple(
            str(keyword).strip().casefold() for keyword in keywords
            if str(keyword).strip()
        )
        if not wanted:
            return ()
        candidates = (
            item for item in self._items
            if any(keyword in item.category.casefold() for keyword in wanted)
        )
        return tuple(sorted(
            candidates, key=lambda item: item.distance_from(position)
        )[:limit])

    def _read_source(self, source: str | Path) -> tuple[str, str]:
        value = str(source).strip()
        parsed = urlparse(value)
        is_remote = parsed.scheme in {"http", "https"} and "://" in value
        if is_remote:
            if parsed.scheme != "https":
                raise CanonnPOIError("Las fuentes remotas POI deben usar HTTPS.")
            try:
                response = self.session.get(value, timeout=30, stream=True)
                response.raise_for_status()
                declared = int(response.headers.get("Content-Length", 0) or 0)
                if declared > self.MAX_DOWNLOAD_BYTES:
                    raise CanonnPOIError("La fuente POI supera el límite de 5 MB.")
                chunks = []
                size = 0
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    size += len(chunk)
                    if size > self.MAX_DOWNLOAD_BYTES:
                        raise CanonnPOIError("La fuente POI supera el límite de 5 MB.")
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8-sig"), parsed.path
            except (requests.RequestException, UnicodeDecodeError, ValueError) as error:
                if isinstance(error, CanonnPOIError):
                    raise
                raise CanonnPOIError(f"No fue posible descargar el catálogo POI: {error}") from error
        if "://" in value:
            raise CanonnPOIError("Las fuentes remotas POI deben usar HTTPS.")
        path = Path(value).expanduser()
        try:
            if path.stat().st_size > self.MAX_DOWNLOAD_BYTES:
                raise CanonnPOIError("La fuente POI supera el límite de 5 MB.")
            return path.read_text(encoding="utf-8-sig"), path.suffix
        except (OSError, UnicodeDecodeError) as error:
            raise CanonnPOIError(f"No fue posible leer el catálogo POI: {error}") from error

    def _parse(self, text: str, hint: str) -> tuple[CanonnPOI, ...]:
        try:
            if hint.casefold().endswith(".json") or text.lstrip().startswith("["):
                payload = json.loads(text)
                if not isinstance(payload, list):
                    raise CanonnPOIError("El catálogo JSON debe ser una lista.")
                records = payload
            else:
                records = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
        except (csv.Error, json.JSONDecodeError, TypeError) as error:
            raise CanonnPOIError(f"Formato POI inválido: {error}") from error
        if len(records) > self.MAX_ENTRIES:
            raise CanonnPOIError("El catálogo POI supera los 10.000 registros.")
        items = []
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise CanonnPOIError(f"Registro POI {index} inválido.")
            items.append(self._validate_record(record, index))
        return tuple(items)

    @staticmethod
    def _validate_record(record: dict, index: int) -> CanonnPOI:
        lowered = {str(key).strip().casefold(): value for key, value in record.items()}
        category = str(lowered.get("type", lowered.get("category", ""))).strip()
        system = str(lowered.get("system", "")).strip()
        if not category or not system:
            raise CanonnPOIError(f"Registro POI {index}: faltan Type o System.")
        try:
            coordinates = tuple(float(lowered[name]) for name in ("x", "y", "z"))
        except (KeyError, TypeError, ValueError) as error:
            raise CanonnPOIError(f"Registro POI {index}: coordenadas inválidas.") from error
        url = str(lowered.get("url", "") or "").strip()
        if url and urlparse(url).scheme not in {"http", "https"}:
            raise CanonnPOIError(f"Registro POI {index}: URL no permitida.")
        return CanonnPOI(
            category=category, system=system,
            x=coordinates[0], y=coordinates[1], z=coordinates[2],
            instructions=str(lowered.get("instructions", "") or "").strip(),
            url=url,
        )

    def _load_cache(self) -> tuple[CanonnPOI, ...]:
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            return self._parse(json.dumps(payload, ensure_ascii=False), ".json")
        except (OSError, json.JSONDecodeError, CanonnPOIError):
            return ()

    def _save_cache(self, items: tuple[CanonnPOI, ...]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.cache_path)
