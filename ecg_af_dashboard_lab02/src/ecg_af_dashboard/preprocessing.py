import numpy as np
from scipy.signal import butter, sosfiltfilt


def bandpass_zero_phase(
    values: np.ndarray,
    sampling_frequency_hz: float,
    low_hz: float,
    high_hz: float,
    order: int = 4,
) -> np.ndarray:
    """Filtra ECG fuera de línea; no representa procesamiento causal."""
    values = np.asarray(values, dtype=float)
    nyquist_hz = sampling_frequency_hz / 2.0
    if values.ndim != 1 or values.size == 0:
        raise ValueError("La señal debe ser un vector no vacío.")
    if not np.all(np.isfinite(values)):
        raise ValueError("La señal contiene valores no finitos.")
    if not 0.0 < low_hz < high_hz < nyquist_hz:
        raise ValueError("Debe cumplirse 0 < low < high < fs/2.")
    if not isinstance(order, int) or order < 1:
        raise ValueError("El orden debe ser un entero positivo.")

    sections = butter(
        order,
        [low_hz, high_hz],
        btype="bandpass",
        fs=sampling_frequency_hz,
        output="sos",
    )
    try:
        return sosfiltfilt(sections, values)
    except ValueError as error:
        raise ValueError("La ventana es demasiado corta para el filtro.") from error
