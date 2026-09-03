import numpy as np

from ecg_af_dashboard.preprocessing import bandpass_zero_phase
from ecg_af_dashboard.qrs import detect_qrs_xqrs
from ecg_af_dashboard.qrs_control import control_qrs_detections


def test_qrs_control():
    """Prueba de contrato para el control de detecciones QRS:
    verifica unicidad, orden, período refractario, límites y conteo de descartes.
    """
    fs = 250.0
    # Simulamos picos problemáticos: duplicados, desordenados, muy juntos, fuera de
    # rango
    raw_peaks = np.array([1000, 500, 500, 530, 2000, -50, 10000])
    signal_length = 5000

    result = control_qrs_detections(
        peak_indices=raw_peaks,
        signal_length=signal_length,
        sampling_frequency_hz=fs,
        min_rr_ms=200.0,  # 50 muestras a 250 Hz
    )

    # Verificar contratos de tipos de salida
    assert isinstance(result.valid_indices, np.ndarray)
    assert isinstance(result.counts, dict)

    # Verificar que los conteos lógicos cuadren con las causas esperadas
    assert result.counts["discarded_duplicates"] == 1  # El 500 duplicado
    assert result.counts["discarded_out_of_bounds"] == 2  # -50 y 10000
    # 530 está a 30 muestras de 500 (< 50)
    assert result.counts["discarded_refractory"] == 1
    assert result.counts["accepted"] == 3  # 500, 1000 y 2000

    # Comprobar que los índices devueltos son estrictamente crecientes y únicos
    assert np.all(np.diff(result.valid_indices) > 0)


def test_preprocessing_and_qrs():
    """Prueba de contrato del flujo completo: filtro de fase cero seguido de
    detección QRS."""
    fs = 250.0
    t = np.linspace(0, 4, int(fs * 4))
    # Señal sintética con onda base de baja frecuencia + picos limpios
    signal = np.sin(2 * np.pi * 0.2 * t)  # Deriva de línea base
    signal[int(fs * 1.0)] += 3.0  # Pico QRS en t=1.0s
    signal[int(fs * 2.5)] += 3.0  # Pico QRS en t=2.5s

    # 1. Aplicar filtro de fase cero
    filtered_signal = bandpass_zero_phase(signal, fs, low_hz=0.5, high_hz=40.0)
    assert filtered_signal.shape == signal.shape

    # 2. Detectar QRS sobre la señal filtrada
    peaks = detect_qrs_xqrs(filtered_signal, fs)
    assert isinstance(peaks, np.ndarray)
