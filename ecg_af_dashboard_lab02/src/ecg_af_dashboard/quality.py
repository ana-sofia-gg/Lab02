from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class QualityAssessment:
    # Clase para agrupar datos, que representan el resultado de la evaluación de calidad
    # de una señal.
    # Indicador 1 si la señal pasó las pruebas generales de calidad.
    is_acceptable: bool
    # Almacena los mensajes oficiales: "Calidad insuficiente para comparar" y "Ok"
    # Estos aparecerán luego aparecerá en la interfaz visual de Streamlit.
    status_message: str
    # Guarda la proporción numérica exacta de valores no finitos.
    non_finite_prop: float
    # Guarda la proporción de la señal que se salió del rango físico normal [mV].
    out_of_range_prop: float
    # Indica específicamente si la señal presentó o no una "línea plana" por cierto
    # tiempo.
    has_flatline: bool


def check_non_finite_prop(signal: np.ndarray) -> float:
    # Se calcula la proporción de valores no finitos (NaN) en la señal.
    # Revisión de la señal, ¿está vacía?
    if signal.size == 0:
        # Para evitar el error, en la división, y en float.
        return 0.0
    return float(np.sum(~np.isfinite(signal)) / signal.size)


def check_out_of_range_prop(
    signal: np.ndarray,
    min_val: float = -5.0,
    max_val: float = 5.0,
) -> float:
    # Fuente: https://pmc.ncbi.nlm.nih.gov/articles/PMC7664289/
    # Se establece que los valores de amplitud pueden ir hasta 5mV.
    if signal.size == 0:
        return 0.0
    # Se consideran solo valores finitos para evaluar el rango. Se filtran.
    valid_data_mask = signal[np.isfinite(signal)]
    # Si ningún valor es finito, el 100% está fuera de rango.
    if valid_data_mask.size == 0:
        return 1.0
    # | como un or
    out_of_bounds = (valid_data_mask < min_val) | (valid_data_mask > max_val)
    return float(np.sum(out_of_bounds) / valid_data_mask.size)


def check_flatline(
    signal: np.ndarray,
    sampling_rate: float,
    max_flat_duration: float = 1.2,
    tol: float = 1e-6,
) -> bool:
    # 60secs/100latidos = 0.6secs/latido
    # 60secs/50latidos = 1.2secs/latido
    # https://fundaciondelcorazon.com/prevencion/marcadores-de-riesgo/frecuencia-cardiaca.html

    # Verificación si la señal permanece plana durante una duración más grande a 1 sec.
    if signal.size == 0:
        return False
    # Convertir el tiempo límite en número de muestras.
    max_samples = int(max_flat_duration * sampling_rate)
    if max_samples <= 1:
        return False
    # Cálculo de la diferencia absoluta entre muestras consecutivas.
    diffs = np.abs(np.diff(signal))
    # Un valor es 'plano' si la diferencia con el anterior es prácticamente 0.
    # Revisión de si el cambio es menor a la tolerancia, dado el funcionamiento de los
    # computadores.
    is_flat = diffs < tol

    # Contador para llevar la cuenta de cuántos puntos se llevan de plano.
    current_run = 0
    # Guarda el número más alto de puntos en señal plana más larga encontrada.
    max_run = 0
    for flat in is_flat:
        if flat:  # True
            current_run += 1
            if current_run > max_run:
                max_run = current_run
        else:
            current_run = 0
    # Retorna True o False, dependiendo si hay un espacio plano excesivo.
    return max_run >= max_samples


def evaluate_signal_quality(
    signal: np.ndarray,
    sampling_rate: float,
    max_non_finite_prop: float = 0.01,  # Umbral: máximo 1% de NaNs.
    max_out_of_range_prop: float = 0.02,  # Umbral: máximo 2% fuera del rango físico.
    max_flat_duration_sec: float = 1.2,  # Umbral: máximo 1.2 segundos.
) -> QualityAssessment:
    # Evaluación de la calidad global de la señal aplicando los tres indicadores.
    non_finite_prop = check_non_finite_prop(signal)
    out_of_range_prop = check_out_of_range_prop(signal)
    has_flatline = check_flatline(signal, sampling_rate, max_flat_duration_sec)

    # Evaluación de umbrales.
    if (
        non_finite_prop > max_non_finite_prop
        or out_of_range_prop > max_out_of_range_prop
    ):
        return QualityAssessment(
            is_acceptable=False,
            status_message="Calidad insuficiente para comparar",
            non_finite_prop=non_finite_prop,
            out_of_range_prop=out_of_range_prop,
            has_flatline=has_flatline,
        )

    if has_flatline:
        return QualityAssessment(
            is_acceptable=False,
            status_message="Requiere revisión, respecto a las líneas planas",
            non_finite_prop=non_finite_prop,
            out_of_range_prop=out_of_range_prop,
            has_flatline=has_flatline,
        )

    return QualityAssessment(
        is_acceptable=True,
        status_message="OK",
        non_finite_prop=non_finite_prop,
        out_of_range_prop=out_of_range_prop,
        has_flatline=has_flatline,
    )


def flat_run_mask(
    signal: np.ndarray,
    sampling_rate: float,
    max_flat_duration: float = 1.2,
    tol: float = 1e-6,
) -> np.ndarray:
    # Marca las muestras que pertenecen a un tramo plano prolongado.
    # check_flatline responde si existe; esta función dice dónde, que es lo
    # que se necesita para excluir los RR que lo cruzan.
    values = np.asarray(signal, dtype=float)
    flat = np.zeros(values.size, dtype=bool)
    if values.size < 2:
        return flat
    min_samples = int(max_flat_duration * sampling_rate)
    if min_samples <= 1:
        return flat

    is_flat = np.abs(np.diff(values)) < tol
    run_start = None
    for i, step in enumerate(is_flat):
        if step:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= min_samples:
                flat[run_start : i + 1] = True
            run_start = None
    if run_start is not None and (is_flat.size - run_start) >= min_samples:
        flat[run_start:] = True
    return flat


def build_quality_mask(
    signal: np.ndarray,
    min_val: float = -5.0,
    max_val: float = 5.0,
    sampling_rate: float | None = None,
    max_flat_duration: float = 1.2,
) -> np.ndarray:
    # Máscara por muestra: True donde la muestra es utilizable.
    # Una muestra se descarta por no ser finita, por salirse del rango físico
    # documentado o por caer en un tramo plano, nunca por el resultado que
    # produzca. Sin sampling_rate no se evalúa el tramo plano.
    values = np.asarray(signal, dtype=float)
    finite = np.isfinite(values)
    in_range = np.zeros_like(finite)
    in_range[finite] = (values[finite] >= min_val) & (values[finite] <= max_val)
    mask = finite & in_range
    if sampling_rate is not None:
        mask &= ~flat_run_mask(values, sampling_rate, max_flat_duration)
    return mask
