import numpy as np
import pytest

from ecg_af_dashboard.annotations import RhythmInterval
from ecg_af_dashboard.rr import (
    REASON_NON_PHYSIOLOGICAL,
    REASON_QUALITY,
    REASON_TRANSITION,
    build_rr_intervals,
    label_at_sample,
    summarize_by_rhythm,
    summarize_rr,
)

FS = 250.0


def _two_rhythm_blocks():
    """OTHER de 0 a 1000, AF de 1000 a 2000 (muestras)."""
    return [
        RhythmInterval(0, 1000, "OTHER", "(N"),
        RhythmInterval(1000, 2000, "AF", "(AFIB"),
    ]


# ── label_at_sample ────────────────────────────────────────────────────────


def test_label_at_sample_inside_and_outside():
    """Fuera de todo intervalo anotado la etiqueta es UNKNOWN, no la vecina."""
    intervals = _two_rhythm_blocks()
    assert label_at_sample(0, intervals) == "OTHER"
    assert label_at_sample(999, intervals) == "OTHER"
    assert label_at_sample(1000, intervals) == "AF"
    assert label_at_sample(2000, intervals) == "UNKNOWN"
    assert label_at_sample(5000, intervals) == "UNKNOWN"


# ── Contratos de entrada ───────────────────────────────────────────────────


def test_build_rr_rejects_non_increasing_qrs():
    """Las detecciones deben venir ya ordenadas y sin duplicados."""
    qrs = np.array([100, 300, 300, 500])
    with pytest.raises(ValueError, match="estrictamente crecientes"):
        build_rr_intervals(qrs, _two_rhythm_blocks(), FS)


def test_build_rr_rejects_float_qrs():
    """Los índices de muestra deben ser enteros, no flotantes."""
    qrs = np.array([100.0, 300.0])
    with pytest.raises(ValueError, match="índices enteros"):
        build_rr_intervals(qrs, _two_rhythm_blocks(), FS)


def test_build_rr_rejects_invalid_sampling_frequency():
    """Una frecuencia no positiva invalida toda conversión a segundos."""
    qrs = np.array([100, 300])
    with pytest.raises(ValueError, match="finita y positiva"):
        build_rr_intervals(qrs, _two_rhythm_blocks(), 0.0)


# ── Construcción y exclusiones ─────────────────────────────────────────────


def test_build_rr_accepts_within_single_rhythm():
    """Tres QRS dentro del mismo ritmo producen dos RR aceptados."""
    qrs = np.array([100, 350, 600])
    result = build_rr_intervals(qrs, _two_rhythm_blocks(), FS)

    assert result.counts["total_pairs"] == 2
    assert result.counts["accepted"] == 2
    assert result.counts["accepted_OTHER"] == 2
    assert [rr.duration_s for rr in result.included] == [1.0, 1.0]


def test_build_rr_excludes_interval_crossing_transition():
    """Un RR con extremos en ritmos distintos no representa a ninguno."""
    # 900 está en OTHER y 1100 en AF: el par cruza la transición.
    qrs = np.array([700, 900, 1100, 1300])
    result = build_rr_intervals(qrs, _two_rhythm_blocks(), FS)

    assert result.counts[REASON_TRANSITION] == 1
    assert result.counts["accepted"] == 2
    crossing = [rr for rr in result.intervals if not rr.included]
    assert crossing[0].exclusion_reason == REASON_TRANSITION
    assert crossing[0].start_sample == 900


def test_build_rr_excludes_by_quality_mask():
    """Una muestra no válida dentro del tramo descarta el intervalo completo."""
    qrs = np.array([100, 350, 600])
    mask = np.ones(2000, dtype=bool)
    mask[200:210] = False  # cae dentro del primer RR

    result = build_rr_intervals(qrs, _two_rhythm_blocks(), FS, quality_mask=mask)

    assert result.counts[REASON_QUALITY] == 1
    assert result.counts["accepted"] == 1
    assert result.intervals[0].exclusion_reason == REASON_QUALITY


def test_quality_takes_precedence_over_transition():
    """Cuando concurren dos causas se atribuye la primera del orden definido."""
    qrs = np.array([900, 1100])
    mask = np.ones(2000, dtype=bool)
    mask[1000] = False

    result = build_rr_intervals(qrs, _two_rhythm_blocks(), FS, quality_mask=mask)

    assert result.counts[REASON_QUALITY] == 1
    assert result.counts[REASON_TRANSITION] == 0


