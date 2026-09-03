"""Vista 3. ¿Qué irregularidad existe en la ventana?"""

import pandas as pd
import streamlit as st

from ecg_af_dashboard.rr import (
    REASON_NON_PHYSIOLOGICAL,
    REASON_QUALITY,
    REASON_TRANSITION,
    RHYTHM_LABELS,
    summarize_by_rhythm,
)
from ecg_af_dashboard.ui import minimum_rr, page_setup, render_quality_banner
from ecg_af_dashboard.visualization import (
    build_poincare_figure,
    build_rr_histogram_figure,
    build_tachogram_figure,
    rhythm_display_name,
)

record_id, record, analysis = page_setup("Análisis RR")

render_quality_banner(analysis)

result = analysis.rr_result
counts = result.counts
fs = analysis.sampling_frequency_hz
min_rr = minimum_rr()

# ── Exclusiones ────────────────────────────────────────────────────────────

st.subheader("Intervalos RR y exclusiones")

metrics = st.columns(5)
metrics[0].metric("Pares de QRS", counts["total_pairs"])
metrics[1].metric("Aceptados", counts["accepted"])
metrics[2].metric("Calidad", counts[REASON_QUALITY])
metrics[3].metric("Cruzan transición", counts[REASON_TRANSITION])
metrics[4].metric("Fuera de límites", counts[REASON_NON_PHYSIOLOGICAL])

if counts["total_pairs"]:
    excluded = counts["total_pairs"] - counts["accepted"]
    st.caption(
        f"Excluidos {excluded} de {counts['total_pairs']} "
        f"({excluded / counts['total_pairs'] * 100:.1f} %). Cada exclusión se "
        "atribuye a la primera causa que la produce, en el orden calidad → "
        "transición → límites."
    )
else:
    st.error(
        "No hay pares de QRS en esta ventana. Amplíe la duración o desplace "
        "la selección."
    )
    st.stop()

st.caption(
    "Los límites fisiológicos de RR están desactivados por defecto: descartar "
    "un intervalo por ser extremo puede borrar justamente la irregularidad "
    "que se estudia."
)

# ── Tacograma ──────────────────────────────────────────────────────────────

st.subheader("Tacograma")
show_excluded = st.toggle("Mostrar intervalos excluidos", value=True)
st.plotly_chart(
    build_tachogram_figure(result, fs, record_id, show_excluded=show_excluded),
    use_container_width=True,
)

# ── Series por etiqueta ────────────────────────────────────────────────────

series = {
    label: result.durations_s(label)
    for label in RHYTHM_LABELS
    if result.durations_s(label).size
}

if not series:
    st.warning("No quedaron intervalos RR aceptados tras aplicar las exclusiones.")
    st.stop()

columns = st.columns(2)
with columns[0]:
    st.subheader("Distribución")
    st.plotly_chart(
        build_rr_histogram_figure(series, record_id), use_container_width=True
    )
with columns[1]:
    st.subheader("Poincaré")
    st.plotly_chart(build_poincare_figure(series, record_id), use_container_width=True)

st.caption(
    "Una nube de Poincaré más dispersa muestra mayor variación entre "
    "intervalos sucesivos, pero no identifica por sí sola la causa."
)

# ── Descriptores ───────────────────────────────────────────────────────────

st.subheader("Descriptores de irregularidad")

summaries = summarize_by_rhythm(result, min_rr)
rows = []
for label, summary in summaries.items():
    if not summary.get("sufficient"):
        continue
    rows.append(
        {
            "Ritmo": rhythm_display_name(label),
            "n RR": summary["count"],
            "Mediana [s]": round(summary["median_rr_s"], 4),
            "IQR [s]": round(summary["iqr_rr_s"], 4),
            "Media [s]": round(summary["mean_rr_s"], 4),
            "SDNN [s]": round(summary["sdnn_s"], 4),
            "CV": round(summary["cv_rr"], 4),
            "RMSSD [s]": round(summary["rmssd_s"], 4),
        }
    )

if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
else:
    st.warning(
        f"Ninguna etiqueta alcanza el mínimo analítico de {min_rr} intervalos "
        "RR válidos. Amplíe la ventana en vez de interpretar una serie corta."
    )

insufficient = [
    (label, summary["count"])
    for label, summary in summaries.items()
    if not summary.get("sufficient") and summary["count"] > 0
]
if insufficient:
    detail = ", ".join(
        f"{rhythm_display_name(label)}: {count}" for label, count in insufficient
    )
    st.info(f"Por debajo del mínimo de {min_rr} RR válidos — {detail}.")

st.caption(
    "SDNN, RMSSD y CV se interpretan como descriptores de irregularidad "
    "ventricular durante el segmento, no como estimación de modulación "
    "autonómica: la FA altera la generación de la serie RR y hace inapropiado "
    "trasladar interpretaciones de HRV obtenidas en ritmo sinusal."
)
