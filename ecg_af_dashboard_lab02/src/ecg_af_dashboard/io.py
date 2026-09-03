from dataclasses import dataclass
from pathlib import Path

import numpy as np
import wfdb


@dataclass(frozen=True)
class ECGRecord:
    record_id: str
    sampling_frequency_hz: float
    signal: np.ndarray
    signal_names: tuple[str, ...]
    units: tuple[str, ...]
    rhythm_samples: np.ndarray
    rhythm_notes: tuple[str, ...]


def load_afdb_record(directory: Path, record_id: str) -> ECGRecord:
    """Lee señal y anotaciones de ritmo sin modificar la fuente."""
    record_path = directory / record_id
    if not (directory / f"{record_id}.hea").is_file():
        raise FileNotFoundError(f"Falta el encabezado WFDB: {record_id}.hea")

    record = wfdb.rdrecord(str(record_path), physical=True)
    rhythm = wfdb.rdann(str(record_path), extension="atr")
    if record.p_signal is None:
        raise ValueError(f"El registro {record_id} no contiene señal física.")

    return ECGRecord(
        record_id=record_id,
        sampling_frequency_hz=float(record.fs),
        signal=np.asarray(record.p_signal, dtype=float),
        signal_names=tuple(record.sig_name),
        units=tuple(record.units),
        rhythm_samples=np.asarray(rhythm.sample, dtype=int),
        rhythm_notes=tuple(rhythm.aux_note),
    )
