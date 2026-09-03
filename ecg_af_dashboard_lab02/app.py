"""Página de entrada del dashboard.

Ejecutar con:
    uv run streamlit run app.py

Esta página resuelve la selección de registro, canal y ventana, y deja el
estado listo para las cinco páginas del análisis. El cálculo científico vive
en `src/ecg_af_dashboard/`; aquí solo hay controles y composición.
"""

import streamlit as st

from ecg_af_dashboard.config import PARAMETERS, RAW_DIR
from ecg_af_dashboard.ui import (
    analyze_window_cached,
    header_fingerprint,
    load_record_cached,
    render_disclaimer,
    render_quality_banner,
    sidebar_selection,
    window_controls,
)

st.set_page_config(
    page_title="ECG y fibrilación auricular anotada",
    page_icon="🫀",
    layout="wide",
)

st.title("Explorador de ECG y fibrilación auricular anotada")
render_disclaimer()

record_id, channel_index = sidebar_selection()
record = load_record_cached(str(RAW_DIR), record_id, header_fingerprint(record_id))
start_sample, end_sample = window_controls(record)

preprocessing = PARAMETERS.preprocessing
analysis = analyze_window_cached(
    str(RAW_DIR),
    record_id,
    header_fingerprint(record_id),
    channel_index,
    start_sample,
    end_sample,
    preprocessing.low_hz,
    preprocessing.high_hz,
    preprocessing.order,
    PARAMETERS.qrs.min_rr_ms,
)

fs = record.sampling_frequency_hz
duration_s = (end_sample - start_sample) / fs

st.subheader(f"Registro {record_id} — canal {analysis.channel_name}")

columns = st.columns(4)
columns[0].metric("Ventana", f"{duration_s:.0f} s")
columns[1].metric("Inicio", f"{start_sample / fs / 3600:.3f} h")
columns[2].metric("QRS aceptados", analysis.qrs_counts.get("accepted", 0))
columns[3].metric("RR aceptados", analysis.rr_result.counts["accepted"])

render_quality_banner(analysis)

st.markdown(
    """
### Recorrido sugerido

1. **Contexto y calidad** — confirme que el registro es utilizable.
2. **Explorador ECG** — observe la ventana con las marcas QRS superpuestas.
3. **Análisis RR** — revise irregularidad y exclusiones.
4. **Episodios y comparación** — contraste una ventana FA con una no-FA
   de igual duración del mismo registro.
5. **Métodos y límites** — consulte parámetros, versiones y procedencia.

La selección de registro, canal y ventana se conserva entre páginas.
"""
)

st.info(
    "La etiqueta de fibrilación auricular proviene de las anotaciones `.atr` "
    "de referencia del conjunto de datos. No es una conclusión generada por "
    "esta aplicación."
)
