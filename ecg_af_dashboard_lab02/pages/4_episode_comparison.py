"""Vista 4. ¿Cuándo aparece FA anotada y cómo contrasta con no-FA?"""

import pandas as pd
import streamlit as st

from ecg_af_dashboard.config import PARAMETERS, RAW_DIR
from ecg_af_dashboard.rr import summarize_by_rhythm
from ecg_af_dashboard.ui import (
    analyze_window_cached,
    header_fingerprint,
    minimum_rr,
    page_setup,
    rhythm_intervals_cached,
)
from ecg_af_dashboard.visualization import (
    build_poincare_figure,
    build_rhythm_timeline_figure,
    rhythm_display_name,
)

record_id, record, analysis = page_setup("Episodios y comparación")

fs = analysis.sampling_frequency_hz
fingerprint = header_fingerprint(record_id)
intervals = rhythm_intervals_cached(str(RAW_DIR), record_id, fingerprint)
min_rr = minimum_rr()

# ── Cronología de episodios ────────────────────────────────────────────────

st.subheader("Cronología de ritmo anotado")
st.plotly_chart(
    build_rhythm_timeline_figure(intervals, fs, record_id),
    use_container_width=True,
)

# ── Carga anotada de la ventana vigente ────────────────────────────────────

st.subheader("Carga anotada de FA en la ventana seleccionada")

af_load = analysis.af_load
metrics = st.columns(4)
metrics[0].metric("Carga anotada de FA", f"{af_load.af_load * 100:.1f} %")
metrics[1].metric("Tiempo seleccionable", f"{af_load.selectable_time_s:.1f} s")
metrics[2].metric("Tiempo analizable", f"{af_load.analyzable_time_s:.1f} s")
metrics[3].metric("Tiempo en FA anotada", f"{af_load.af_time_s:.1f} s")

st.dataframe(
    pd.DataFrame(
        {
            "Etiqueta": [
                rhythm_display_name(label)
                for label in ("AF", "AFL", "J", "OTHER", "UNKNOWN")
            ],
            "Tiempo [s]": [
                round(af_load.af_time_s, 2),
                round(af_load.afl_time_s, 2),
                round(af_load.j_time_s, 2),
                round(af_load.other_time_s, 2),
                round(af_load.unknown_time_s, 2),
            ],
        }
    ),
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "Es **carga anotada de FA**: la proporción de tiempo analizable que las "
    "anotaciones de referencia marcan como (AFIB. No es una detección "
    "producida por esta aplicación. El denominador es el tiempo analizable, "
    "que descuenta solo los tramos retirados por la política de calidad."
)

# ── Selección de ventanas comparables ──────────────────────────────────────

st.subheader("Comparación FA / no-FA del mismo registro")


def longest_interval(label: str):
    """Episodio más largo con una etiqueta dada; None si no hay ninguno."""
    candidates = [item for item in intervals if item.label == label]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.end_sample - item.start_sample)


af_interval = longest_interval("AF")
other_interval = longest_interval("OTHER")

if af_interval is None or other_interval is None:
    st.error(
        "Este registro no tiene simultáneamente episodios FA y no-FA "
        "anotados. La comparación dentro del mismo registro no es posible; "
        "elija otro registro en la barra lateral."
    )
    st.stop()

af_length_s = (af_interval.end_sample - af_interval.start_sample) / fs
other_length_s = (other_interval.end_sample - other_interval.start_sample) / fs
maximum_s = int(min(af_length_s, other_length_s))

if maximum_s < 10:
    st.error(
        "Los episodios disponibles son demasiado cortos para construir "
        "ventanas comparables de al menos 10 s."
    )
    st.stop()

options = [value for value in (30, 60, 120, 300, 600) if value <= maximum_s]
if not options:
    options = [maximum_s]

