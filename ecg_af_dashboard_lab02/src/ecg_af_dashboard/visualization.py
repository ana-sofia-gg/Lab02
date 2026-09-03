"""Figuras Plotly reutilizables (Actividad 5.1).

Este módulo construye objetos `go.Figure` y nada más: no carga archivos, no
llama a Streamlit y no decide qué ventana mostrar. Recibe datos ya
seleccionados y validados.

Cada figura declara registro o canal, unidad, eje temporal y qué
transformación se está viendo, para que ninguna vista quede sin procedencia.
El color nunca es el único portador de significado: las series se distinguen
además por nombre, símbolo o patrón de línea.
"""

from dataclasses import dataclass

import numpy as np
import plotly.graph_objects as go

# Paleta legible ante deficiencias de visión cromática. Cada entrada se
# acompaña siempre de un nombre en la leyenda y, donde aplica, de un símbolo.
COLOR_RAW = "#3b6fb6"
COLOR_PROCESSED = "#d97706"
COLOR_QRS = "#7a1f5c"
COLOR_EXCLUDED = "#9ca3af"

RHYTHM_COLORS = {
    "AF": "#b45309",
    "AFL": "#7c3aed",
    "J": "#0f766e",
    "OTHER": "#3b6fb6",
    "UNKNOWN": "#9ca3af",
}

RHYTHM_DISPLAY = {
    "AF": "FA anotada",
    "AFL": "Flutter anotado",
    "J": "Ritmo de la unión anotado",
    "OTHER": "No-FA anotado",
    "UNKNOWN": "Sin anotación",
}


@dataclass(frozen=True)
class Envelope:
    """Resultado de la reducción mínimo-máximo para dibujar."""

    time_s: np.ndarray
    values: np.ndarray
    reduced: bool
    original_points: int


def rhythm_display_name(label: str) -> str:
    """Nombre visible de una etiqueta de ritmo.

    Se usan las formas «FA anotada» y «no-FA anotado». Nunca «positivo»,
    «negativo» ni «FA detectada»: la etiqueta viene de la anotación de
    referencia, no de la aplicación.
    """
    return RHYTHM_DISPLAY.get(label, f"Etiqueta {label}")


def minmax_envelope(
    time_s: np.ndarray,
    values: np.ndarray,
    max_points: int = 4000,
) -> Envelope:
    """Reduce una serie para dibujarla conservando los extremos por bloque.

    Se aplica **solo para presentar**. Los QRS, los RR y todos los
    descriptores se calculan sobre la serie completa; diezmar antes de
    calcular ocultaría eventos breves.

    Cada bloque aporta su mínimo y su máximo en el orden temporal en que
    aparecen, de modo que los picos no desaparecen al alejar el zoom.
    """
    time_s = np.asarray(time_s, dtype=float)
    values = np.asarray(values, dtype=float)
    if time_s.shape != values.shape:
        raise ValueError("Tiempo y valores deben tener la misma longitud.")
    if time_s.ndim != 1 or time_s.size == 0:
        raise ValueError("Se requiere un vector no vacío.")
    if max_points < 4:
        raise ValueError("max_points debe ser al menos 4.")

    total = time_s.size
    if total <= max_points:
        return Envelope(time_s, values, reduced=False, original_points=total)

    blocks = max_points // 2
    block_size = int(np.ceil(total / blocks))
    keep: list[int] = []
    for start in range(0, total, block_size):
        stop = min(start + block_size, total)
        chunk = values[start:stop]
        low = start + int(np.argmin(chunk))
        high = start + int(np.argmax(chunk))
        keep.extend(sorted({low, high}))

    indices = np.array(sorted(set(keep)), dtype=int)
    return Envelope(
        time_s=time_s[indices],
        values=values[indices],
        reduced=True,
        original_points=total,
    )


