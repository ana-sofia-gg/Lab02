from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class QRSControlResult:
    valid_indices: np.ndarray
    counts: dict[str, int]


def control_qrs_detections(
    peak_indices: np.ndarray,
    signal_length: int,
    sampling_frequency_hz: float,
    min_rr_ms: float = 200.0,
    quality_mask: np.ndarray = None,
) -> QRSControlResult:
    """Aplica filtros de control de calidad, límites y fisiología sobre los picos
    QRS."""
    counts = {
        "total_detected": len(peak_indices),
        "discarded_out_of_bounds": 0,
        "discarded_duplicates": 0,
        "discarded_refractory": 0,
        "discarded_poor_quality": 0,
        "accepted": 0,
    }

    if peak_indices.size == 0:
        return QRSControlResult(valid_indices=np.array([], dtype=int), counts=counts)

    # 1. Asegurar enteros, únicos y ordenados de forma creciente
    peaks = np.unique(np.asarray(peak_indices, dtype=int))
    peaks.sort()

    # Conteo de duplicados eliminados por unique
    duplicates_count = len(peak_indices) - len(peaks)
    counts["discarded_duplicates"] = duplicates_count

    valid = []
    min_samples_between_peaks = int((min_rr_ms / 1000.0) * sampling_frequency_hz)

    last_accepted = -999999

    for p in peaks:
        # 2. Marcas dentro de los límites de la señal
        if p < 0 or p >= signal_length:
            counts["discarded_out_of_bounds"] += 1
            continue

        # 3. Regla fisiológica: período refractario (intervalos improbables / doble
        # detección)
        if (p - last_accepted) < min_samples_between_peaks:
            counts["discarded_refractory"] += 1
            continue

        # 4. Exclusión en ventanas de calidad insuficiente (si se provee una máscara
        # booleana por muestra)
        if quality_mask is not None and not quality_mask[p]:
            counts["discarded_poor_quality"] += 1
            continue

        valid.append(p)
        last_accepted = p

    valid_arr = np.array(valid, dtype=int)
    counts["accepted"] = len(valid_arr)

    return QRSControlResult(valid_indices=valid_arr, counts=counts)
