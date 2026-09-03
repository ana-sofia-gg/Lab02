import numpy as np
import pytest

from ecg_af_dashboard.qrs import detect_qrs_xqrs


def test_detect_qrs_short_signal():
    """Verifica que se lance un ValueError si la señal dura menos de 2 segundos."""
    fs = 250.0
    # 1 segundo de señal (menor al requisito de 2 segundos)
    short_signal = np.zeros(int(fs * 1.0))
    with pytest.raises(ValueError, match="Se requieren al menos dos segundos"):
        detect_qrs_xqrs(short_signal, fs)


def test_detect_qrs_non_finite():
    """Verifica que se lance un ValueError si la señal contiene NaNs o valores
    infinitos."""
    fs = 250.0
    signal = np.sin(np.linspace(0, 10, int(fs * 3)))
    signal[100] = np.nan
    with pytest.raises(ValueError, match="El ECG contiene valores no finitos"):
        detect_qrs_xqrs(signal, fs)


def test_detect_qrs_invalid_dimension():
    """Verifica que se lance un ValueError si la señal no es un vector
    unidimensional."""
    fs = 250.0
    signal_2d = np.zeros((5, int(fs * 3)))
    with pytest.raises(ValueError):
        detect_qrs_xqrs(signal_2d, fs)


def test_detect_qrs_execution():
    """Verifica que la función ejecute el detector de wfdb correctamente y retorne un
    arreglo numpy."""
    fs = 250.0
    # Creación de 3 segundos de una señal base con picos marcados simulados
    t = np.linspace(0, 3, int(fs * 3))
    signal = np.sin(2 * np.pi * 1.5 * t)
    signal[int(fs * 1.0)] = 5.0  # Simulación de pico QRS en t=1.0s
    signal[int(fs * 2.0)] = 5.0  # Simulación de pico QRS en t=2.0s

    peaks = detect_qrs_xqrs(signal, fs)
    assert isinstance(peaks, np.ndarray)