def build_ecg_figure(
    time_s: np.ndarray,
    raw_mv: np.ndarray,
    processed_mv: np.ndarray | None,
    qrs_samples_local: np.ndarray,
    channel: str,
    rhythm_label: str,
    units: str = "mV",
    record_id: str = "",
) -> go.Figure:
    """Construye ECG con marcas QRS; no carga datos ni llama Streamlit.

    `qrs_samples_local` son índices relativos a la ventana dibujada, no al
    registro completo. La función lo verifica en vez de suponerlo.
    """
    time_s = np.asarray(time_s, dtype=float)
    raw_mv = np.asarray(raw_mv, dtype=float)
    qrs_samples_local = np.asarray(qrs_samples_local, dtype=int)

    if time_s.ndim != 1 or time_s.size == 0:
        raise ValueError("El eje temporal debe ser un vector no vacío.")
    if raw_mv.shape != time_s.shape:
        raise ValueError("El ECG físico y el eje temporal deben coincidir.")
    if processed_mv is not None:
        processed_mv = np.asarray(processed_mv, dtype=float)
        if processed_mv.shape != time_s.shape:
            raise ValueError("El ECG procesado y el eje temporal deben coincidir.")
    if qrs_samples_local.size and (
        qrs_samples_local.min() < 0 or qrs_samples_local.max() >= time_s.size
    ):
        raise ValueError("Hay marcas QRS fuera de la ventana dibujada.")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=time_s,
            y=raw_mv,
            mode="lines",
            name="ECG físico",
            line={"color": COLOR_RAW, "width": 1.1},
        )
    )
    if processed_mv is not None:
        figure.add_trace(
            go.Scatter(
                x=time_s,
                y=processed_mv,
                mode="lines",
                name="ECG procesado",
                # Patrón distinto para no depender solo del color.
                line={"color": COLOR_PROCESSED, "width": 1.1, "dash": "dot"},
            )
        )
    if qrs_samples_local.size:
        figure.add_trace(
            go.Scatter(
                x=time_s[qrs_samples_local],
                y=raw_mv[qrs_samples_local],
                mode="markers",
                name="QRS aceptado",
                marker={"color": COLOR_QRS, "symbol": "x", "size": 8},
            )
        )

    if rhythm_label in RHYTHM_DISPLAY:
        label_text = rhythm_display_name(rhythm_label)
    else:
        label_text = rhythm_label
    figure.update_layout(
        title=(
            (f"Registro {record_id} — " if record_id else "")
            + f"canal {channel} — ritmo de referencia: {label_text}"
        ),
        xaxis_title="Tiempo [s]",
        yaxis_title=f"Amplitud [{units}]",
        hovermode="x unified",
        template="plotly_white",
    )
    return figure


def build_rhythm_timeline_figure(
    intervals,
    sampling_frequency_hz: float,
    record_id: str,
    window: tuple[int, int] | None = None,
) -> go.Figure:
    """Cronología de los intervalos de ritmo anotados de un registro.

    Permite ubicar los episodios antes de elegir una ventana. Si se pasa
    `window`, se marca la selección vigente sobre la misma escala.
    """
    if not np.isfinite(sampling_frequency_hz) or sampling_frequency_hz <= 0:
        raise ValueError("La frecuencia de muestreo debe ser finita y positiva.")

    fs = float(sampling_frequency_hz)
    figure = go.Figure()
    seen: set[str] = set()

    for interval in intervals:
        start_h = interval.start_sample / fs / 3600.0
        end_h = interval.end_sample / fs / 3600.0
        label = interval.label
        figure.add_trace(
            go.Scatter(
                x=[start_h, end_h],
                y=[label, label],
                mode="lines",
                name=rhythm_display_name(label),
                legendgroup=label,
                showlegend=label not in seen,
                line={"color": RHYTHM_COLORS.get(label, "#111827"), "width": 12},
                hovertemplate=(
                    f"{rhythm_display_name(label)}<br>%{{x:.3f}} h<extra></extra>"
                ),
            )
        )
        seen.add(label)

    if window is not None:
        for edge in window:
            figure.add_vline(
                x=edge / fs / 3600.0,
                line={"color": "#111827", "width": 1, "dash": "dash"},
            )

    figure.update_layout(
        title=f"Registro {record_id} — cronología de ritmo anotado",
        xaxis_title="Tiempo [h]",
        yaxis_title="Etiqueta de ritmo",
        template="plotly_white",
    )
    return figure


