import numpy as np
import pytest

from ecg_af_dashboard.annotations import RhythmInterval
from ecg_af_dashboard.rr import build_rr_intervals
from ecg_af_dashboard.visualization import (
    build_ecg_figure,
    build_poincare_figure,
    build_rhythm_timeline_figure,
    build_rr_histogram_figure,
    build_tachogram_figure,
    minmax_envelope,
    rhythm_display_name,
)

FS = 250.0

# Estas pruebas verifican contratos estructurales: unidades declaradas,
# procedencia visible y número de series. No demuestran legibilidad, honestidad
# de escala ni alineación clínica; eso exige revisión humana.


# ── Figura de ECG ──────────────────────────────────────────────────────────


def test_ecg_figure_has_units_qrs_and_reference_label():
    """Contrato de la Actividad 5.2: tres series, unidades y etiqueta visible."""
    time_s = np.array([0.0, 0.5, 1.0])
    raw_mv = np.array([0.0, 1.0, 0.0])
    processed_mv = np.array([0.1, 0.8, 0.1])
    qrs_local = np.array([1])

    figure = build_ecg_figure(
        time_s,
        raw_mv,
        processed_mv,
        qrs_local,
        channel="ECG1",
        rhythm_label="AF anotada",
    )

    assert len(figure.data) == 3
    assert figure.layout.xaxis.title.text == "Tiempo [s]"
    assert "mV" in figure.layout.yaxis.title.text
    assert "AF anotada" in figure.layout.title.text


def test_ecg_figure_translates_internal_label():
    """La etiqueta interna AF se presenta como «FA anotada», nunca «positivo»."""
    time_s = np.linspace(0, 1, 5)
    raw_mv = np.zeros(5)

    figure = build_ecg_figure(
        time_s, raw_mv, None, np.array([], dtype=int), "ECG1", "AF"
    )

    assert "FA anotada" in figure.layout.title.text
    assert "positivo" not in figure.layout.title.text.lower()


def test_ecg_figure_without_processed_or_qrs_has_one_trace():
    """Sin señal procesada ni marcas, queda una sola serie."""
    time_s = np.linspace(0, 1, 5)
    raw_mv = np.zeros(5)

    figure = build_ecg_figure(
        time_s, raw_mv, None, np.array([], dtype=int), "ECG2", "OTHER"
    )

    assert len(figure.data) == 1
    assert figure.data[0].name == "ECG físico"


def test_ecg_figure_rejects_qrs_outside_window():
    """Un índice QRS fuera de la ventana es un error de conversión, no un dato."""
    time_s = np.linspace(0, 1, 5)
    raw_mv = np.zeros(5)

    with pytest.raises(ValueError, match="fuera de la ventana"):
        build_ecg_figure(time_s, raw_mv, None, np.array([9]), "ECG1", "AF")


def test_ecg_figure_rejects_length_mismatch():
    """El eje temporal y la señal deben tener la misma longitud."""
    with pytest.raises(ValueError, match="deben coincidir"):
        build_ecg_figure(
            np.linspace(0, 1, 5),
            np.zeros(4),
            None,
            np.array([], dtype=int),
            "ECG1",
            "AF",
        )


def test_ecg_figure_accepts_declared_units():
    """La unidad se declara, no se supone."""
    time_s = np.linspace(0, 1, 5)
    figure = build_ecg_figure(
        time_s, np.zeros(5), None, np.array([], dtype=int), "ECG1", "AF", units="uV"
    )

    assert "uV" in figure.layout.yaxis.title.text


# ── Reducción para pantalla ────────────────────────────────────────────────


def test_minmax_envelope_keeps_short_series_intact():
    """Si la serie ya cabe, no se toca."""
    time_s = np.linspace(0, 1, 100)
    values = np.sin(time_s)

    envelope = minmax_envelope(time_s, values, max_points=4000)

    assert envelope.reduced is False
    assert envelope.values.size == 100


def test_minmax_envelope_preserves_extremes():
    """La reducción conserva el pico aunque descarte la mayoría de puntos."""
    total = 50_000
    time_s = np.linspace(0, 200, total)
    values = np.zeros(total)
    values[12_345] = 5.0  # pico breve que no debe desaparecer
    values[40_000] = -3.0

    envelope = minmax_envelope(time_s, values, max_points=1000)

    assert envelope.reduced is True
    assert envelope.original_points == total
    assert envelope.values.size <= 1000
    assert envelope.values.max() == pytest.approx(5.0)
    assert envelope.values.min() == pytest.approx(-3.0)


def test_minmax_envelope_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="misma longitud"):
        minmax_envelope(np.zeros(10), np.zeros(9))


