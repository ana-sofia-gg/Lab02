"""Genera el inventario reproducible de los datos crudos (Actividad 1.2).

El inventario documenta procedencia, DOI, licencia, versión, hashes SHA-256,
fecha de descarga, tamaño, duración, canales, unidades y problemas conocidos
de cada registro, según el contrato de datos de la sección 3.2.

El hash detecta cambios en el archivo, más no anonimiza ni protege el contenido.
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import wfdb

from ecg_af_dashboard.config import RAW_DIR, RESULTS_DIR

OUTPUT_PATH = RESULTS_DIR / "data_inventory.json"

SOURCE = {
    "database": "MIT-BIH Atrial Fibrillation Database (afdb)",
    "provenance": "https://physionet.org/content/afdb/1.0.0/",
    "doi": "10.13026/C2MW2D",
    "version": "1.0.0",
    "license": "Open Data Commons Attribution License (ODC-By) v1.0",
}

# Problemas conocidos documentados por el equipo en la Actividad 1.1.
# No se corrigen sobre el archivo original: se declaran para que el análisis
# posterior los tenga en cuenta.
KNOWN_ISSUES = {
    "05091": [
        "Sin problemas estructurales; las anotaciones de latido son "
        "auditadas (extensión .qrsc)."
    ],
    "04043": ["Bloque 39 ilegible: aproximadamente 10.24 s de ceros en la señal."],
    "06453": ["Grabación incompleta: la duración es menor a las 10 horas nominales."],
}


def calculate_sha256(file_path: Path) -> str:
    """Calcula el hash SHA-256 leyendo el archivo en bloques de 4096 bytes.

    La lectura por bloques evita cargar archivos de decenas de MB en memoria.
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def file_timestamp_utc(file_path: Path) -> str:
    """Devuelve la fecha de última modificación del archivo en ISO 8601 UTC.

    Para los archivos crudos, que nunca se modifican, equivale a la fecha en
    que fueron descargados.
    """
    mtime = file_path.stat().st_mtime
    return datetime.fromtimestamp(mtime, tz=UTC).isoformat()


def describe_file(file_path: Path) -> dict:
    """Construye la entrada de inventario de un archivo individual."""
    return {
        # Ruta relativa con separador POSIX para que el inventario sea
        # legible en cualquier sistema operativo.
        "path": file_path.as_posix(),
        "size_bytes": file_path.stat().st_size,
        "sha256": calculate_sha256(file_path),
        "downloaded_at": file_timestamp_utc(file_path),
    }


def describe_metadata(record_id: str) -> dict:
    """Lee el encabezado WFDB y deriva duración, canales y unidades."""
    try:
        header = wfdb.rdheader(str(RAW_DIR / record_id))
    except Exception as error:
        return {"error": str(error)}

    duration_s = header.sig_len / header.fs
    return {
        "sampling_frequency_hz": header.fs,
        "num_samples": header.sig_len,
        "duration_seconds": round(duration_s, 3),
        "duration_hours": round(duration_s / 3600, 4),
        "num_channels": header.n_sig,
        "signal_names": header.sig_name,
        "units": header.units,
    }


def generate_data_inventory() -> dict:
    """Recorre la carpeta cruda y escribe el inventario de datos."""
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            f"La carpeta {RAW_DIR} no existe. "
            "Ejecuta scripts/download_data.py antes de generar el inventario."
        )

    inventory = dict(SOURCE)
    inventory["inventory_generated_at"] = datetime.now(UTC).isoformat()
    inventory["records"] = []

    record_ids = sorted({f.stem for f in RAW_DIR.glob("*.hea")})
    if not record_ids:
        raise FileNotFoundError(
            f"No se encontraron encabezados WFDB (.hea) en {RAW_DIR}."
        )

    for record_id in record_ids:
        associated = sorted(RAW_DIR.glob(f"{record_id}.*"))
        inventory["records"].append(
            {
                "record_id": record_id,
                "files": [describe_file(f) for f in associated],
                "metadata": describe_metadata(record_id),
                "known_issues": KNOWN_ISSUES.get(record_id, []),
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as inv:
        json.dump(inventory, inv, indent=4, ensure_ascii=False)

    print(f"Inventario generado en {OUTPUT_PATH}")
    print(f"Registros documentados: {len(inventory['records'])}")
    return inventory
