from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from ecg_af_dashboard.annotations import (
    RhythmInterval,
    build_rhythm_intervals,
    calculate_af_load,
)
from ecg_af_dashboard.config import (
    FIGURES_DIR,
    PARAMETERS,
    PROCESSED_DIR,
    RAW_DIR,
    RECORD_IDS,
    RESULTS_DIR,
)
from ecg_af_dashboard.inventory import calculate_sha256, generate_data_inventory
from ecg_af_dashboard.io import load_afdb_record
from ecg_af_dashboard.preprocessing import bandpass_zero_phase
from ecg_af_dashboard.qrs import detect_qrs_xqrs
from ecg_af_dashboard.qrs_control import control_qrs_detections
from ecg_af_dashboard.quality import build_quality_mask, evaluate_signal_quality
from ecg_af_dashboard.rr import build_rr_intervals, summarize_by_rhythm
from ecg_af_dashboard.validation import validate_ecg_record

# El script corre en terminal: no abre ventanas de gráficos.
matplotlib.use("Agg")

CHANNEL_INDEX = 0


def longest_interval(
    intervals: list[RhythmInterval], label: str
) -> RhythmInterval | None:
    """Intervalo más largo con esa etiqueta de ritmo."""
    candidates = [i for i in intervals if i.label == label]
    if not candidates:
        return None
    return max(candidates, key=lambda i: i.end_sample - i.start_sample)


def comparison_window_samples(
    intervals: list[RhythmInterval], sampling_frequency_hz: float
) -> int | None:
    """Duración común de las ventanas FA y no-FA de un mismo registro.

    Recortar la duración objetivo es preferible a comparar ventanas desiguales:
    la equivalencia temporal es lo que hace legítima la comparación.
    """
    af = longest_interval(intervals, "AF")
    other = longest_interval(intervals, "OTHER")
    if af is None or other is None:
        return None

    available = min(
        af.end_sample - af.start_sample, other.end_sample - other.start_sample
    )
    target = int(PARAMETERS.rr.comparison_window_s * sampling_frequency_hz)
    minimum = int(PARAMETERS.rr.min_comparison_window_s * sampling_frequency_hz)
    window = min(target, available)
    return window if window >= minimum else None


def select_window(
    intervals: list[RhythmInterval],
    label: str,
    window_samples: int,
) -> tuple[int, int] | None:
    """Ventana centrada dentro del intervalo más largo con esa etiqueta.

    Al quedar contenida en un solo intervalo, la ventana no cruza transiciones.
    """
    candidates = [i for i in intervals if i.label == label]
    if not candidates:
        return None
    longest = max(candidates, key=lambda i: i.end_sample - i.start_sample)
    available = longest.end_sample - longest.start_sample
    if available < window_samples:
        return None
    center = (longest.start_sample + longest.end_sample) // 2
    start = center - window_samples // 2
    return start, start + window_samples


def analyze_window(
    record,
    intervals: list[RhythmInterval],
    window: tuple[int, int],
) -> dict:
    """Preprocesa, detecta QRS, construye RR y resume una ventana."""
    fs = record.sampling_frequency_hz
    start, end = window
    raw = record.signal[start:end, CHANNEL_INDEX]

    quality = evaluate_signal_quality(
        raw,
        fs,
        PARAMETERS.quality.max_non_finite_prop,
        PARAMETERS.quality.max_out_of_range_prop,
        PARAMETERS.quality.max_flat_duration_s,
    )
    mask = build_quality_mask(
        raw,
        PARAMETERS.quality.physiological_min_mv,
        PARAMETERS.quality.physiological_max_mv,
        sampling_rate=fs,
        max_flat_duration=PARAMETERS.quality.max_flat_duration_s,
    )
    global_mask = np.ones(end, dtype=bool)
    global_mask[start:end] = mask

    # El filtro no admite no finitos; la máscara los excluye después.
    clean = np.where(np.isfinite(raw), raw, 0.0)
    processed = bandpass_zero_phase(
        clean,
        fs,
        PARAMETERS.preprocessing.low_hz,
        PARAMETERS.preprocessing.high_hz,
        PARAMETERS.preprocessing.order,
    )

    peaks = detect_qrs_xqrs(processed, fs)
    control = control_qrs_detections(
        peaks,
        processed.size,
        fs,
        PARAMETERS.qrs.min_rr_ms,
        quality_mask=mask,
    )

    # Índices de vuelta al registro completo, para asignar el ritmo.
    global_peaks = control.valid_indices + start
    rr = build_rr_intervals(
        global_peaks,
        intervals,
        fs,
        quality_mask=global_mask,
        physiological_rr_min_s=PARAMETERS.rr.physiological_rr_min_s,
        physiological_rr_max_s=PARAMETERS.rr.physiological_rr_max_s,
    )
    summaries = summarize_by_rhythm(rr, PARAMETERS.rr.min_rr_for_summary)

    excluded = [(start, end)] if not quality.is_acceptable else []
    load = calculate_af_load(intervals, (start, end), fs, excluded_spans=excluded)

    return {
        "window_samples": [int(start), int(end)],
        "window_start_s": start / fs,
        "duration_s": (end - start) / fs,
        "channel": record.signal_names[CHANNEL_INDEX],
        "units": record.units[CHANNEL_INDEX],
        "quality": {
            "is_acceptable": quality.is_acceptable,
            "status_message": quality.status_message,
            "non_finite_prop": quality.non_finite_prop,
            "out_of_range_prop": quality.out_of_range_prop,
            "has_flatline": quality.has_flatline,
        },
        "qrs_counts": control.counts,
        "rr_counts": rr.counts,
        "rr_summaries": summaries,
        "af_load": {
            "selectable_time_s": load.selectable_time_s,
            "excluded_time_s": load.excluded_time_s,
            "analyzable_time_s": load.analyzable_time_s,
            "af_time_s": load.af_time_s,
            "af_load": load.af_load,
        },
        "_rr_durations": rr.durations_s,
    }


