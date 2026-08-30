"""Configura el corte público estable anterior a la IA experimental."""

import os

os.environ["ODIN_PUBLIC_NO_AI"] = "1"
os.environ["ODIN_ENABLE_BROKK"] = "1"
os.environ["ODIN_VERSION_OVERRIDE"] = "0.8.0-beta-pre-IA"
os.environ["ODIN_CAPABILITY_OVERRIDE"] = (
    "MÍMIR, HEIMDALL, FREYJA, BROKK, Guardian, Ingeniería y Powerplay"
)