duration_s = st.select_slider(
    "Duración de ambas ventanas [s]",
    options=options,
    value=options[-1],
    help=(
        f"Máximo posible sin salirse del episodio: {maximum_s} s. Las dos "
        "ventanas usan la misma duración para que la comparación sea "
        "equivalente."
    ),
)

length_samples = int(round(duration_s * fs))


def centered_window(interval) -> tuple[int, int]:
    """Ventana centrada dentro del episodio, sin cruzar sus bordes."""
    middle = (interval.start_sample + interval.end_sample) // 2
    start = max(interval.start_sample, middle - length_samples // 2)
    end = min(interval.end_sample, start + length_samples)
    start = max(interval.start_sample, end - length_samples)
    return int(start), int(end)


preprocessing = PARAMETERS.preprocessing


def analyze(window: tuple[int, int]):
    return analyze_window_cached(
        str(RAW_DIR),
        record_id,
        fingerprint,
        analysis.channel_index,
        window[0],
        window[1],
        preprocessing.low_hz,
        preprocessing.high_hz,
        preprocessing.order,
        PARAMETERS.qrs.min_rr_ms,
    )


af_window = centered_window(af_interval)
other_window = centered_window(other_interval)
af_analysis = analyze(af_window)
other_analysis = analyze(other_window)

# ── Resultado de la comparación ────────────────────────────────────────────

comparison_rows = []
blocked = []

for name, window, item in (
    ("AF anotada", af_window, af_analysis),
    ("No-FA anotado", other_window, other_analysis),
):
    label = "AF" if name.startswith("AF") else "OTHER"
    summary = summarize_by_rhythm(item.rr_result, min_rr).get(label, {})
    row = {
        "Ventana": name,
        "Inicio [h]": round(window[0] / fs / 3600, 3),
        "Duración [s]": round((window[1] - window[0]) / fs, 1),
        "Calidad": item.quality.status_message,
        "n RR": summary.get("count", 0),
    }
    if summary.get("sufficient"):
        row.update(
            {
                "Mediana [s]": round(summary["median_rr_s"], 4),
                "IQR [s]": round(summary["iqr_rr_s"], 4),
                "SDNN [s]": round(summary["sdnn_s"], 4),
                "CV": round(summary["cv_rr"], 4),
                "RMSSD [s]": round(summary["rmssd_s"], 4),
            }
        )
    else:
        blocked.append(name)
    comparison_rows.append(row)

st.dataframe(pd.DataFrame(comparison_rows), hide_index=True, use_container_width=True)

if blocked:
    st.warning(
        "Sin descriptores para: "
        + ", ".join(blocked)
        + f". No se alcanza el mínimo analítico de {min_rr} intervalos RR "
        "válidos, o la calidad de la ventana no permite compararla. Amplíe la "
        "duración en vez de interpretar una serie corta."
    )

for item, name in ((af_analysis, "AF anotada"), (other_analysis, "No-FA anotado")):
    if not item.quality.is_acceptable:
        st.warning(
            f"La ventana **{name}** fue marcada como «"
            f"{item.quality.status_message}». Cualquier diferencia observada "
            "puede deberse a la calidad de la señal y no al ritmo."
        )

# ── Poincaré comparado ─────────────────────────────────────────────────────

series = {}
if af_analysis.rr_result.durations_s("AF").size >= 2:
    series["AF"] = af_analysis.rr_result.durations_s("AF")
if other_analysis.rr_result.durations_s("OTHER").size >= 2:
    series["OTHER"] = other_analysis.rr_result.durations_s("OTHER")

if series:
    st.plotly_chart(build_poincare_figure(series, record_id), use_container_width=True)

st.caption(
    "Comparación descriptiva entre ventanas equivalentes del mismo registro. "
    "Una diferencia observada no es un efecto causal de la fibrilación "
    "auricular, y las categorías de flutter, ritmo de la unión y sin "
    "anotación se mantienen fuera de esta comparación en lugar de mezclarse "
    "con no-FA."
)