def build_tachogram_figure(
    rr_result,
    sampling_frequency_hz: float,
    record_id: str,
    show_excluded: bool = True,
) -> go.Figure:
    """Tacograma RR con los intervalos excluidos visibles pero diferenciados.

    Ocultar las exclusiones haría creer que la serie es continua. Se dibujan
    en gris y con símbolo abierto, y la leyenda dice cuántos son.
    """
    if not np.isfinite(sampling_frequency_hz) or sampling_frequency_hz <= 0:
        raise ValueError("La frecuencia de muestreo debe ser finita y positiva.")

    fs = float(sampling_frequency_hz)
    figure = go.Figure()

    by_label: dict[str, list[tuple[float, float]]] = {}
    excluded: list[tuple[float, float]] = []
    for rr in rr_result.intervals:
        point = (rr.start_sample / fs, rr.duration_s)
        if rr.included:
            by_label.setdefault(rr.label, []).append(point)
        else:
            excluded.append(point)

    for label, points in by_label.items():
        xs, ys = zip(*points, strict=True)
        figure.add_trace(
            go.Scatter(
                x=list(xs),
                y=list(ys),
                mode="markers",
                name=f"{rhythm_display_name(label)} (n={len(points)})",
                marker={
                    "color": RHYTHM_COLORS.get(label, "#111827"),
                    "symbol": "circle",
                    "size": 6,
                },
            )
        )

    if show_excluded and excluded:
        xs, ys = zip(*excluded, strict=True)
        figure.add_trace(
            go.Scatter(
                x=list(xs),
                y=list(ys),
                mode="markers",
                name=f"Excluido (n={len(excluded)})",
                marker={
                    "color": COLOR_EXCLUDED,
                    "symbol": "circle-open",
                    "size": 6,
                },
            )
        )

    figure.update_layout(
        title=f"Registro {record_id} — tacograma RR",
        xaxis_title="Tiempo [s]",
        yaxis_title="Intervalo RR [s]",
        template="plotly_white",
    )
    return figure


def build_rr_histogram_figure(
    series_by_label: dict[str, np.ndarray],
    record_id: str,
    bin_size_s: float = 0.02,
) -> go.Figure:
    """Histograma de RR por etiqueta de ritmo, superpuesto y semitransparente.

    Cada etiqueta conserva su identidad; no se agrega un «no-FA» que mezcle
    OTHER con AFL o J.
    """
    if bin_size_s <= 0:
        raise ValueError("El ancho de bin debe ser positivo.")

    figure = go.Figure()
    for label, values in series_by_label.items():
        values = np.asarray(values, dtype=float)
        if values.size == 0:
            continue
        figure.add_trace(
            go.Histogram(
                x=values,
                name=f"{rhythm_display_name(label)} (n={values.size})",
                marker={"color": RHYTHM_COLORS.get(label, "#111827")},
                opacity=0.6,
                xbins={"size": bin_size_s},
            )
        )

    figure.update_layout(
        title=f"Registro {record_id} — distribución de intervalos RR",
        xaxis_title="Intervalo RR [s]",
        yaxis_title="Conteo",
        barmode="overlay",
        template="plotly_white",
    )
    return figure


def build_poincare_figure(
    series_by_label: dict[str, np.ndarray],
    record_id: str,
) -> go.Figure:
    """Diagrama de Poincaré: cada punto es un par (RR_n, RR_n+1).

    Una nube más dispersa indica mayor variación entre intervalos sucesivos,
    pero no identifica por sí sola la causa. Los pares que cruzarían una
    transición de ritmo ya fueron excluidos al construir la serie.
    """
    figure = go.Figure()
    all_values: list[float] = []

    for label, values in series_by_label.items():
        values = np.asarray(values, dtype=float)
        if values.size < 2:
            continue
        figure.add_trace(
            go.Scatter(
                x=values[:-1],
                y=values[1:],
                mode="markers",
                name=f"{rhythm_display_name(label)} (n={values.size - 1})",
                marker={
                    "color": RHYTHM_COLORS.get(label, "#111827"),
                    "symbol": "circle",
                    "size": 5,
                    "opacity": 0.65,
                },
            )
        )
        all_values.extend(values.tolist())

    if all_values:
        low = min(all_values)
        high = max(all_values)
        margin = 0.05 * (high - low) if high > low else 0.05
        figure.add_trace(
            go.Scatter(
                x=[low - margin, high + margin],
                y=[low - margin, high + margin],
                mode="lines",
                name="Identidad (RRn = RRn+1)",
                line={"color": "#111827", "width": 1, "dash": "dash"},
            )
        )

    figure.update_layout(
        title=f"Registro {record_id} — diagrama de Poincaré",
        xaxis_title="RRn [s]",
        yaxis_title="RRn+1 [s]",
        template="plotly_white",
    )
    return figure
