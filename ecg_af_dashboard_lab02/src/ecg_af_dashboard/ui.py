"""Soporte de interfaz: caché, selección de registro y estados inválidos.

Este módulo es la única parte del paquete que importa Streamlit. Contiene
envoltorios de caché y controles compartidos entre `app.py` y las páginas;
el cálculo científico sigue viviendo en los módulos puros y aquí solo se
orquesta.

Streamlit vuelve a ejecutar el script completo cada vez que cambia un
control, de modo que la carga y los cálculos costosos se separan de la
composición visual y se invalidan según archivo, parámetros y ventana.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import streamlit as st

from ecg_af_dashboard.annotations import (
    AFLoadResult,
    build_rhythm_intervals,
    calculate_af_load,
)
from ecg_af_dashboard.config import PARAMETERS, RAW_DIR
from ecg_af_dashboard.io import ECGRecord, load_afdb_record
from ecg_af_dashboard.preprocessing import bandpass_zero_phase
from ecg_af_dashboard.qrs import check_qrs_channel_disagreement, detect_qrs_xqrs
from ecg_af_dashboard.qrs_control import control_qrs_detections
from ecg_af_dashboard.quality import (
    QualityAssessment,
    build_quality_mask,
    evaluate_signal_quality,
)
from ecg_af_dashboard.rr import RRBuildResult, build_rr_intervals

CLINICAL_DISCLAIMER = (
    "Prototipo académico de exploración de registros previamente anotados. "
    "No diagnostica fibrilación auricular, no estima riesgo individual y no "
    "sustituye la revisión de un profesional de la salud."
)

DATA_CITATION = (
    "MIT-BIH Atrial Fibrillation Database v1.0.0 · DOI 10.13026/C2MW2D · "
    "Open Data Commons Attribution License (ODC-By) v1.0"
)


@dataclass(frozen=True)
class WindowAnalysis:
    """Todo lo que una ventana produce, calculado una sola vez."""

    start_sample: int
    end_sample: int
    channel_index: int
    channel_name: str
    units: str
    sampling_frequency_hz: float
    raw_mv: np.ndarray
    processed_mv: np.ndarray | None
    quality: QualityAssessment
    qrs_local: np.ndarray
    qrs_counts: dict[str, int]
    rr_result: RRBuildResult
    af_load: AFLoadResult
    filter_error: str | None


# ── Descubrimiento de registros ────────────────────────────────────────────


def list_record_ids(directory: Path | None = None) -> list[str]:
    """Registros con encabezado WFDB disponibles en la carpeta de datos."""
    folder = Path(directory) if directory is not None else RAW_DIR
    if not folder.is_dir():
        return []
    return sorted(path.stem for path in folder.glob("*.hea"))


def records_without_signal(directory: Path | None = None) -> list[str]:
    """Registros que tienen encabezado pero no archivo de señal.

    En el AFDB, 00735 y 03665 solo incluyen anotaciones: no puede mostrarse
    su ECG y deben quedar fuera del explorador.
    """
    folder = Path(directory) if directory is not None else RAW_DIR
    missing = []
    for record_id in list_record_ids(folder):
        if not (folder / f"{record_id}.dat").is_file():
            missing.append(record_id)
    return missing


def header_fingerprint(record_id: str, directory: Path | None = None) -> int:
    """Marca de modificación del encabezado, usada para invalidar la caché."""
    folder = Path(directory) if directory is not None else RAW_DIR
    return (folder / f"{record_id}.hea").stat().st_mtime_ns


# ── Carga y análisis con caché ─────────────────────────────────────────────


@st.cache_data(show_spinner="Leyendo registro…")
def load_record_cached(
    directory_text: str,
    record_id: str,
    header_modified_ns: int,
) -> ECGRecord:
    """Invalida la caché cuando cambia el encabezado del registro."""
    del header_modified_ns
    return load_afdb_record(Path(directory_text), record_id)


@st.cache_data(show_spinner="Reconstruyendo intervalos de ritmo…")
def rhythm_intervals_cached(
    directory_text: str,
    record_id: str,
    header_modified_ns: int,
) -> list:
    """Intervalos de ritmo del registro completo."""
    record = load_record_cached(directory_text, record_id, header_modified_ns)
    return build_rhythm_intervals(
        record.rhythm_samples,
        record.rhythm_notes,
        record.signal.shape[0],
    )


@st.cache_data(show_spinner="Calculando calidad, QRS e intervalos RR…")
def analyze_window_cached(
    directory_text: str,
    record_id: str,
    header_modified_ns: int,
    channel_index: int,
    start_sample: int,
    end_sample: int,
    low_hz: float,
    high_hz: float,
    order: int,
    min_rr_ms: float,
) -> WindowAnalysis:
    """Ejecuta el flujo completo sobre una ventana y cachea el resultado.

    La clave de caché incluye el archivo, la ventana y los parámetros, de modo
    que cambiar cualquiera de ellos fuerza el recálculo.
    """
    record = load_record_cached(directory_text, record_id, header_modified_ns)
    intervals = rhythm_intervals_cached(directory_text, record_id, header_modified_ns)

    fs = record.sampling_frequency_hz
    raw = np.asarray(record.signal[start_sample:end_sample, channel_index], dtype=float)

    quality = evaluate_signal_quality(
    raw,
    fs,
    max_non_finite_prop = PARAMETERS.quality.max_non_finite_prop,
    max_out_of_range_prop = PARAMETERS.quality.max_out_of_range_prop,
    max_flat_duration_sec = PARAMETERS.quality.max_flat_duration_s,
    )
    """ Máscara por muestra con la que se excluyen las detecciones QRS que
    caen en tramos de calidad insuficiente (Actividad 3.4). """
    quality_mask = build_quality_mask(
        raw,
        PARAMETERS.quality.physiological_min_mv,
        PARAMETERS.quality.physiological_max_mv,
        sampling_rate=fs,
        max_flat_duration=PARAMETERS.quality.max_flat_duration_s,
    )
    # build_rr_intervals indexa por muestra del registro completo.
    global_mask = np.ones(end_sample, dtype=bool)
    global_mask[start_sample:end_sample] = quality_mask

    processed: np.ndarray | None = None
    filter_error: str | None = None
    qrs_local = np.array([], dtype=int)
    qrs_counts: dict[str, int] = {}

    try:
        clean = np.where(np.isfinite(raw), raw, 0.0)
        processed = bandpass_zero_phase(clean, fs, low_hz, high_hz, order)
    except ValueError as error:
        filter_error = str(error)

    if processed is not None:
        try:
            peaks = detect_qrs_xqrs(processed, fs)
            control = control_qrs_detections(
                peaks,
                raw.size,
                fs,
                min_rr_ms=min_rr_ms,
                quality_mask=quality_mask,
            )
            qrs_local = np.asarray(control.valid_indices, dtype=int)
            qrs_counts = dict(control.counts)
        except ValueError as error:
            filter_error = filter_error or str(error)

    rr_result = build_rr_intervals(
        qrs_local + start_sample,
        intervals,
        fs,
        quality_mask=global_mask,
    )
    af_load = calculate_af_load(
    intervals, 
    (start_sample, end_sample), 
    fs, 
    excluded_spans=quality.excluded_spans
    )

    return WindowAnalysis(
        start_sample=start_sample,
        end_sample=end_sample,
        channel_index=channel_index,
        channel_name=record.signal_names[channel_index],
        units=record.units[channel_index],
        sampling_frequency_hz=fs,
        raw_mv=raw,
        processed_mv=processed,
        quality=quality,
        qrs_local=qrs_local,
        qrs_counts=qrs_counts,
        rr_result=rr_result,
        af_load=af_load,
        filter_error=filter_error,
    )


# ── Estados inválidos y controles compartidos ──────────────────────────────


def stop_if_no_records() -> list[str]:
    """Estado inválido: no hay archivos WFDB en la carpeta de datos."""
    record_ids = list_record_ids()
    if not record_ids:
        st.error(
            f"No se encontraron registros WFDB en `{RAW_DIR}`.\n\n"
            "Descárguelos y verifíquelos con:\n\n"
            "```bash\nuv run python scripts/download_data.py\n```"
        )
        st.stop()
    return record_ids


def stop_if_annotations_only(record_id: str) -> None:
    """Estado inválido: el registro no tiene señal, solo anotaciones."""
    if record_id in records_without_signal():
        st.error(
            f"El registro **{record_id}** solo incluye anotaciones: no existe "
            "archivo de señal, por lo que no puede mostrarse un ECG. "
            "Seleccione otro registro."
        )
        st.stop()


def sidebar_selection() -> tuple[str, int]:
    """Selector de registro y canal, compartido por todas las páginas."""
    record_ids = stop_if_no_records()

    with st.sidebar:
        st.subheader("Selección")
        default = st.session_state.get("record_id", record_ids[0])
        index = record_ids.index(default) if default in record_ids else 0
        record_id = st.selectbox("Registro", options=record_ids, index=index)
        st.session_state["record_id"] = record_id

        stop_if_annotations_only(record_id)

        record = load_record_cached(
            str(RAW_DIR), record_id, header_fingerprint(record_id)
        )
        names = list(record.signal_names)
        stored = st.session_state.get("channel_index", 0)
        channel_index = st.selectbox(
            "Canal",
            options=range(len(names)),
            index=stored if stored < len(names) else 0,
            format_func=lambda i: f"{names[i]} [{record.units[i]}]",
        )
        st.session_state["channel_index"] = int(channel_index)

        st.caption(DATA_CITATION)

    return record_id, int(channel_index)


def window_controls(record: ECGRecord) -> tuple[int, int]:
    """Controles de ventana en minutos, devueltos en índices de muestra.

    El estado se guarda en `st.session_state` para que las cinco páginas
    trabajen sobre la misma selección.
    """
    fs = record.sampling_frequency_hz
    total_s = record.signal.shape[0] / fs

    with st.sidebar:
        st.subheader("Ventana")
        start_min = st.number_input(
            "Inicio [min]",
            min_value=0.0,
            max_value=float(total_s / 60.0),
            value=float(st.session_state.get("window_start_min", 0.0)),
            step=1.0,
        )
        duration_s = st.select_slider(
            "Duración [s]",
            options=[30, 60, 120, 300, 600],
            value=int(st.session_state.get("window_duration_s", 60)),
        )
        if st.button("Volver al estado inicial", use_container_width=True):
            start_min, duration_s = 0.0, 60

    st.session_state["window_start_min"] = float(start_min)
    st.session_state["window_duration_s"] = int(duration_s)

    start_sample = int(round(start_min * 60.0 * fs))
    end_sample = min(record.signal.shape[0], start_sample + int(round(duration_s * fs)))
    return start_sample, end_sample


def render_quality_banner(analysis: WindowAnalysis) -> None:
    """Veredicto de calidad con el mensaje oficial y desacuerdo QRS."""
    if analysis.filter_error is not None:
        st.error(
            f"No se pudo procesar la ventana: {analysis.filter_error} "
            "Revise los cortes del filtro (debe cumplirse 0 < low < high < fs/2) "
            "o amplíe la ventana."
        )
        return
    if analysis.quality.is_acceptable:
        st.success(f"Calidad: {analysis.quality.status_message}")
    else:
        st.warning(
            f"Calidad: {analysis.quality.status_message}. "
            "Los descriptores de esta ventana no deben usarse para comparar."
        )

    if analysis.disagreement_info and analysis.disagreement_info.get("disagreement_flag"):
        diff_pct = analysis.disagreement_info.get("max_diff_pct", 0.0)
        st.warning(
            f"**Desacuerdo marcado de QRS entre canales** "
            f"(Diferencia del {diff_pct:.1f}% entre derivaciones). "
            "Posible artefacto, ruido o fallo en una de las derivaciones."
        )


def render_disclaimer() -> None:
    """Nota de alcance, presente en todas las páginas."""
    st.caption(CLINICAL_DISCLAIMER)


def minimum_rr() -> int:
    """Mínimo analítico de intervalos RR para reportar descriptores."""
    return PARAMETERS.rr.min_rr_for_summary


def page_setup(title: str) -> tuple[str, ECGRecord, WindowAnalysis]:
    """Encabezado, selección y análisis compartidos por cada página.

    Evita repetir el mismo bloque en las cinco páginas y garantiza que todas
    trabajen sobre la misma ventana.
    """
    st.set_page_config(page_title=title, page_icon="🫀", layout="wide")
    st.title(title)
    render_disclaimer()

    record_id, channel_index = sidebar_selection()
    fingerprint = header_fingerprint(record_id)
    record = load_record_cached(str(RAW_DIR), record_id, fingerprint)
    start_sample, end_sample = window_controls(record)

    preprocessing = PARAMETERS.preprocessing
    analysis = analyze_window_cached(
        str(RAW_DIR),
        record_id,
        fingerprint,
        channel_index,
        start_sample,
        end_sample,
        preprocessing.low_hz,
        preprocessing.high_hz,
        preprocessing.order,
        PARAMETERS.qrs.min_rr_ms,
    )
    return record_id, record, analysis
