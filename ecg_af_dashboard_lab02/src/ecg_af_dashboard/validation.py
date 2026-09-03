import numpy as np

from ecg_af_dashboard.annotations import normalize_rhythm
from ecg_af_dashboard.io import ECGRecord


def validate_ecg_record(record: ECGRecord) -> bool:
    """Valida la integridad temporal, estructural y de metadatos
    de un registro ECG según los criterios de la Actividad 1.4"""

    # I. Validación de la frecuencia de muestro (finita y positiva).
    fs = record.sampling_frequency_hz
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError(
            f"Frecuencia de muestreo inválida: {fs}. Debe ser finita y positiva."
        )

    # II. Validación de la matriz (bidimensional -muestra x canal-).
    if record.signal.ndim != 2:
        raise ValueError(
            "La señal debe ser bidimensional (muestras x canales), "
            f"tiene {record.signal.ndim} dimensiones."
        )

    num_samples, num_channels = record.signal.shape
    num_names = len(record.signal_names)
    num_units = len(record.units)

    # III. Validación de que el número de nombres y unidades coincida al número de
    # canales.
    if num_names != num_channels or num_units != num_channels:
        raise ValueError(
            f"El número de canales ({num_channels}) no coincide con los nombres "
            f"({num_names}) o unidades ({num_units}) proporcionados."
        )

    # IV. Comprobación que las muestras y posteriormente marcas de tiempo incrementan y
    # van en orden cronológico correcto.
    # Se verifica primero que la lista tenga más de un elemento con el cual se pueda
    # hacer una comparación.
    if len(record.rhythm_samples) > 1:
        # Se revisa que todas las restas entre los elementos sean mayores a 0.
        if not np.all(np.diff(record.rhythm_samples) > 0):
            raise ValueError("Las anotaciones de ritmo no están en orden ascendente.")

    # V. Validación respecto a la compatibilidad de la duración del ECG con número de
    # muestras y fs.
    expected_duration = num_samples / record.sampling_frequency_hz
    if expected_duration <= 0:
        raise ValueError("La duración calculada de la señal es cero o negativa.")

    # VI. Comprobación de la respectiva proporción de valores no finitos por canal
    # (NaN).
    # Se deben recorrer todos los canales, para analizar todo elemento en cada uno.
    for i in range(num_channels):
        # Extracción de toda la fila, en el canal analizado i.
        channel_data = record.signal[:, i]
        # Cuenta de los valores que no son finitos.
        non_finite_count = np.sum(~np.isfinite(channel_data))
        if non_finite_count > 0:
            # Cálculo de la proporción (# de valores defectuosos : # total de muestras
            # del canal)
            prop = non_finite_count / num_samples

            # Plus: Si supera el 50%, se podría advertir de la presencia de estos
            # valores.
            if prop > 0.5:
                print(
                    f"Advertencia: El canal {record.signal_names[i]} supera el 50% "
                    f"de valores no finitos ({prop * 100:.2f}%)."
                )

    # VII. Comprobación de la presencia de ventanas FA y no-FA en el conjunto de
    # anotaciones. Se reutiliza normalize_rhythm (annotations.py) en vez de comparar
    # substrings a mano, para no depender de la forma exacta de cada nota.
    normalized_labels = {normalize_rhythm(note) for note in record.rhythm_notes}
    FA_present = "AF" in normalized_labels
    N_present = "OTHER" in normalized_labels
    # Se exige que AMBAS etiquetas existan (no basta con que exista al menos una):
    # un registro solo-FA o solo-no-FA no permite la comparación que pide la guía.
    if not (FA_present and N_present):
        raise ValueError(
            "El registro no contiene tanto anotaciones de FA como de ritmo no-FA; "
            "no permite la comparación FA/no-FA requerida."
        )

    return True