def save_figure(record_id: str, channel: str, units: str, blocks: dict) -> Path:
    """Histograma RR de las ventanas FA y no-FA del mismo registro."""
    figure, axes = plt.subplots(figsize=(7.0, 4.0))
    for label, style in (("AF", "//"), ("OTHER", "..")):
        block = blocks.get(label)
        if block is None:
            continue
        durations = block["_rr_durations"](label)
        if durations.size == 0:
            continue
        axes.hist(
            durations,
            bins=40,
            alpha=0.55,
            hatch=style,
            label=f"{'FA anotada' if label == 'AF' else 'No-FA anotado'} "
            f"(n={durations.size})",
        )
    duration_s = next(iter(blocks.values()))["duration_s"]
    axes.set_title(
        f"Registro {record_id} — canal {channel} — RR de ventanas de "
        f"{duration_s:.0f} s\nseñal procesada (pasabanda de fase cero)"
    )
    axes.set_xlabel("Intervalo RR [s]")
    axes.set_ylabel("Número de intervalos")
    axes.legend()
    figure.tight_layout()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"rr_hist_{record_id}.png"
    figure.savefig(path, dpi=150)
    plt.close(figure)
    return path


def write_results_table(summary: dict) -> Path:
    """Tabla LaTeX de la comparación FA/no-FA que el informe hace \\input."""
    rows = []
    for record in summary["records"]:
        for label, name in (("AF", "FA anotada"), ("OTHER", "No-FA anotado")):
            block = record["comparison"][label]
            stats = block["rr_summaries"].get(label, {})
            if not stats.get("sufficient"):
                rows.append(
                    f"{record['record_id']} & {name} & "
                    f"{stats.get('count', 0)} & --- & --- & --- & --- \\\\"
                )
                continue
            rows.append(
                f"{record['record_id']} & {name} & {stats['count']} & "
                f"{stats['median_rr_s']:.3f} & {stats['iqr_rr_s']:.3f} & "
                f"{stats['cv_rr']:.3f} & {stats['rmssd_s']:.3f} \\\\"
            )

    body = "\n    ".join(rows)
    content = (
        "% Generado por scripts/reproduce.py. No editar a mano.\n"
        "\\begin{table}[h]\n"
        "  \\centering\n"
        "  \\caption{Descriptores RR por ventana equivalente (misma duración,\n"
        "  mismo registro, sin transiciones de ritmo internas).}\n"
        "  \\begin{tabular}{llrrrrr}\n"
        "    \\toprule\n"
        "    Registro & Ventana & $n$ RR & Mediana [s] & IQR [s] & "
        "$CV_{RR}$ & RMSSD [s] \\\\\n"
        "    \\midrule\n"
        f"    {body}\n"
        "    \\bottomrule\n"
        "  \\end{tabular}\n"
        "\\end{table}\n"
    )
    path = RESULTS_DIR / "summary_table.tex"
    path.write_text(content, encoding="utf-8")
    return path