# ── Cronología, tacograma, histograma y Poincaré ───────────────────────────


def _intervals():
    return [
        RhythmInterval(0, 1000, "OTHER", "(N"),
        RhythmInterval(1000, 2000, "AF", "(AFIB"),
    ]


def test_rhythm_timeline_declares_hours_and_record():
    """La cronología usa horas y nombra el registro."""
    figure = build_rhythm_timeline_figure(_intervals(), FS, "05091")

    assert figure.layout.xaxis.title.text == "Tiempo [h]"
    assert "05091" in figure.layout.title.text
    assert len(figure.data) == 2


def test_rhythm_timeline_rejects_invalid_frequency():
    with pytest.raises(ValueError, match="finita y positiva"):
        build_rhythm_timeline_figure(_intervals(), 0.0, "05091")


def test_tachogram_shows_excluded_intervals_separately():
    """Los RR excluidos aparecen como serie propia con su conteo."""
    # 900 -> 1100 cruza la transición de ritmo y queda excluido.
    qrs = np.array([200, 450, 700, 900, 1100, 1350])
    result = build_rr_intervals(qrs, _intervals(), FS)
    assert result.counts["accepted"] < result.counts["total_pairs"]

    figure = build_tachogram_figure(result, FS, "05091")

    names = [trace.name for trace in figure.data]
    assert any(name.startswith("Excluido") for name in names)
    assert figure.layout.yaxis.title.text == "Intervalo RR [s]"


def test_tachogram_can_hide_excluded():
    qrs = np.array([200, 450, 700, 900, 1100, 1350])
    result = build_rr_intervals(qrs, _intervals(), FS)

    figure = build_tachogram_figure(result, FS, "05091", show_excluded=False)

    assert all(not trace.name.startswith("Excluido") for trace in figure.data)


def test_histogram_keeps_labels_separate():
    """AFL no se funde con OTHER en el histograma."""
    series = {
        "OTHER": np.array([0.8, 0.82, 0.79]),
        "AFL": np.array([0.5, 0.52]),
    }

    figure = build_rr_histogram_figure(series, "05091")

    names = " ".join(trace.name for trace in figure.data)
    assert "No-FA anotado" in names
    assert "Flutter anotado" in names
    assert figure.layout.xaxis.title.text == "Intervalo RR [s]"


def test_histogram_skips_empty_series():
    series = {"AF": np.array([]), "OTHER": np.array([0.8, 0.9, 1.0])}

    figure = build_rr_histogram_figure(series, "05091")

    assert len(figure.data) == 1


def test_poincare_pairs_and_identity_line():
    """N intervalos producen N-1 puntos, más la línea de identidad."""
    series = {"AF": np.array([0.6, 0.9, 0.7, 1.1])}

    figure = build_poincare_figure(series, "05091")

    scatter = figure.data[0]
    assert len(scatter.x) == 3
    assert len(scatter.y) == 3
    assert scatter.x[1] == pytest.approx(0.9)
    assert scatter.y[1] == pytest.approx(0.7)
    assert figure.data[-1].name.startswith("Identidad")
    assert figure.layout.xaxis.title.text == "RRn [s]"


def test_poincare_ignores_series_too_short():
    figure = build_poincare_figure({"AF": np.array([0.8])}, "05091")

    assert all(not trace.name.startswith("FA anotada") for trace in figure.data)


# ── Nomenclatura ───────────────────────────────────────────────────────────


def test_display_names_avoid_diagnostic_wording():
    """Ninguna etiqueta visible usa lenguaje diagnóstico."""
    prohibited = ("positivo", "negativo", "diagnóstico", "detectada")
    for label in ("AF", "AFL", "J", "OTHER", "UNKNOWN"):
        text = rhythm_display_name(label).lower()
        assert all(word not in text for word in prohibited)
    assert rhythm_display_name("AF") == "FA anotada"
    assert rhythm_display_name("OTHER") == "No-FA anotado"


def test_ecg_figure_declares_record_in_title() -> None:
    """La figura debe llevar el registro dentro del objeto, no solo al lado en
    la página: si alguien exporta la figura sola, la procedencia viaja con
    ella (regla 1.6: cada figura indica registro, canal, unidad y tiempo)."""
    figure = build_ecg_figure(
        np.array([0.0, 0.5, 1.0]),
        np.array([0.0, 1.0, 0.0]),
        None,
        np.array([1]),
        channel="ECG1",
        rhythm_label="AF anotada",
        record_id="04043",
    )

    title = figure.layout.title.text
    assert "04043" in title
    assert "ECG1" in title
    assert "mV" in figure.layout.yaxis.title.text
