import numpy as np

from ecg_af_dashboard.quality import evaluate_signal_quality


def test_signal_quality_ok():
    # Se prueba una señal limpia y dentro de parámetros normales.
    sampling_rate = 250.0
    # Simulación de una señal normal que dura 2 segundos.
    t = np.linspace(0, 2, int(sampling_rate * 2))
    clean_signal = np.sin(2 * np.pi * 1.5 * t)  # Rango entre -1 y 1.

    result = evaluate_signal_quality(clean_signal, sampling_rate)

    assert result.is_acceptable is True
    assert result.status_message == "OK"
    assert result.has_flatline is False


def test_signal_quality_NANs():
    # Validación con una señal que supera el 1% de valores no finitos (NaNs).
    sampling_rate = 250.0
    signal = np.array([1.0, 2.0, 3.0, 4.0] * 100)
    # Adición de un 10% de NaNs (supera el umbral del 1%)
    signal[::10] = np.nan

    result = evaluate_signal_quality(signal, sampling_rate)

    assert result.is_acceptable is False
    assert result.status_message == "Calidad insuficiente para comparar"
    assert result.non_finite_prop > 0.01


def test_evaluate_signal_quality_flatline():
    # Verificación de una línea plana mayor a 1.2 segundos.
    sampling_rate = 100.0
    # Creación de 1.5 segundos de puros ceros.
    flat_signal = np.zeros(int(sampling_rate * 1.5))

    result = evaluate_signal_quality(flat_signal, sampling_rate)

    assert result.is_acceptable is False
    assert result.status_message == "Requiere revisión, respecto a las líneas planas"
    assert result.has_flatline is True
