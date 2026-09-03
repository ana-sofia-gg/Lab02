from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RhythmInterval:
    start_sample: int
    end_sample: int
    label: str
    original_note: str


def normalize_rhythm(note: str) -> str:
    cleaned = note.strip().lstrip("(").upper()
    mapping = {"AFIB": "AF", "AFL": "AFL", "J": "J", "N": "OTHER"}
    return mapping.get(cleaned, "UNKNOWN")


def build_rhythm_intervals(
    samples: np.ndarray,
    notes: tuple[str, ...],
    signal_length: int,
) -> list[RhythmInterval]:
    samples = np.asarray(samples, dtype=int)
    if samples.ndim != 1 or samples.size != len(notes):
        raise ValueError("Muestras y notas de ritmo no concuerdan.")
    if samples.size == 0:
        raise ValueError("Se requiere una anotación de ritmo desde la muestra 0.")
    if np.any(np.diff(samples) <= 0):
        raise ValueError("Las anotaciones deben ser estrictamente crecientes.")
    if samples[-1] >= signal_length:
        raise ValueError("Una anotación está fuera del registro.")

    # Si el primer ritmo no empieza en 0, se documenta el intervalo inicial sin
    # etiqueta.
    current_samples = list(samples)
    current_notes = list(notes)

    if current_samples[0] > 0:
        # Reasignar la enumeración de las muestras de forma que se inserte un cero en la
        # posición cero.
        current_samples.insert(0, 0)
        # Reasignar la enumeración de las notas de forma que se inserte una etiqueta no
        # específica en la posición cero.
        current_notes.insert(0, "UNKNOWN")

    # np.r_[ ... ]: Concatenar elementos en una sola dimensión.
    ends = np.r_[current_samples[1:], signal_length]

    return [
        RhythmInterval(
            start_sample=int(start),
            end_sample=int(end),
            label=normalize_rhythm(note),
            original_note=note,
        )
        for start, end, note in zip(current_samples, ends, current_notes, strict=True)
    ]


@dataclass(frozen=True)
class AFLoadResult:
    """Reparto temporal de una ventana según el ritmo anotado (Actividad 2.3).

    Todos los tiempos están en segundos. `af_load` es una proporción
    adimensional en [0, 1] calculada sobre el tiempo analizable, no sobre el
    seleccionable: excluir tramos por calidad no debe inflar ni desinflar
    artificialmente la carga.

    Las etiquetas AFL, J, OTHER y UNKNOWN se reportan por separado. Agruparlas
    en un único "no-FA" ocultaría que flutter y ritmo de la unión no son ritmo
    sinusal.
    """

    selectable_time_s: float
    excluded_time_s: float
    analyzable_time_s: float
    af_time_s: float
    af_load: float
    afl_time_s: float
    j_time_s: float
    other_time_s: float
    unknown_time_s: float


def calculate_intersection(
    start1: float, end1: float, start2: float, end2: float
) -> float:
    """Longitud del solapamiento entre dos intervalos; 0.0 si no se tocan."""
    inter_start = max(start1, start2)
    inter_end = min(end1, end2)
    return max(0.0, inter_end - inter_start)


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Fusiona tramos solapados para no contar dos veces el mismo tiempo."""
    ordered = sorted((int(s), int(e)) for s, e in spans if e > s)
    merged: list[tuple[int, int]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _excluded_within(start: int, end: int, excluded: list[tuple[int, int]]) -> float:
    """Cantidad de muestras excluidas que caen dentro de [start, end)."""
    return sum(
        calculate_intersection(start, end, ex_s, ex_e) for ex_s, ex_e in excluded
    )


def calculate_af_load(
    intervals: list[RhythmInterval],
    window: tuple[int, int],
    sampling_frequency_hz: float,
    excluded_spans: list[tuple[int, int]] | None = None,
) -> AFLoadResult:
    """Calcula el reparto temporal y la carga anotada de FA en una ventana.

    `window` y `excluded_spans` se expresan en índices de muestra, igual que
    `RhythmInterval`. La conversión a segundos ocurre una sola vez, al final,
    usando la frecuencia leída del encabezado.

    `excluded_spans` son los tramos retirados por la política de calidad. Es
    la única razón admitida para reducir el tiempo analizable.
    """
    win_start, win_end = int(window[0]), int(window[1])
    if win_end <= win_start:
        raise ValueError("El fin de la ventana debe ser mayor que el inicio.")
    if not np.isfinite(sampling_frequency_hz) or sampling_frequency_hz <= 0:
        raise ValueError("La frecuencia de muestreo debe ser finita y positiva.")

    excluded = merge_spans(excluded_spans or [])

    selectable = float(win_end - win_start)
    excluded_total = _excluded_within(win_start, win_end, excluded)
    analyzable = selectable - excluded_total

    by_label = {"AF": 0.0, "AFL": 0.0, "J": 0.0, "OTHER": 0.0, "UNKNOWN": 0.0}

    for interval in intervals:
        overlap_start = max(win_start, interval.start_sample)
        overlap_end = min(win_end, interval.end_sample)
        if overlap_end <= overlap_start:
            continue
        net = (overlap_end - overlap_start) - _excluded_within(
            overlap_start, overlap_end, excluded
        )
        label = interval.label if interval.label in by_label else "UNKNOWN"
        by_label[label] += float(net)

    # El tiempo analizable que ninguna anotación cubre se reporta como
    # desconocido; no se reparte entre las demás etiquetas.
    gap = max(0.0, analyzable - sum(by_label.values()))
    by_label["UNKNOWN"] += gap

    af_load = (by_label["AF"] / analyzable) if analyzable > 0 else 0.0
    fs = float(sampling_frequency_hz)

    return AFLoadResult(
        selectable_time_s=selectable / fs,
        excluded_time_s=excluded_total / fs,
        analyzable_time_s=analyzable / fs,
        af_time_s=by_label["AF"] / fs,
        af_load=af_load,
        afl_time_s=by_label["AFL"] / fs,
        j_time_s=by_label["J"] / fs,
        other_time_s=by_label["OTHER"] / fs,
        unknown_time_s=by_label["UNKNOWN"] / fs,
    )
