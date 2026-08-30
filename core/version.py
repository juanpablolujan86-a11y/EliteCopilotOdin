"""Versión visible de ODIN durante el desarrollo y las distribuciones."""

import os

VERSION = os.environ.get("ODIN_VERSION_OVERRIDE", "0.8.0-beta")
CAPABILITY = os.environ.get(
    "ODIN_CAPABILITY_OVERRIDE",
    "MÍMIR, HEIMDALL, FREYJA y BROKK beta",
)
