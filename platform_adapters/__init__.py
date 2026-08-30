"""Adaptadores que aíslan al núcleo de los servicios del sistema operativo."""

from platform_adapters.clipboard import ClipboardAdapter, copy_text, create_clipboard
from platform_adapters.hotkey import HotkeyAdapter, create_hotkey
from platform_adapters.single_instance import SingleInstanceAdapter, create_single_instance
from platform_adapters.audio import AudioPlayer, SpeechPlayer, create_audio_player, create_speech_player
from platform_adapters.process import hidden_process_flags
from platform_adapters.cockpit import CockpitControlSender, create_cockpit_sender

__all__ = [
    "ClipboardAdapter", "copy_text", "create_clipboard",
    "HotkeyAdapter", "create_hotkey",
    "SingleInstanceAdapter", "create_single_instance",
    "AudioPlayer", "SpeechPlayer", "create_audio_player", "create_speech_player",
    "hidden_process_flags",
    "CockpitControlSender", "create_cockpit_sender",
]
