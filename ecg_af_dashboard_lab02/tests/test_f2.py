import numpy as np
import pytest

from ecg_af_dashboard.annotations import (
    RhythmInterval,
    build_rhythm_intervals,
    calculate_af_load,
    calculate_intersection,
    merge_spans,
)


def test_build_rhythm_intervals_valid():
    """Verifica la correcta reconstrucción de intervalos cuando empieza en la muestra
    0."""
    samples = np.array([0, 250, 500])
    notes = ("(N", "(AFIB", "(N")
    signal_length = 750
    intervals = build_rhythm_intervals(samples, notes, signal_length)

    assert len(intervals) == 3
    assert intervals[0].start_sample == 0
    assert intervals[0].end_sample == 250
    assert intervals[0].label == "OTHER"  # Mapeo de (N a OTHER
    assert intervals[1].label == "AF"  # Mapeo de (AFIB a AF


def test_build_rhythm_intervals_missing_zero():
    """Verifica que se inserte un intervalo 'UNKNOWN' si el registro no empieza en 0."""
    samples = np.array([100, 300])
    notes = ("(AFIB", "(N")
    signal_length = 500
    intervals = build_rhythm_intervals(samples, notes, signal_length)

    assert intervals[0].start_sample == 0
    assert intervals[0].end_sample == 100
    assert intervals[0].label == "UNKNOWN"
    assert intervals[1].start_sample == 100
    assert intervals[1].end_sample == 300
    assert intervals[1].label == "AF"


def test_calculate_intersection_limits():
    """Prueba los límites y casos borde de la intersección temporal."""
    # Solapamiento total
    assert calculate_intersection(0.0, 10.0, 0.0, 10.0) == 10.0
    # Sin solapamiento (separados)
    assert calculate_intersection(0.0, 5.0, 6.0, 10.0) == 0.0
    # Solapamiento parcial (ventana empieza dentro del intervalo)
    assert calculate_intersection(2.0, 8.0, 0.0, 5.0) == 3.0


def _three_block_intervals():
    """OTHER 0-10 s, AF 10-20 s, OTHER 20-30 s a 250 Hz."""
    return [
        RhythmInterval(0, 2500, "OTHER", "(N"),
        RhythmInterval(2500, 5000, "AF", "(AFIB"),
        RhythmInterval(5000, 7500, "OTHER", "(N"),
    ]


def test_calculate_af_load_boundary():
    """La ventana corta un episodio a la mitad: no debe sumarse completo."""
    # Ventana de 15 s a 25 s: 5 s de AF y 5 s de OTHER.
    result = calculate_af_load(_three_block_intervals(), (3750, 6250), 250.0)

    assert result.selectable_time_s == 10.0
    assert result.analyzable_time_s == 10.0
    assert result.af_time_s == 5.0
    assert result.af_load == 0.5
    assert result.other_time_s == 5.0
    assert result.unknown_time_s == 0.0


def test_calculate_af_load_excludes_by_quality():
    """El tiempo excluido reduce el analizable y cambia el denominador."""
    # Se excluyen 2 s (500 muestras) que caen dentro del tramo de AF.
    result = calculate_af_load(
        _three_block_intervals(),
        (3750, 6250),
        250.0,
        excluded_spans=[(4000, 4500)],
    )

    assert result.selectable_time_s == 10.0
    assert result.excluded_time_s == 2.0
    assert result.analyzable_time_s == 8.0
    assert result.af_time_s == 3.0
    assert result.af_load == 3.0 / 8.0


def test_calculate_af_load_gap_counts_as_unknown():
    """El tiempo analizable sin anotación se reporta como desconocido."""
    intervals = [RhythmInterval(0, 1250, "AF", "(AFIB")]  # solo 0-5 s
    result = calculate_af_load(intervals, (0, 2500), 250.0)

    assert result.af_time_s == 5.0
    assert result.unknown_time_s == 5.0
    assert result.af_load == 0.5


def test_merge_spans_overlapping():
    """Los tramos excluidos que se solapan no deben contarse dos veces."""
    assert merge_spans([(0, 10), (5, 20), (30, 40)]) == [(0, 20), (30, 40)]


def test_calculate_af_load_invalid_window():
    """Verifica que se lance ValueError si la ventana es invertida o nula."""
    intervals = [RhythmInterval(0, 2500, "AF", "(AFIB")]
    with pytest.raises(ValueError, match="El fin de la ventana debe ser mayor"):
        calculate_af_load(intervals, (2500, 1250), 250.0)
