"""Descarga los registros de AFDB usados en el laboratorio y verifica su integridad.

Los archivos crudos (~77 MB) no se versionan en Git. Este script los recupera
desde PhysioNet y comprueba que coincidan con los hashes SHA-256 registrados
en results/data_inventory.json.

Uso:
    uv run python scripts/download_data.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import wfdb

from ecg_af_dashboard.config import RAW_DIR, RECORD_IDS, RESULTS_DIR
from ecg_af_dashboard.inventory import generate_data_inventory

DATABASE = "afdb"
"""Las rutas se derivan de la raíz del proyecto."""
RECORDS = list(RECORD_IDS)
INVENTORY_PATH = RESULTS_DIR / "data_inventory.json"


def calculate_sha256(file_path: Path) -> str:
    """Calcula el hash SHA-256 de un archivo leyéndolo por bloques."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def download_records() -> None:
    """Descarga los registros desde PhysioNet si aún no están en disco."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    missing = [r for r in RECORDS if not (RAW_DIR / f"{r}.hea").is_file()]
    if not missing:
        print(f"Los {len(RECORDS)} registros ya están en {RAW_DIR}.")
        return

    print(
        f"Descargando {len(missing)} registro(s) desde PhysioNet: {', '.join(missing)}"
    )
    print("Son ~26 MB por registro; puede tardar varios minutos.\n")

    wfdb.dl_database(
        DATABASE,
        str(RAW_DIR),
        records=missing,
        annotators="all",
    )
    print(f"\nDescarga completa en {RAW_DIR}")


def load_expected_hashes() -> dict[str, str]:
    """Lee los hashes esperados del inventario, indexados por nombre de archivo."""
    if not INVENTORY_PATH.is_file():
        """ Primer arranque del proyecto: todavía no existe una referencia contra
        la cual comparar. Se genera desde los archivos recién descargados y
        queda como referencia versionada para las siguientes ejecuciones."""
        print(f"\nNo existe {INVENTORY_PATH}; se genera desde lo descargado.")
        print("Versione ese archivo: es la referencia de integridad del proyecto.")
        generate_data_inventory()

    with open(INVENTORY_PATH, encoding="utf-8") as f:
        inventory = json.load(f)

    expected: dict[str, str] = {}
    for record in inventory.get("records", []):
        for file_entry in record.get("files", []):
            # El inventario guarda rutas con separador de Windows; se usa
            # solo el nombre del archivo para que funcione en cualquier SO.
            filename = file_entry["path"].replace("\\", "/").split("/")[-1]
            expected[filename] = file_entry["sha256"]
    return expected


def verify_integrity() -> bool:
    """Compara los archivos descargados contra los hashes del inventario."""
    expected = load_expected_hashes()
    if not expected:
        print(f"\n{INVENTORY_PATH} no lista ningún archivo; no hay nada que verificar.")
        return False

    print("\nVerificando integridad (SHA-256)...")
    all_ok = True

    for filename, expected_hash in sorted(expected.items()):
        file_path = RAW_DIR / filename
        if not file_path.is_file():
            print(f"  FALTA     {filename}")
            all_ok = False
            continue

        actual_hash = calculate_sha256(file_path)
        if actual_hash == expected_hash:
            print(f"  OK        {filename}")
        else:
            print(f"  ALTERADO  {filename}")
            print(f"            esperado: {expected_hash}")
            print(f"            obtenido: {actual_hash}")
            all_ok = False

    return all_ok


def main() -> int:
    download_records()

    if verify_integrity():
        print("\nTodos los archivos coinciden con el inventario.")
        print("El proyecto está listo. Siguiente paso:")
        print("  uv run python scripts/reproduce.py")
        return 0

    print("\nHay archivos faltantes o alterados.")
    print(f"Borra {RAW_DIR} y vuelve a ejecutar este script.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
