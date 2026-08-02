"""Lectura, auditoría y respaldo seguro de bindings de Elite Dangerous."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

NO_DEVICE = {"", "{NoDevice}"}


@dataclass(frozen=True, slots=True)
class BindingInput:
    device: str
    key: str
    modifiers: tuple[tuple[str, str], ...] = ()

    @property
    def configured(self) -> bool:
        return self.device not in NO_DEVICE and bool(self.key)


@dataclass(frozen=True, slots=True)
class BindingAction:
    name: str
    primary: BindingInput
    secondary: BindingInput

    @property
    def configured(self) -> bool:
        return self.primary.configured or self.secondary.configured


@dataclass(slots=True)
class BindingProfile:
    path: Path
    preset_name: str
    major_version: str
    minor_version: str
    keyboard_layout: str
    actions: dict[str, BindingAction] = field(default_factory=dict)
    sha256: str = ""


@dataclass(frozen=True, slots=True)
class BindingAudit:
    profiles: tuple[BindingProfile, ...]
    active_presets: tuple[str, ...]
    loading_errors: tuple[str, ...]
    snapshot_path: Path | None


class BindingCustodian:
    """Nunca modifica los originales; sólo lee y crea snapshots externos."""

    IMPORTANT_ACTIONS = (
        "ShipSpotLightToggle", "NightVisionToggle",
        "HumanoidToggleFlashlightButton", "HumanoidToggleNightVisionButton",
        "OrderRequestDock", "UIFocus", "FocusLeftPanel",
        "UI_Up", "UI_Down", "UI_Left", "UI_Right", "UI_Select",
    )

    def __init__(self, bindings_root: Path, data_root: Path) -> None:
        self.bindings_root = bindings_root
        self.backup_root = data_root / "heimdall" / "bindings"

    def audit(self, *, create_snapshot: bool = True) -> BindingAudit:
        profiles = tuple(
            self.parse_profile(path)
            for path in sorted(self.bindings_root.glob("*.binds"))
        ) if self.bindings_root.exists() else ()
        snapshot = self.create_snapshot(profiles) if create_snapshot and profiles else None
        return BindingAudit(
            profiles, self._active_presets(), self._loading_errors(), snapshot
        )

    def parse_profile(self, path: Path) -> BindingProfile:
        raw = path.read_bytes()
        root = ET.fromstring(raw)
        profile = BindingProfile(
            path=path,
            preset_name=root.attrib.get("PresetName", path.stem),
            major_version=root.attrib.get("MajorVersion", ""),
            minor_version=root.attrib.get("MinorVersion", ""),
            keyboard_layout=root.findtext("KeyboardLayout", default=""),
            sha256=hashlib.sha256(raw).hexdigest(),
        )
        for name in self.IMPORTANT_ACTIONS:
            element = root.find(name)
            if element is not None:
                profile.actions[name] = BindingAction(
                    name, self._input(element.find("Primary")),
                    self._input(element.find("Secondary")),
                )
        return profile

    def create_snapshot(self, profiles: tuple[BindingProfile, ...]) -> Path:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        source_files = tuple(profile.path for profile in profiles)
        source_files += tuple(sorted(self.bindings_root.glob("StartPreset*.start")))
        error_log = self.bindings_root / "BindingLoadingErrors.log"
        if error_log.exists():
            source_files += (error_log,)

        digest = hashlib.sha256()
        for path in source_files:
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        fingerprint = digest.hexdigest()
        existing = sorted(self.backup_root.glob(f"*-{fingerprint[:12]}"))
        if existing:
            return existing[-1]

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = self.backup_root / f"{timestamp}-{fingerprint[:12]}"
        destination.mkdir(parents=True, exist_ok=False)
        for path in source_files:
            shutil.copy2(path, destination / path.name)
        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "fingerprint": fingerprint,
            "files": [path.name for path in source_files],
            "profiles": [
                {
                    "file": profile.path.name,
                    "preset": profile.preset_name,
                    "version": f"{profile.major_version}.{profile.minor_version}",
                    "keyboard_layout": profile.keyboard_layout,
                    "sha256": profile.sha256,
                }
                for profile in profiles
            ],
        }
        (destination / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return destination

    def _active_presets(self) -> tuple[str, ...]:
        values: list[str] = []
        for path in sorted(self.bindings_root.glob("StartPreset*.start")):
            values.extend(
                line.strip()
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.strip()
            )
        return tuple(values)

    def _loading_errors(self) -> tuple[str, ...]:
        path = self.bindings_root / "BindingLoadingErrors.log"
        if not path.exists():
            return ()
        return tuple(
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        )

    @staticmethod
    def _input(element: ET.Element | None) -> BindingInput:
        if element is None:
            return BindingInput("", "")
        modifiers = tuple(
            (item.attrib.get("Device", ""), item.attrib.get("Key", ""))
            for item in element.findall("Modifier")
        )
        return BindingInput(
            element.attrib.get("Device", ""), element.attrib.get("Key", ""), modifiers
        )
