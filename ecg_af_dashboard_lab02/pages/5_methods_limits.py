"""Vista 5. ¿Cómo se obtuvo y qué no permite concluir?"""

import json
import platform
import sys

import pandas as pd
import streamlit as st

from ecg_af_dashboard.config import PARAMETERS, RESULTS_DIR
from ecg_af_dashboard.ui import DATA_CITATION, minimum_rr, page_setup

record_id, record, analysis = page_setup("Métodos y límites")

# ── Parámetros ─────────────────────────────────────────────────────────────

st.subheader("Parámetros en uso")

preprocessing = PARAMETERS.preprocessing
quality = PARAMETERS.quality

st.dataframe(
    pd.DataFrame(
        {
            "Etapa": [
                "Filtro de inspección",
                "Filtro de inspección",
                "Detector QRS",
                "Control de QRS",
                "Calidad — no finitos",
                "Calidad — rango físico",
                "Calidad — línea plana",
                "RR — mínimo analítico",
                "RR — límites fisiológicos",
            ],
            "Parámetro": [
                "Banda",
                "Orden y fase",
                "Método",
                "Período refractario mínimo",
                "Umbral",
                "Umbral",
                "Umbral",
                "Intervalos válidos",
                "Estado",
            ],
            "Valor": [
                f"{preprocessing.low_hz}–{preprocessing.high_hz} Hz",
                f"orden {preprocessing.order}, fase cero (sosfiltfilt)",
                PARAMETERS.qrs.detector,
                f"{PARAMETERS.qrs.min_rr_ms:.0f} ms",
                f"> {quality.max_non_finite_prop * 100:.1f} %",
                (
                    f"> {quality.max_out_of_range_prop * 100:.1f} % fuera de "
                    f"[{quality.physiological_min_mv:.0f}, "
                    f"{quality.physiological_max_mv:.0f}] mV"
                ),
                f"> {quality.max_flat_duration_s:.1f} s continuos",
                f"{minimum_rr()}",
                "desactivados por defecto",
            ],
        }
    ),
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "Los valores provienen de `src/ecg_af_dashboard/config.py`; la interfaz "
    "no los redefine por su cuenta."
)

# ── Procedencia ────────────────────────────────────────────────────────────

st.subheader("Procedencia de los datos")
st.markdown(
    f"""
- {DATA_CITATION}
- Registro en pantalla: **{record_id}**, {record.signal.shape[0]:,} muestras a
  {record.sampling_frequency_hz:.0f} Hz, canales
  {", ".join(record.signal_names)} en {", ".join(set(record.units))}.
- La etiqueta de ritmo proviene de las anotaciones manuales `.atr`.
- Las anotaciones de latido `.qrs` no están auditadas y se usan únicamente
  como control auxiliar, nunca como verdad clínica.
"""
)

inventory_path = RESULTS_DIR / "data_inventory.json"
if inventory_path.is_file():
    with open(inventory_path, encoding="utf-8") as handle:
        inventory = json.load(handle)
    entry = next(
        (
            item
            for item in inventory.get("records", [])
            if item["record_id"] == record_id
        ),
        None,
    )
    if entry is not None:
        with st.expander("Inventario y hashes de este registro"):
            st.json(entry)
        if entry.get("known_issues"):
            st.warning("Problemas conocidos: " + " ".join(entry["known_issues"]))
else:
    st.info(
        "No se encontró `results/data_inventory.json`. Genérelo con "
        "`uv run python scripts/reproduce.py`."
    )

# ── Versiones ──────────────────────────────────────────────────────────────

st.subheader("Entorno")

versions = {"python": sys.version.split()[0], "sistema": platform.system()}
for name in ("numpy", "scipy", "pandas", "plotly", "streamlit", "wfdb"):
    try:
        module = __import__(name)
        versions[name] = getattr(module, "__version__", "desconocida")
    except ImportError:
        versions[name] = "no instalado"

st.dataframe(
    pd.DataFrame({"Componente": list(versions), "Versión": list(versions.values())}),
    hide_index=True,
    use_container_width=True,
)

# ── Límites ────────────────────────────────────────────────────────────────

st.subheader("Qué no permite concluir este producto")

st.error(
    "Este dashboard **no diagnostica** fibrilación auricular, no estima "
    "riesgo individual, no recomienda tratamiento y no sustituye la revisión "
    "de un profesional de la salud."
)

st.markdown(
    """
- **La FA que se muestra es anotada, no detectada.** Todas las etiquetas
  provienen de los archivos `.atr` de referencia. La aplicación las lee y las
  reparte en el tiempo; no las produce.
- **Los descriptores no son un umbral diagnóstico.** SDNN, RMSSD, CV e IQR
  describen la irregularidad de la serie RR durante el segmento. No se
  interpretan como modulación autonómica: la FA altera la generación de la
  serie RR y hace inapropiado trasladar interpretaciones de HRV obtenidas en
  ritmo sinusal.
- **Una diferencia entre ventanas no es un efecto causal.** La comparación es
  descriptiva, dentro de registros seleccionados con un criterio documentado.
- **La detección QRS puede fallar.** Un falso positivo divide un intervalo RR;
  una detección perdida fusiona dos. Ambos errores pueden imitar o exagerar
  irregularidad, por eso las marcas se superponen al ECG para ser revisables.
- **El filtrado es de fase cero.** Usa muestras futuras y pasadas: sirve para
  análisis fuera de línea y no describe una operación en tiempo real. Tampoco
  recupera contenido que la cadena analógica nunca registró.
- **La guía clínica de 2023 exige confirmación visual** de las señales para
  documentar FA, aun cuando un dispositivo haya marcado el evento. Este
  prototipo no implementa esa guía ni evalúa sus recomendaciones.
"""
)

st.caption(
    "Formulación completa en `reports/project_brief.md`; operaciones sobre la "
    "señal, con parámetros y riesgos, en `reports/transformations.md`."
)
