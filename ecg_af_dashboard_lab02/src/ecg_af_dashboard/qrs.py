import numpy as np
from wfdb import processing


def detect_qrs_xqrs(
    values: np.ndarray,
    sampling_frequency_hz: float,
) -> np.ndarray:
    """Detecta QRS; la salida exige control de calidad y revisión visual."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.size < round(2 * sampling_frequency_hz):
        raise ValueError("Se requieren al menos dos segundos de ECG.")
    if not np.all(np.isfinite(values)):
        raise ValueError("El ECG contiene valores no finitos.")
    return processing.xqrs_detect(
        sig=values,
        fs=sampling_frequency_hz,
        verbose=False,
    )
