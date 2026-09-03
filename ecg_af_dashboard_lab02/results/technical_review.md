# Revisión Técnica y Arquitectura — ECG AF Dashboard

Este documento detalla la estructura interna, los fundamentos de procesamiento de señales, la estrategia de validación y las decisiones de diseño implementadas en el prototipo académico para la exploración de fibrilación auricular (FA) en registros ambulatorios de ECG.

---

## 1. Arquitectura del Sistema y Módulos (`src/ecg_af_dashboard/`)

El núcleo de procesamiento científico y la lógica de negocio se encuentran desacoplados de la interfaz gráfica, organizados en módulos especializados:

* **`io.py`**: Encargado de la lectura de registros y anotaciones desde el formato estándar WFDB (utilizando `wfdb`), extrayendo tanto la señal física en milivoltios como las anotaciones de ritmo `.atr`.
* **`validation.py`**: Valida la integridad estructural y temporal de los registros cargados, asegurando que las dimensiones y frecuencias de muestreo coincidan con lo esperado.
* **`annotations.py`**: Normaliza las anotaciones de ritmo, calcula los intervalos entre cambios de ritmo y determina la carga porcentual de fibrilación auricular en el segmento o registro.
* **`preprocessing.py`**: Aplica el filtrado pasabanda utilizando un filtro Butterworth de fase cero (`sosfiltfilt`) para eliminar ruido de línea de base y artefactos de alta frecuencia sin introducir desfase temporal.
* **`quality.py`**: Ejecuta pruebas de calidad sobre la señal (detección de valores no finitos, desbordamiento de rango físico y tramos de línea plana o saturación).
* **`qrs.py`**: Envuelve el detector de complejos QRS (XQRS) para identificar los latidos basales en la señal procesada.
* **`qrs_control.py`**: Aplica un control post-detección riguroso sobre los picos QRS crudos (filtrado por límites de amplitud, eliminación de duplicados y aplicación de un período refractario mínimo de 200 ms).
* **`rr.py`**: Calcula los intervalos RR válidos a partir de los picos QRS controlados, excluyendo anomalías y calculando descriptores estadísticos de variabilidad.
* **`visualization.py`**: Construye las figuras gráficas reutilizables basadas en `Plotly`, completamente desacopladas de Streamlit para facilitar su prueba y mantenimiento.
* **`ui.py`**: Maneja la caché de Streamlit, la selección de registros/canales en la barra lateral y la gestión de estados inválidos de la interfaz.
* **`config.py`**: Centraliza los parámetros globales del proyecto (frecuencias de corte, umbrales de QRS, directorios base).
* **`inventory.py`**: Gestiona el inventario reproducible y la verificación de hashes SHA-256 de los datos crudos.

---

## 2. Pipeline de Procesamiento de Señal y Detección

El flujo de análisis de una ventana o registro sigue una secuencia determinista:

1. **Carga y Verificación:** Se lee la señal cruda desde `data/raw/afdb/` verificando su integridad mediante SHA-256.
2. **Control de Calidad:** Se evalúan los segmentos para detectar artefactos severos (como el bloque ilegible de ceros en el registro `04043`).
3. **Preprocesamiento:** Filtrado pasabanda Butterworth (fase cero) optimizado para eliminar ruido muscular y deriva de línea de base.
4. **Detección QRS:** Localización de picos ventriculares mediante XQRS.
5. **Filtrado Post-detección:** Descarte de falsos positivos mediante validación de período refractario (200 ms) y umbrales de amplitud.
6. **Análisis de Ritmo e Intervalos RR:** Cálculo de intervalos entre latidos consecutivos, clasificación de intervalos válidos y estimación de métricas de irregularidad asociadas a episodios de FA anotados de referencia.

---

## 3. Estrategia de Pruebas y Calidad de Código (`tests/`)

El proyecto cuenta con una suite completa de pruebas unitarias y de integración ejecutadas mediante `pytest`:

* **Pruebas de IO y Validación:** Comprueban la correcta lectura de archivos WFDB y la detección de archivos corruptos o faltantes.
* **Pruebas de Preprocesamiento y QRS:** Verifican el comportamiento de los filtros y el control de picos ante datos sintéticos y reales.
* **Pruebas de Intervalos RR:** Aseguran que funciones como `summarize_rr` manejen correctamente los límites (por ejemplo, rechazando conjuntos con menos de tres intervalos mediante excepciones controladas de tipo `ValueError`).

Para ejecutar la verificación completa:
```bash
uv run pytest -v