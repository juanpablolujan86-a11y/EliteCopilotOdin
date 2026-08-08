"""Reproducción de MP3 mediante la API multimedia nativa de Windows."""

from __future__ import annotations

import ctypes
import os
import subprocess
import tempfile
import uuid
from pathlib import Path


class AudioPlaybackError(RuntimeError):
    pass


class WindowsMp3Player:
    def __init__(self, cache_directory: Path | None = None) -> None:
        self.cache_directory = cache_directory or Path(tempfile.gettempdir()) / "ODIN"
        self._winmm = ctypes.WinDLL("winmm.dll")
        self._send = self._winmm.mciSendStringW
        self._send.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_wchar_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        )
        self._send.restype = ctypes.c_uint

    def _command(self, command: str) -> None:
        error = self._send(command, None, 0, None)
        if error:
            raise AudioPlaybackError(f"Windows no pudo reproducir el audio ({error}).")

    def play(self, audio: bytes) -> None:
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        path = self.cache_directory / f"voice-{uuid.uuid4().hex}.mp3"
        alias = f"odinvoice{uuid.uuid4().hex}"
        path.write_bytes(audio)
        try:
            self._command(f'open "{path}" type mpegvideo alias {alias}')
            try:
                self._command(f"play {alias} wait")
            finally:
                self._send(f"close {alias}", None, 0, None)
        finally:
            path.unlink(missing_ok=True)


class WindowsSpeechPlayer:
    """Voces OneCore locales mediante Windows Runtime, sin créditos."""

    SCRIPT = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime] | Out-Null

function Await-WinRt($operation, $resultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait()
    return $task.Result
}

$voiceName = $env:ODIN_VOICE_NAME
$rate = [int]$env:ODIN_VOICE_RATE
$volume = [int]$env:ODIN_VOICE_VOLUME
$text = [Console]::In.ReadToEnd()
$speaker = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
    Where-Object {
        $_.DisplayName -eq $voiceName -or
        $voiceName.StartsWith($_.DisplayName) -or
        $_.Id -eq $voiceName
    } |
    Select-Object -First 1
if ($null -eq $voice) { throw "Voz OneCore no encontrada: $voiceName" }
$speaker.Voice = $voice
$speaker.Options.SpeakingRate = [Math]::Max(0.5, [Math]::Min(2.0, 1.0 + ($rate * 0.1)))
$speaker.Options.AudioVolume = [Math]::Max(0.0, [Math]::Min(1.0, $volume / 100.0))
$stream = Await-WinRt ($speaker.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$netStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream)
$path = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "odin-voice-$([Guid]::NewGuid()).wav")
$file = [System.IO.File]::Create($path)
$netStream.CopyTo($file)
$file.Dispose()
$netStream.Dispose()
$speaker.Dispose()
$sound = New-Object System.Media.SoundPlayer($path)
$sound.PlaySync()
$sound.Dispose()
Remove-Item -LiteralPath $path -Force
"""

    def speak(self, text: str, voice: str = "", rate: int = 0, volume: int = 100) -> None:
        environment = dict(os.environ)
        environment.update(
            {
                "ODIN_VOICE_NAME": voice,
                "ODIN_VOICE_RATE": str(rate),
                "ODIN_VOICE_VOLUME": str(volume),
            }
        )
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                self.SCRIPT,
            ],
            input=text,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
            env=environment,
        )
        if result.returncode:
            detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else ""
            raise AudioPlaybackError(
                "Windows no pudo usar la voz local solicitada. " + detail
            )
