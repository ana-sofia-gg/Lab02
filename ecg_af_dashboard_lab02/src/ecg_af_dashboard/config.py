"""Parámetros del proyecto en un solo lugar.

Centralizar los valores evita que la interfaz y los scripts usen constantes
distintas, y permite volcarlos a `results/parameters.json` para trazabilidad.
Ningún módulo científico debe redefinir estos valores por su cuenta.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path

# ── Rutas ──────────────────────────────────────────────────────────────────
# La raíz se resuelve desde este archivo, nunca desde el directorio de
# trabajo ni desde una ruta personal.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "afdb"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIGURES_DIR = PROJECT_ROOT / "figures"
RESULTS_DIR = PROJECT_ROOT / "results"

RECORD_IDS: tuple[str, ...] = ("04043", "05091", "06453")


@dataclass(frozen=True)
class PreprocessingParams:
    """Cortes del filtro de inspección.

    El AFDB fue adquirido con un ancho de banda aproximado de 0.1–40 Hz. Los
    cortes se mantienen dentro de esa banda: un filtro digital no recupera
    contenido que el sistema analógico nunca registró.
    """

    low_hz: float = 0.5
    high_hz: float = 40.0
    order: int = 4


@dataclass(frozen=True)
class QualityParams:
    """Umbrales de los indicadores de calidad (Actividad 2.2)."""

    max_non_finite_prop: float = 0.01
    max_out_of_range_prop: float = 0.02
    max_flat_duration_s: float = 1.2
    physiological_min_mv: float = -5.0
    physiological_max_mv: float = 5.0


@dataclass(frozen=True)
class QRSParams:
    """Parámetros del detector y de su control posterior."""

    detector: str = "wfdb.processing.xqrs_detect"
    min_rr_ms: float = 200.0


@dataclass(frozen=True)
class RRParams:
    """Reglas de construcción y resumen de intervalos RR (Fase 4).

    `min_rr_for_summary` es el mínimo analítico del equipo, más exigente que
    los 3 intervalos que `summarize_rr` necesita para ejecutarse. Por debajo
    de ese número la interfaz muestra un aviso en vez de descriptores.
    """

    min_rr_for_summary: int = 30
    # Duración objetivo de las ventanas FA y no-FA comparadas. Se recorta a
    # lo que permita el registro: en AFDB hay episodios de menos de un
    # minuto. Por debajo del mínimo la comparación no se realiza.
    comparison_window_s: float = 300.0
    min_comparison_window_s: float = 30.0
    # Límites fisiológicos opcionales. Están desactivados por defecto: excluir
    # RR por ser extremos puede borrar justamente la irregularidad que se
    # estudia. Actívelos solo con justificación documentada.
    physiological_rr_min_s: float | None = None
    physiological_rr_max_s: float | None = None


@dataclass(frozen=True)
class Parameters:
    """Agrupa todos los parámetros para volcarlos a JSON."""

    preprocessing: PreprocessingParams = field(default_factory=PreprocessingParams)
    quality: QualityParams = field(default_factory=QualityParams)
    qrs: QRSParams = field(default_factory=QRSParams)
    rr: RRParams = field(default_factory=RRParams)

    def to_dict(self) -> dict:
        """Representación serializable para results/parameters.json."""
        return asdict(self)


PARAMETERS = Parameters()
