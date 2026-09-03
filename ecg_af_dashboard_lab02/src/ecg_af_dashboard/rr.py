"""Intervalos RR válidos y descriptores de irregularidad (Fase 4).

Este módulo no clasifica ritmos ni emite conclusiones clínicas. Construye la
serie RR a partir de detecciones QRS ya controladas, registra por qué se
excluye cada intervalo, y resume la irregularidad de los que sobreviven.

Los descriptores (SDNN, RMSSD, CV) se interpretan como medidas de
irregularidad ventricular durante el segmento, no como estimación de
modulación autonómica: la FA altera la generación de la serie RR y hace
inapropiado trasladar interpretaciones de HRV obtenidas en ritmo sinusal.
"""

from bisect import bisect_right
from dataclasses import dataclass

import numpy as np

from ecg_af_dashboard.annotations import RhythmInterval

# Causas de exclusión, en el orden en que se evalúan. El orden importa porque
# a cada intervalo se le atribuye la primera causa que lo descarta.
REASON_QUALITY = "calidad_insuficiente"
REASON_TRANSITION = "cruza_transicion_de_ritmo"
REASON_NON_PHYSIOLOGICAL = "rr_fuera_de_limites"

RHYTHM_LABELS = ("AF", "AFL", "J", "OTHER", "UNKNOWN")


@dataclass(frozen=True)
class RRInterval:
    """Un intervalo RR con su procedencia y su destino."""

    start_sample: int
    end_sample: int
    duration_s: float
    label: str
    included: bool
    exclusion_reason: str | None


@dataclass(frozen=True)
class RRBuildResult:
    """Serie RR completa más el conteo de aceptados y descartados por causa."""

    intervals: list[RRInterval]
    counts: dict[str, int]

    @property
    def included(self) -> list[RRInterval]:
        """Solo los intervalos aceptados, en orden."""
        return [rr for rr in self.intervals if rr.included]

    def durations_s(self, label: str | None = None) -> np.ndarray:
        """Duraciones de los intervalos aceptados, opcionalmente de un ritmo."""
        selected = self.included
        if label is not None:
            selected = [rr for rr in selected if rr.label == label]
        return np.array([rr.duration_s for rr in selected], dtype=float)


def label_at_sample(sample: int, intervals: list[RhythmInterval]) -> str:
    """Etiqueta de ritmo vigente en una muestra.

    Devuelve UNKNOWN si la muestra cae fuera de todo intervalo anotado, en vez
    de inventar la etiqueta del intervalo más cercano.
    """
    starts = [interval.start_sample for interval in intervals]
    position = bisect_right(starts, sample) - 1
    if position < 0:
        return "UNKNOWN"
    candidate = intervals[position]
    if sample >= candidate.end_sample:
        return "UNKNOWN"
    return candidate.label


def _index_at_sample(sample: int, intervals: list[RhythmInterval]) -> int:
    """Índice del intervalo de ritmo que contiene la muestra; -1 si ninguno."""
    starts = [interval.start_sample for interval in intervals]
    position = bisect_right(starts, sample) - 1
    if position < 0 or sample >= intervals[position].end_sample:
        return -1
    return position


