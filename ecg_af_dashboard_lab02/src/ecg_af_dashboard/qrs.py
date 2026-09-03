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


def check_qrs_channel_disagreement(
    record_signal: np.ndarray,
    sampling_frequency_hz: float,
    start_sample: int,
    end_sample: int,
    disagreement_threshold_pct: float = 25.0,
) -> dict:
    """Evalúa el desacuerdo de detecciones QRS entre los canales disponibles

    en una ventana específica para detectar inconsistencias multicanal.
    """
    record_signal = np.asarray(record_signal, float)
    if record_signal.ndim != 2:
        raise ValueError("La señal del registro debe ser bidimensional (muestras x canales).")
    
    num_channels = record_signal.shape[1]
    channel_counts = {}

    for i in range(num_channels):
        raw_ch = record_signal[start_sample:end_sample, i]
        clean_ch = np.where(np.isfinite(raw_ch), raw_ch, 0.0)
        try:
            peaks = detect_qrs_xqrs(clean_ch, sampling_frequency_hz)
            channel_counts[i] = len(peaks)
        except Exception:
            channel_counts[i] = 0

    counts_list = list(channel_counts.values())
    if not counts_list or max(counts_list) == 0:
        return {"disagreement_flag": False, "max_diff_pct": 0.0, "counts": channel_counts}

    min_c = min(counts_list)
    max_c = max(counts_list)
    
    diff_pct = ((max_c - min_c) / max(max_c, 1)) * 100.0
    has_disagreement = diff_pct > disagreement_threshold_pct

    return {
        "disagreement_flag": has_disagreement,
        "max_diff_pct": diff_pct,
        "counts": channel_counts,
    }
