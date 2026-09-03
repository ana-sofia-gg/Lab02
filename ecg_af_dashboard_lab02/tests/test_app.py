"""Pruebas del dashboard (Evidencia F5).

Las pruebas de páginas ejecutan cada script con `AppTest`, el runner de
pruebas de Streamlit, y verifican que no lancen excepción y que las etiquetas
visibles no usen lenguaje diagnóstico. No demuestran legibilidad ni
accesibilidad: eso exige revisión humana.

Requieren los datos crudos. Si no están descargados, se omiten en vez de
fallar.
"""

from pathlib import Path

import pytest

from ecg_af_dashboard.config import PROJECT_ROOT, RAW_DIR
from ecg_af_dashboard.ui import (
    CLINICAL_DISCLAIMER,
    DATA_CITATION,
    list_record_ids,
    records_without_signal,
)

PAGES = [
    "app.py",
    "pages/1_context_quality.py",
    "pages/2_ecg_explorer.py",
    "pages/3_rr_analysis.py",
    "pages/4_episode_comparison.py",
    "pages/5_methods_limits.py",
]

data_required = pytest.mark.skipif(
    not list(RAW_DIR.glob("*.dat")),
    reason="Faltan los datos crudos: uv run python scripts/download_data.py",
)


# ── Descubrimiento y estados inválidos ─────────────────────────────────────


def test_list_record_ids_empty_directory(tmp_path: Path):
    """Sin archivos WFDB la lista es vacía, no una excepción."""
    assert list_record_ids(tmp_path) == []


def test_records_without_signal_detects_annotation_only(tmp_path: Path):
    """Un registro con encabezado pero sin .dat se marca como sin señal."""
    (tmp_path / "00735.hea").write_text("00735 2 250 0\n", encoding="utf-8")
    (tmp_path / "05091.hea").write_text("05091 2 250 0\n", encoding="utf-8")
    (tmp_path / "05091.dat").write_bytes(b"\x00" * 16)

    assert records_without_signal(tmp_path) == ["00735"]


def test_real_records_all_have_signal():
    """Los tres registros elegidos tienen señal; ninguno es solo anotaciones."""
    if not list_record_ids():
        pytest.skip("Sin datos descargados.")
    assert records_without_signal() == []


# ── Textos obligatorios ────────────────────────────────────────────────────


def test_disclaimer_states_the_clinical_limit():
    text = CLINICAL_DISCLAIMER.lower()
    assert "no diagnostica" in text
    assert "no sustituye" in text


def test_citation_keeps_doi_license_and_version():
    assert "10.13026/C2MW2D" in DATA_CITATION
    assert "ODC-By" in DATA_CITATION
    assert "1.0.0" in DATA_CITATION


# ── Ejecución de las páginas ───────────────────────────────────────────────


@data_required
@pytest.mark.parametrize("script", PAGES)
def test_page_runs_without_exception(script: str):
    """Cada página compone su vista sin lanzar excepción."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / script), default_timeout=300)
    app.run()

    assert not app.exception, [str(item.value) for item in app.exception]


@data_required
@pytest.mark.parametrize("script", PAGES)
def test_page_avoids_diagnostic_wording(script: str):
    """Ninguna vista rotula resultados como positivo, negativo o detectado."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / script), default_timeout=300)
    app.run()

    rendered = " ".join(
        str(getattr(element, "value", "")) for element in app.get("markdown")
    ).lower()
    rendered += " ".join(
        str(getattr(element, "value", "")) for element in app.get("caption")
    ).lower()

    assert "paciente positivo" not in rendered
    assert "fa detectada" not in rendered


@data_required
def test_entry_page_shows_the_clinical_scope():
    """La página de entrada declara el alcance antes de mostrar resultados."""
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=300)
    app.run()

    captions = " ".join(str(element.value) for element in app.get("caption"))
    assert "No diagnostica" in captions
