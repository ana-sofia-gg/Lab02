"""Reporta el entorno de ejecución para la bitácora de reproducción.

Uso:
    uv run python scripts/environment_report.py
"""

from __future__ import annotations

import importlib
import platform
import sys
from datetime import UTC, datetime

PACKAGES = [
    "numpy",
    "pandas",
    "scipy",
    "matplotlib",
    "plotly",
    "streamlit",
    "wfdb",
]


def main() -> int:
    print("REPORTE DE ENTORNO")
    print("=" * 46)
    print(f"fecha (UTC)   : {datetime.now(UTC).isoformat(timespec='seconds')}")
    print(f"sistema       : {platform.system()} {platform.release()}")
    print(f"arquitectura  : {platform.machine()}")
    print(f"python        : {sys.version.split()[0]}")
    print(f"ejecutable    : {sys.executable}")
    print("-" * 46)

    missing = []
    for name in PACKAGES:
        try:
            module = importlib.import_module(name)
            version = getattr(module, "__version__", "sin __version__")
            print(f"{name:<14}: {version}")
        except ImportError:
            print(f"{name:<14}: NO INSTALADO")
            missing.append(name)

    print("=" * 46)
    if missing:
        print(f"Faltan {len(missing)} paquete(s). Ejecuta: uv sync --locked")
        return 1

    print("Entorno completo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
