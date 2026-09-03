"""Vista 2. ¿Qué ocurre en la ventana?"""

import numpy as np
import streamlit as st

from ecg_af_dashboard.config import PARAMETERS, RAW_DIR
from ecg_af_dashboard.rr import label_at_sample
from ecg_af_dashboard.ui import (
    header_fingerprint,
    page_setup,
    render_quality_banner,
    rhythm_intervals_cached,
)
from ecg_af_dashboard.visualization import (
    build_ecg_figure,
    build_rhythm_timeline_figure,
    minmax_envelope,
    rhythm_display_name,
)

record_id, record, analysis = page_setup("Explorador ECG")

fs = analysis.sampling_frequency_hz
intervals = rhythm_intervals_cached(
    str(RAW_DIR), record_id, header_fingerprint(record_id)
)

render_quality_banner(analysis)

# ── Cronología: dónde está la ventana dentro del registro ──────────────────

st.subheader("Ubicación de la ventana en el registro")
st.plotly_chart(
    build_rhythm_timeline_figure(
        intervals,
        fs,
        record_id,
        window=(analysis.start_sample, analysis.end_sample),
    ),
    use_container_width=True,
)

# ── Controles de la vista ──────────────────────────────────────────────────

st.subheader("Ventana seleccionada")

controls = st.columns(3)
show_processed = controls[0].toggle("Mostrar ECG procesado", value=True)
show_qrs = controls[1].toggle("Mostrar marcas QRS", value=True)
max_points = controls[2].select_slider(
    "Puntos dibujados",
    options=[2000, 4000, 8000, 16000],
    value=4000,
    help=(
        "Solo afecta el dibujo. Los QRS y los RR se calculan siempre sobre la "
        "serie completa."
    ),
)

if analysis.filter_error is not None:
    st.stop()

# ── Etiquetas de ritmo presentes en la ventana ─────────────────────────────

labels_in_window = {
    label_at_sample(sample, intervals)
    for sample in (analysis.start_sample, analysis.end_sample - 1)
}
if len(labels_in_window) > 1:
    st.warning(
        "La ventana contiene una **transición de ritmo**: "
        + ", ".join(sorted(rhythm_display_name(x) for x in labels_in_window))
        + ". Los intervalos RR que cruzan la transición quedan excluidos y "
        "no se atribuyen a ninguno de los dos ritmos."
    )
window_label = label_at_sample(analysis.start_sample, intervals)

# ── Figura ─────────────────────────────────────────────────────────────────

time_full_s = (
    np.arange(analysis.raw_mv.size, dtype=float) + analysis.start_sample
) / fs

envelope_raw = minmax_envelope(time_full_s, analysis.raw_mv, max_points=max_points)

if envelope_raw.reduced:
    # Con la serie reducida, las marcas QRS ya no tienen índice equivalente:
    # se dibuja la envolvente sin marcas y se avisa por qué.
    figure = build_ecg_figure(
        envelope_raw.time_s,
        envelope_raw.values,
        None,
        np.array([], dtype=int),
        analysis.channel_name,
        window_label,
        units=analysis.units,
        record_id=record_id,
    )
    st.plotly_chart(figure, use_container_width=True)
    st.info(
        f"Vista reducida: {envelope_raw.original_points:,} muestras dibujadas "
        f"como envolvente mínimo-máximo de {envelope_raw.values.size:,} puntos. "
        "Reduzca la duración de la ventana para ver las marcas QRS sobre la "
        "señal completa.".replace(",", " ")
    )
else:
    processed = analysis.processed_mv if show_processed else None
    marks = analysis.qrs_local if show_qrs else np.array([], dtype=int)
    figure = build_ecg_figure(
        time_full_s,
        analysis.raw_mv,
        processed,
        marks,
        analysis.channel_name,
        window_label,
        units=analysis.units,
        record_id=record_id,
    )
    st.plotly_chart(figure, use_container_width=True)

# ── Procedencia de lo que se está viendo ───────────────────────────────────

preprocessing = PARAMETERS.preprocessing
st.caption(
    f"Registro {record_id} · canal {analysis.channel_name} "
    f"[{analysis.units}] · "
    f"{analysis.start_sample / fs:.1f}–{analysis.end_sample / fs:.1f} s · "
    f"ritmo de referencia: {rhythm_display_name(window_label)} · "
    f"ECG procesado = pasabanda {preprocessing.low_hz}–{preprocessing.high_hz} Hz, "
    f"orden {preprocessing.order}, fase cero."
)

# ── Control de detecciones ─────────────────────────────────────────────────

st.subheader("Control de detecciones QRS")

counts = analysis.qrs_counts
total = counts.get("total_detected", 0)
accepted = counts.get("accepted", 0)

metrics = st.columns(5)
metrics[0].metric("Detectados", total)
metrics[1].metric("Aceptados", accepted)
metrics[2].metric("Fuera de límites", counts.get("discarded_out_of_bounds", 0))
metrics[3].metric("Duplicados", counts.get("discarded_duplicates", 0))
metrics[4].metric("Refractarios", counts.get("discarded_refractory", 0))

if total and accepted / total < 0.8:
    st.warning(
        "Se descartó más del 20 % de las detecciones. Las marcas QRS de esta "
        "ventana no son confiables: revise visualmente antes de comparar."
    )

st.caption(
    "El detector es wfdb.processing.xqrs_detect sobre la señal procesada. "
    "Su salida exige control de calidad y revisión visual; llamar la función "
    "no sustituye la revisión."
)
