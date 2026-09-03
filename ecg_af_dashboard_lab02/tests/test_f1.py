from pathlib import Path

import numpy as np
import pytest

from ecg_af_dashboard.io import ECGRecord, load_afdb_record
from ecg_af_dashboard.validation import validate_ecg_record


# 1. Prueba de registros reales existentes (Tu código actual)
@pytest.mark.parametrize("rec_id", ["04043", "05091", "06453"])
def test_afdb_record_loading_and_validation(rec_id):
    raw_dir = Path("data/raw/afdb")

    if not (raw_dir / f"{rec_id}.hea").exists():
        pytest.skip(f"El registro {rec_id} no está descargado localmente.")

    record = load_afdb_record(raw_dir, rec_id)

    assert record is not None
    assert record.record_id == rec_id
    assert record.signal.ndim == 2

    is_valid = validate_ecg_record(record)
    assert is_valid is True


# 2. Pruebas negativas para la Evidencia F1
def test_missing_file_raises_error(tmp_path):
    """Verifica que se lance FileNotFoundError si el archivo .hea no existe."""
    non_existent_id = "99999"
    with pytest.raises(FileNotFoundError):
        load_afdb_record(tmp_path, non_existent_id)


def test_incompatible_metadata_raises_error():
    """Verifica que validation.py detecte cuando los canales no coinciden con
    nombres/unidades."""
    bad_record = ECGRecord(
        record_id="test_bad",
        sampling_frequency_hz=250.0,
        signal=np.random.rand(1000, 2),  # 2 canales
        signal_names=("MLII",),  # Solo 1 nombre (Incompatible)
        units=("mV", "mV"),
        rhythm_samples=np.array([100, 200]),
        rhythm_notes=("(N", "(AFIB"),
    )
    with pytest.raises(ValueError, match="no coincide con los nombres"):
        validate_ecg_record(bad_record)


def test_unordered_annotations_raises_error():
    """Verifica que validation.py rechace anotaciones de ritmo que no estén en orden
    ascendente."""
    bad_record = ECGRecord(
        record_id="test_bad_ann",
        sampling_frequency_hz=250.0,
        signal=np.random.rand(1000, 2),
        signal_names=("MLII", "V1"),
        units=("mV", "mV"),
        rhythm_samples=np.array([300, 100]),  # Desordenadas (300 va antes de 100)
        rhythm_notes=("(N", "(AFIB"),
    )
    with pytest.raises(ValueError, match="orden ascendente"):
        validate_ecg_record(bad_record)


def test_invalid_sampling_frequency_raises_error():
    """Verifica que se rechacen frecuencias de muestreo negativas o no finitas."""
    bad_record = ECGRecord(
        record_id="test_bad_fs",
        sampling_frequency_hz=-250.0,  # Inválida
        signal=np.random.rand(1000, 2),
        signal_names=("MLII", "V1"),
        units=("mV", "mV"),
        rhythm_samples=np.array([100, 200]),
        rhythm_notes=("(N", "(AFIB"),
    )
    with pytest.raises(ValueError, match="Frecuencia de muestreo inválida"):
        validate_ecg_record(bad_record)
