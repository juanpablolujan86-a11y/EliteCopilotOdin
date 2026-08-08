"""Descubrimiento de voces OneCore instaladas en Windows."""

from __future__ import annotations

import locale
import winreg
from dataclasses import dataclass


TOKENS_PATH = r"SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens"


@dataclass(frozen=True, slots=True)
class WindowsVoice:
    name: str
    language: str
    gender: str
    token: str


def list_windows_voices() -> tuple[WindowsVoice, ...]:
    voices: list[WindowsVoice] = []
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, TOKENS_PATH)
    except OSError:
        return ()
    with root:
        index = 0
        while True:
            try:
                token = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            with winreg.OpenKey(root, token) as voice_key:
                name = str(winreg.QueryValue(voice_key, None) or token)
                try:
                    with winreg.OpenKey(voice_key, "Attributes") as attributes:
                        language_raw = str(winreg.QueryValueEx(attributes, "Language")[0])
                        gender = str(winreg.QueryValueEx(attributes, "Gender")[0])
                except OSError:
                    language_raw, gender = "", ""
            try:
                language = locale.windows_locale[int(language_raw.split(";")[0], 16)]
            except (KeyError, ValueError):
                language = language_raw
            voices.append(WindowsVoice(name, language, gender, token))
    return tuple(sorted(voices, key=lambda item: (item.language, item.name)))