def test_physiological_limits_are_off_by_default():
    """Un RR muy largo se conserva si no se fijaron límites explícitos."""
    qrs = np.array([0, 900])  # 3.6 s
    result = build_rr_intervals(qrs, _two_rhythm_blocks(), FS)

    assert result.counts["accepted"] == 1
    assert result.counts[REASON_NON_PHYSIOLOGICAL] == 0


def test_physiological_limits_when_enabled():
    """Con límites activos, el RR fuera de rango se descarta con su causa."""
    qrs = np.array([0, 900])
    result = build_rr_intervals(
        qrs,
        _two_rhythm_blocks(),
        FS,
        physiological_rr_min_s=0.3,
        physiological_rr_max_s=2.0,
    )

    assert result.counts[REASON_NON_PHYSIOLOGICAL] == 1
    assert result.counts["accepted"] == 0


def test_build_rr_labels_unannotated_region_as_unknown():
    """Un RR fuera de todo intervalo anotado se etiqueta UNKNOWN, no OTHER."""
    qrs = np.array([2100, 2350])
    result = build_rr_intervals(qrs, _two_rhythm_blocks(), FS)

    assert result.counts["accepted_UNKNOWN"] == 1
    assert result.included[0].label == "UNKNOWN"


# ── Descriptores ───────────────────────────────────────────────────────────


def test_summarize_rr_requires_three_intervals():
    """Con menos de tres RR no se calculan descriptores."""
    with pytest.raises(ValueError, match="al menos tres"):
        summarize_rr(np.array([0.8, 0.9]))


def test_summarize_rr_rejects_non_positive():
    """Un RR nulo o negativo indica un error de construcción, no un dato."""
    with pytest.raises(ValueError, match="finitos y positivos"):
        summarize_rr(np.array([0.8, 0.0, 0.9]))


def test_summarize_rr_constant_series_has_zero_dispersion():
    """Una serie constante tiene SDNN, CV y RMSSD nulos."""
    summary = summarize_rr(np.array([0.8, 0.8, 0.8, 0.8]))

    assert summary["count"] == 4
    assert summary["mean_rr_s"] == pytest.approx(0.8)
    assert summary["median_rr_s"] == pytest.approx(0.8)
    assert summary["iqr_rr_s"] == pytest.approx(0.0)
    assert summary["sdnn_s"] == pytest.approx(0.0)
    assert summary["cv_rr"] == pytest.approx(0.0)
    assert summary["rmssd_s"] == pytest.approx(0.0)


def test_summarize_rr_known_values():
    """Comprueba los descriptores contra valores calculados a mano."""
    rr = np.array([0.8, 1.0, 0.6, 1.0])
    summary = summarize_rr(rr)

    assert summary["mean_rr_s"] == pytest.approx(0.85)
    # Diferencias sucesivas: +0.2, -0.4, +0.4 -> RMSSD = sqrt(0.36/3)
    assert summary["rmssd_s"] == pytest.approx(np.sqrt(0.12))
    assert summary["sdnn_s"] == pytest.approx(np.std(rr, ddof=1))
    assert summary["cv_rr"] == pytest.approx(summary["sdnn_s"] / 0.85)


def test_summarize_by_rhythm_flags_insufficient_windows():
    """Por debajo del mínimo analítico se avisa en vez de reportar números."""
    qrs = np.arange(0, 1000, 250)  # 3 RR dentro de OTHER
    result = build_rr_intervals(qrs, _two_rhythm_blocks(), FS)

    summaries = summarize_by_rhythm(result, min_rr_for_summary=30)

    assert summaries["OTHER"]["sufficient"] is False
    assert summaries["OTHER"]["count"] == 3
    assert "amplíe la ventana" in summaries["OTHER"]["message"]
    assert summaries["AF"]["count"] == 0


def test_summarize_by_rhythm_reports_labels_separately():
    """AFL y J no se mezclan con OTHER en el resumen."""
    intervals = [RhythmInterval(0, 2000, "AFL", "(AFL")]
    qrs = np.arange(0, 1500, 250)
    result = build_rr_intervals(qrs, intervals, FS)

    summaries = summarize_by_rhythm(result, min_rr_for_summary=3)

    assert summaries["AFL"]["sufficient"] is True
    assert summaries["AFL"]["count"] == 5
    assert summaries["OTHER"]["count"] == 0