def write_manifest(paths: list[Path]) -> Path:
    """Manifiesto con la huella SHA-256 de cada producto regenerado."""
    lines = [
        "MANIFIESTO DE ENTREGA",
        "=====================",
        "Archivos regenerados por scripts/reproduce.py.",
        "Los hashes permiten comprobar que dos ejecuciones producen lo mismo.",
        "",
    ]
    for path in sorted(paths):
        if not path.is_file():
            continue
        relative = path.relative_to(RESULTS_DIR.parent).as_posix()
        size = path.stat().st_size
        lines.append(f"{calculate_sha256(path)}  {size:>10} B  {relative}")

    manifest_path = RESULTS_DIR / "delivery_manifest.txt"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    print(f"Raíz del proyecto: {RAW_DIR.parents[2]}")

    print("Generando inventario y verificando hashes SHA-256...")
    try:
        generate_data_inventory()
    except FileNotFoundError as error:
        print(
            f"{error}\nEjecute primero: uv run python scripts/download_data.py",
            file=sys.stderr,
        )
        return 1

    window_samples_by_record: dict[str, int] = {}
    summary: dict = {"records": [], "parameters_file": "results/parameters.json"}
    produced: list[Path] = []

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    for record_id in RECORD_IDS:
        print(f"Procesando {record_id}...")
        record = load_afdb_record(RAW_DIR, record_id)
        validate_ecg_record(record)

        fs = record.sampling_frequency_hz
        total_samples = record.signal.shape[0]
        intervals = build_rhythm_intervals(
            record.rhythm_samples, record.rhythm_notes, total_samples
        )

        window_samples = comparison_window_samples(intervals, fs)
        if window_samples is None:
            print(
                f"  {record_id}: no admite una comparación FA/no-FA de al menos "
                f"{PARAMETERS.rr.min_comparison_window_s:.0f} s.",
                file=sys.stderr,
            )
            return 1
        window_samples_by_record[record_id] = window_samples
        print(f"  ventana común: {window_samples / fs:.1f} s por ritmo")

        # Carga anotada del registro completo: solo anotaciones, sin QRS.
        whole = calculate_af_load(intervals, (0, total_samples), fs)

        blocks: dict[str, dict] = {}
        for label in ("AF", "OTHER"):
            window = select_window(intervals, label, window_samples)
            if window is None:
                print(
                    f"  {record_id}: sin ventana {label} de "
                    f"{window_samples / fs:.1f} s sin transiciones.",
                    file=sys.stderr,
                )
                continue
            blocks[label] = analyze_window(record, intervals, window)

        if set(blocks) != {"AF", "OTHER"}:
            print(
                f"  {record_id}: no se pudo formar la pareja FA/no-FA equivalente.",
                file=sys.stderr,
            )
            return 1

        figure_path = save_figure(
            record_id,
            record.signal_names[CHANNEL_INDEX],
            record.units[CHANNEL_INDEX],
            blocks,
        )
        produced.append(figure_path)

        # Derivado: RR de cada ventana, para reconstruir sin releer WFDB.
        derived_path = PROCESSED_DIR / f"rr_{record_id}.json"
        derived_path.write_text(
            json.dumps(
                {
                    label: {
                        "window_samples": block["window_samples"],
                        "rr_s": [
                            round(float(v), 6)
                            for v in block["_rr_durations"](label).tolist()
                        ],
                    }
                    for label, block in blocks.items()
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        produced.append(derived_path)

        for block in blocks.values():
            block.pop("_rr_durations")

        summary["records"].append(
            {
                "record_id": record_id,
                "sampling_frequency_hz": fs,
                "total_samples": int(total_samples),
                "comparison_window_s": window_samples / fs,
                "duration_s": total_samples / fs,
                "channels": list(record.signal_names),
                "units": list(record.units),
                "whole_record_af_load": {
                    "analyzable_time_s": whole.analyzable_time_s,
                    "af_time_s": whole.af_time_s,
                    "afl_time_s": whole.afl_time_s,
                    "j_time_s": whole.j_time_s,
                    "other_time_s": whole.other_time_s,
                    "unknown_time_s": whole.unknown_time_s,
                    "af_load": whole.af_load,
                },
                "comparison": blocks,
                "figure": f"figures/{figure_path.name}",
            }
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    produced.append(summary_path)

    parameters = PARAMETERS.to_dict()
    parameters["comparison_window_samples"] = window_samples_by_record
    parameters["channel_index"] = CHANNEL_INDEX
    parameters_path = RESULTS_DIR / "parameters.json"
    parameters_path.write_text(
        json.dumps(parameters, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    produced.append(parameters_path)

    produced.append(write_results_table(summary))

    produced.append(RESULTS_DIR / "data_inventory.json")
    write_manifest(produced)

    print("\nReproducción completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
