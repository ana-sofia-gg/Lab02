"""Vista 1. ¿Qué registro se analiza y es utilizable?"""

import pandas as pd
import streamlit as st

from ecg_af_dashboard.annotations import RhythmInterval
from ecg_af_dashboard.config import PARAMETERS, RAW_DIR
from ecg_af_dashboard.quality import check_non_finite_prop
from ecg_af_dashboard.ui import (
    DATA_CITATION,
    header_fingerprint,
    page_setup,
    render_quality_banner,
    rhythm_intervals_cached,
)
from ecg_af_dashboard.visualization import rhythm_display_name

record_id, record, analysis = page_setup("Contexto y calidad")

fs = record.sampling_frequency_hz
total_samples = record.signal.shape[0]
duration_s = total_samples / fs

# ── Metadatos ──────────────────────────────────────────────────────────────

st.subheader("Metadatos del registro")

columns = st.columns(4)
columns[0].metric("Frecuencia de muestreo", f"{fs:.0f} Hz")
columns[1].metric("Duración", f"{duration_s / 3600:.2f} h")
columns[2].metric("Muestras", f"{total_samples:,}".replace(",", " "))
columns[3].metric("Canales", len(record.signal_names))

channel_table = pd.DataFrame(
    {
        "Canal": list(record.signal_names),
        "Unidad": list(record.units),
        "No finitos [%]": [
            100.0 * check_non_finite_prop(record.signal[:, i])
            for i in range(record.signal.shape[1])
        ],
    }
)
st.dataframe(channel_table, hide_index=True, use_container_width=True)

# ── Cronología de ritmo del registro completo ──────────────────────────────

st.subheader("Reparto de ritmo anotado en el registro completo")

intervals: list[RhythmInterval] = rhythm_intervals_cached(
    str(RAW_DIR), record_id, header_fingerprint(record_id)
)

totals: dict[str, float] = {}
counts: dict[str, int] = {}
for interval in intervals:
    seconds = (interval.end_sample - interval.start_sample) / fs
    totals[interval.label] = totals.get(interval.label, 0.0) + seconds
    counts[interval.label] = counts.get(interval.label, 0) + 1

rhythm_table = pd.DataFrame(
    {
        "Etiqueta": [rhythm_display_name(label) for label in totals],
        "Episodios": [counts[label] for label in totals],
        "Tiempo [h]": [totals[label] / 3600.0 for label in totals],
        "Proporción del registro": [totals[label] / duration_s for label in totals],
    }
).sort_values("Tiempo [h]", ascending=False)

st.dataframe(rhythm_table, hide_index=True, use_container_width=True)

if "AF" not in totals or "OTHER" not in totals:
    st.warning(
        "Este registro no contiene simultáneamente tramos FA y no-FA "
        "anotados. La comparación dentro del mismo registro no es posible."
    )

# ── Calidad de la ventana seleccionada ─────────────────────────────────────

st.subheader("Calidad de la ventana seleccionada")

render_quality_banner(analysis)

quality = analysis.quality
params = PARAMETERS.quality

quality_table = pd.DataFrame(
    {
        "Indicador": [
            "Proporción de valores no finitos",
            "Amplitud fuera del rango físico",
            "Línea plana continua",
        ],
        "Valor": [
            f"{quality.non_finite_prop * 100:.3f} %",
            f"{quality.out_of_range_prop * 100:.3f} %",
            "sí" if quality.has_flatline else "no",
        ],
        "Umbral": [
            f"> {params.max_non_finite_prop * 100:.1f} %",
            (
                f"> {params.max_out_of_range_prop * 100:.1f} % fuera de "
                f"[{params.physiological_min_mv:.0f}, "
                f"{params.physiological_max_mv:.0f}] mV"
            ),
            f"> {params.max_flat_duration_s:.1f} s",
        ],
    }
)
st.dataframe(quality_table, hide_index=True, use_container_width=True)

st.caption(
    "Los umbrales son técnicos y describen la señal, no al sujeto. Un "
    "indicador de ruido nunca es un resultado de ritmo."
)

# ── Procedencia y licencia ─────────────────────────────────────────────────

st.subheader("Procedencia y licencia")
st.markdown(
    f"""
- **Fuente:** {DATA_CITATION}
- **Anotaciones de ritmo:** archivos `.atr`, manuales, usados como referencia.
- **Anotaciones de latido:** archivos `.qrs` (no auditadas) y `.qrsc`
  (auditadas). Las no auditadas se usan solo como control auxiliar.
- **Integridad:** verificable con `uv run python scripts/download_data.py`,
  que compara cada archivo contra `results/data_inventory.json`.
"""
)