def build_rr_intervals(
    qrs_samples: np.ndarray,
    rhythm_intervals: list[RhythmInterval],
    sampling_frequency_hz: float,
    quality_mask: np.ndarray | None = None,
    physiological_rr_min_s: float | None = None,
    physiological_rr_max_s: float | None = None,
) -> RRBuildResult:
    """Construye la serie RR a partir de detecciones QRS ya controladas.

    Reglas aplicadas a cada par de QRS consecutivos, en este orden:

    1. Si `quality_mask` marca alguna muestra del tramo como no válida, se
       excluye por calidad.
    2. Si los dos QRS no pertenecen al mismo intervalo de ritmo, se excluye:
       un RR que cruza una transición no representa a ninguno de los dos
       ritmos.
    3. Si se fijaron límites fisiológicos y el RR queda fuera, se excluye.
       Estos límites están desactivados por defecto a propósito: descartar un
       RR por ser extremo puede borrar justamente la irregularidad que se
       estudia. La exclusión debe apoyarse en evidencia de detección o
       calidad, no en el resultado deseado.

    `quality_mask` es un arreglo booleano por muestra donde True significa
    válida.
    """
    qrs_samples = np.asarray(qrs_samples)
    if qrs_samples.ndim != 1:
        raise ValueError("Las detecciones QRS deben ser un vector unidimensional.")
    if not np.issubdtype(qrs_samples.dtype, np.integer):
        raise ValueError("Las detecciones QRS deben ser índices enteros.")
    if qrs_samples.size and np.any(np.diff(qrs_samples) <= 0):
        raise ValueError("Las detecciones QRS deben ser estrictamente crecientes.")
    if not np.isfinite(sampling_frequency_hz) or sampling_frequency_hz <= 0:
        raise ValueError("La frecuencia de muestreo debe ser finita y positiva.")
    if physiological_rr_min_s is not None and physiological_rr_max_s is not None:
        if physiological_rr_min_s >= physiological_rr_max_s:
            raise ValueError("El límite RR inferior debe ser menor que el superior.")

    fs = float(sampling_frequency_hz)
    counts = {
        "total_pairs": max(0, qrs_samples.size - 1),
        "accepted": 0,
        REASON_QUALITY: 0,
        REASON_TRANSITION: 0,
        REASON_NON_PHYSIOLOGICAL: 0,
    }
    counts.update({f"accepted_{label}": 0 for label in RHYTHM_LABELS})

    intervals: list[RRInterval] = []

    for start, end in zip(qrs_samples[:-1], qrs_samples[1:], strict=True):
        start, end = int(start), int(end)
        duration_s = (end - start) / fs
        reason: str | None = None

        if quality_mask is not None and not bool(np.all(quality_mask[start : end + 1])):
            reason = REASON_QUALITY

        index_start = _index_at_sample(start, rhythm_intervals)
        index_end = _index_at_sample(end, rhythm_intervals)
        if reason is None and index_start != index_end:
            reason = REASON_TRANSITION

        if reason is None:
            below = (
                physiological_rr_min_s is not None
                and duration_s < physiological_rr_min_s
            )
            above = (
                physiological_rr_max_s is not None
                and duration_s > physiological_rr_max_s
            )
            if below or above:
                reason = REASON_NON_PHYSIOLOGICAL

        label = label_at_sample(start, rhythm_intervals)
        included = reason is None
        if included:
            counts["accepted"] += 1
            counts[f"accepted_{label}"] += 1
        else:
            counts[reason] += 1

        intervals.append(
            RRInterval(
                start_sample=start,
                end_sample=end,
                duration_s=duration_s,
                label=label,
                included=included,
                exclusion_reason=reason,
            )
        )

    return RRBuildResult(intervals=intervals, counts=counts)


def summarize_rr(rr_s: np.ndarray) -> dict[str, float | int]:
    """Resume irregularidad RR sin emitir una clasificación clínica.

    Requiere al menos tres intervalos para poder ejecutarse. Ese mínimo
    técnico no equivale a un mínimo analítico: para comparar segmentos use
    `RRParams.min_rr_for_summary`, que es más exigente.
    """
    rr_s = np.asarray(rr_s, dtype=float)
    if rr_s.ndim != 1 or rr_s.size < 3:
        raise ValueError("Se requieren al menos tres intervalos RR válidos.")
    if not np.all(np.isfinite(rr_s)) or np.any(rr_s <= 0.0):
        raise ValueError("Los RR deben ser finitos y positivos.")

    differences_s = np.diff(rr_s)
    mean_rr_s = float(np.mean(rr_s))
    standard_deviation_s = float(np.std(rr_s, ddof=1))
    q25_s, median_s, q75_s = np.percentile(rr_s, [25, 50, 75])
    return {
        "count": int(rr_s.size),
        "mean_rr_s": mean_rr_s,
        "median_rr_s": float(median_s),
        "iqr_rr_s": float(q75_s - q25_s),
        "sdnn_s": standard_deviation_s,
        "cv_rr": standard_deviation_s / mean_rr_s,
        "rmssd_s": float(np.sqrt(np.mean(differences_s**2))),
    }


def summarize_by_rhythm(
    result: RRBuildResult,
    min_rr_for_summary: int,
) -> dict[str, dict]:
    """Descriptores por etiqueta de ritmo, con aviso si faltan intervalos.

    Cada etiqueta se reporta por separado. AFL y J no se mezclan con OTHER:
    la comparación principal recomendada es AF frente a OTHER, y agrupar
    silenciosamente flutter o ritmo de la unión dentro de "no-FA" haría esa
    comparación engañosa.
    """
    summaries: dict[str, dict] = {}
    for label in RHYTHM_LABELS:
        durations = result.durations_s(label)
        if durations.size < max(3, min_rr_for_summary):
            summaries[label] = {
                "count": int(durations.size),
                "sufficient": False,
                "message": (
                    f"Se requieren al menos {max(3, min_rr_for_summary)} "
                    "intervalos RR válidos; amplíe la ventana."
                ),
            }
            continue
        summary = summarize_rr(durations)
        summary["sufficient"] = True
        summaries[label] = summary
    return summaries
