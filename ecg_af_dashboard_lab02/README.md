# ECG AF Dashboard — Laboratorio 2, Bioseñales de ECG

Dashboard de exploración de episodios de fibrilación auricular **previamente
anotados** en registros ambulatorios de ECG de la
**MIT-BIH Atrial Fibrillation Database (AFDB)** de PhysioNet.

> **Alcance clínico.** Este es un prototipo académico de exploración. No
> diagnostica fibrilación auricular, no estima riesgo individual, no recomienda
> tratamiento y no sustituye la revisión de un profesional de la salud. La
> etiqueta de FA proviene de las anotaciones de referencia del conjunto de
> datos; no es una conclusión generada por la aplicación.


## Requisitos

- Python 3.13
- [uv]como gestor de entorno y dependencias
- Conexión a internet para la descarga inicial de los datos
- Para compilar informe y presentación: una distribución LaTeX con
  `latexmk`, `beamer`, `booktabs`, `siunitx` y **`babel` con soporte de
  español** (en Debian/Ubuntu: `texlive-latex-recommended`,
  `texlive-lang-spanish`; en Windows, MiKTeX o TeX Live completos)

## Puesta en marcha (en dicho orden)

```bash
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run python scripts/download_data.py
uv run pytest -v
uv run python scripts/reproduce.py
uv run streamlit run app.py
```

Si la verificación de integridad (SHA-256) reporta que faltan archivos .dat o están alterados:
Linux: `rm -rf data/raw/afdb`
Windows: `Remove-Item -Recurse -Force data\raw\afdb`
Luego (para ambos casos): `uv run python scripts/download_data.py`

Con esa secuencia el proyecto queda operativo y los datos verificados.

## Datos

Los registros crudos pesan ~77 MB y **no están versionados**. Se recuperan
desde PhysioNet con `scripts/download_data.py`, que descarga los tres
registros en `data/raw/afdb/` y verifica cada archivo contra los hashes
SHA-256 almacenados en `results/data_inventory.json`. Así los datos usados son
bit a bit idénticos a los originales.

**Fuente:** MIT-BIH Atrial Fibrillation Database v1.0.0
· DOI [10.13026/C2MW2D](https://doi.org/10.13026/C2MW2D)
· Licencia Open Data Commons Attribution (ODC-By) v1.0
· Detalles en [`data/raw/afdb/README.md`](data/raw/afdb/README.md)

## Comandos

| Comando | Qué hace |
| :--- | :--- |
| `uv sync --locked` | Instala el entorno exacto fijado en `uv.lock` |
| `uv run ruff check .` | Revisa estilo y errores comunes |
| `uv run python scripts/download_data.py` | Descarga y verifica los datos crudos |
| `uv run pytest` | Ejecuta la batería de pruebas |
| `uv run python scripts/reproduce.py` | Regenera inventario, derivados, `summary.json`, `parameters.json`, figuras y manifiesto |
| `uv run python scripts/environment_report.py` | Reporta versiones para la bitácora |
| `uv run streamlit run app.py` | Inicia el dashboard |
| `latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build/reports reports/informe.tex` | Compila el informe en LaTeX|
| `latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir=build/slides slides/presentacion.tex` | Compila el beamer en LaTeX|

Para abrir el informe:
Windows: `Start-Process "build\reports\informe.pdf"`
Linux: `xdg-open build/reports/informe.pdf`

Para abrir la presentación:
Windows: `Start-Process "build\slides\presentacion.pdf"`
Linux: `xdg-open build/slides/presentacion.pdf`

---

## Registros seleccionados (Actividad 1.1)

| Identificador | Disponibilidad de señal | Duración | Canales y unidades | Intervalos FA y no-FA | Problemas conocidos | Razón de inclusión |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **05091** | Completa | 10 h 14 min | 2 ch (mV) | Varias transiciones FA y no-FA | Ninguno estructural (anotaciones `qrsc`) | Caso base de referencia limpia |
| **04043** | Completa (con artefacto) | 10 h 14 min | 2 ch (mV) | Presenta episodios de FA y no-FA | Bloque 39 ilegible (ceros por 10.24 s) | Prueba de robustez del código ante segmentos huecos de datos |
| **06453** | Parcial (duración recortada) | 9 h 15 min | 2 ch (mV) | Presenta episodios de FA y no-FA | Grabación incompleta (no fueron 10 horas) | Prueba del código ante series temporales de menor longitud |

Los tres se muestrean a 250 Hz sobre 2 canales de ECG. Las duraciones provienen
del encabezado WFDB, no de la documentación del conjunto.

La formulación completa del producto está en
[`reports/project_brief.md`](reports/project_brief.md); las operaciones
aplicadas a la señal, con sus parámetros y riesgos, en
[`reports/transformations.md`](reports/transformations.md).

---

## Estructura

```
ecg_af_dashboard_lab02/
├── .python-version        Versión de Python fijada (3.13)
├── .gitignore
├── README.md
├── pyproject.toml         Dependencias, Ruff y pytest
├── uv.lock                Entorno exacto reproducible
├── app.py                 Página de entrada del dashboard
├── build/                 Salida de latexmk (no versionada)
│   ├── reports/           informe.pdf
│   └── slides/            presentacion.pdf
├── pages/
│   ├── 1_context_quality.py     Contexto y calidad
│   ├── 2_ecg_explorer.py        Explorador ECG
│   ├── 3_rr_analysis.py         Análisis RR
│   ├── 4_episode_comparison.py  Episodios y comparación
│   └── 5_methods_limits.py      Métodos y límites
├── data/
│   ├── raw/afdb/          Registros WFDB originales (no versionados) + licencia
│   ├── interim/           Intermedios regenerables
│   └── processed/         Derivados regenerables (RR por ventana)
├── figures/               Figuras resumen regeneradas por reproduce.py
├── reports/
│   ├── informe.tex        Informe técnico (fuente LaTeX)
│   ├── project_brief.md   Ficha de formulación (Control D1)
│   └── transformations.md Tabla de transformaciones (Actividad 3.1)
├── results/
│   ├── data_inventory.json     Procedencia, hashes SHA-256, duración y problemas
│   ├── summary.json            Resultados numéricos regenerables
│   ├── parameters.json         Parámetros usados en la corrida
│   ├── summary_table.tex       Tabla del informe, generada por Python
│   ├── delivery_manifest.txt   Hash y tamaño de cada producto
│   ├── manual_review.md        Bitácora de revisión manual
│   ├── reproduction_log.md     Bitácora de reproducción
│   ├── technical_review.md     Notas de revisión técnica
│   └── contributions.md        Reparto de trabajo
├── scripts/
│   ├── download_data.py        Descarga y verificación de los datos crudos
│   ├── reproduce.py            Orquestación reproducible
│   └── environment_report.py   Versiones de Python y dependencias
├── slides/
│   └── presentacion.tex   Presentación Beamer (fuente LaTeX)
├── src/ecg_af_dashboard/
│   ├── config.py          Parámetros y rutas centralizados
│   ├── io.py              Lectura de registros WFDB (señal + anotaciones .atr)
│   ├── validation.py      Validación de integridad temporal y estructural
│   ├── preprocessing.py   Filtro pasabanda Butterworth de fase cero
│   ├── annotations.py     Ritmo: normalización, intervalos y carga anotada de FA
│   ├── quality.py         Calidad: no finitos, rango físico, línea plana
│   ├── qrs.py             Detección de complejos QRS (XQRS)
│   ├── qrs_control.py     Control de picos: límites, duplicados, refractariedad
│   ├── rr.py              Intervalos RR válidos, exclusiones y descriptores
│   ├── visualization.py   Figuras Plotly reutilizables (sin Streamlit)
│   ├── ui.py              Caché, selección y estados inválidos de la interfaz
│   └── inventory.py       Inventario reproducible con hashes SHA-256
└── tests/                 Pruebas por fase (pytest)
```

Los archivos de `data/raw/afdb/`, `build/`, `data/interim/` y `data/processed/`
no se versionan: se regeneran con `download_data.py`, `reproduce.py` y
`latexmk`. Las carpetas sí se conservan mediante `.gitkeep`.

## El dashboard

```bash
uv run streamlit run app.py
```

Cinco vistas, con la selección de registro, canal y ventana compartida entre
todas: **Contexto y calidad**, **Explorador ECG**, **Análisis RR**,
**Episodios y comparación** y **Métodos y límites**.

Las etiquetas visibles son «FA anotada» y «no-FA anotado». Nunca «positivo»,
«negativo» ni «FA detectada»: la etiqueta viene de la anotación de
referencia, no de la aplicación. Hay pruebas que lo verifican.

## Decisiones de diseño

- **Detector, Filtros y Ventanas**: Se utiliza el detector XQRS para 
  la localización de picos ventriculares y un filtro pasabanda Butterworth 
  de fase cero (sosfiltfilt) para la eliminación de ruido. El análisis se 
  estructura mediante ventanas temporales configurables desde la interfaz.
- **Reglas de Calidad**: El sistema descarta segmentos con valores no finitos, 
  superación de rangos físicos o tramos de línea plana/saturación prolongada.
- **Asignación de Ritmo a Intervalos RR**: Los intervalos entre latidos 
  consecutivos (RR) se alinean temporalmente con las anotaciones de ritmo 
  del archivo .atr, asignando la etiqueta correspondiente (FA u otro ritmo) 
  a cada intervalo según su marca de tiempo.
- **Carga anotada de FA**: porcentaje del tiempo analizable que las
  anotaciones `.atr` marcan como `(AFIB`, sobre la ventana o el registro
  seleccionado. Es una lectura de la anotación de referencia, no una
  detección de la aplicación ni una afirmación sobre el sujeto.
- **Filtrado de fase cero** (`sosfiltfilt`): elimina el desfase que
  introduciría un filtro causal, a costa de usar muestras futuras. Válido para
  análisis offline; **no** describe una operación en tiempo real.
- **Tres representaciones separadas**: señal física original leída de WFDB,
  señal procesada para inspección, y la transformación interna del detector
  QRS. El filtrado del detector no se presenta como ECG equivalente al
  original.
- **Control post-detección de QRS**: los picos crudos de XQRS se filtran por
  límites de la señal, duplicados, período refractario mínimo (200 ms) y
  máscara de calidad, con conteo explícito de cada descarte.
- **Datos inmutables**: `data/raw/` nunca se modifica. La verificación por
  SHA-256 garantiza la trazabilidad entre resultados y fuente.
- **Índices de muestra como referencia interna**: la conversión a segundos u
  horas ocurre solo al presentar, usando la frecuencia leída del encabezado y
  nunca una constante global.

## Distribución del trabajo

El trabajo y las responsabilidades se distribuyeron de manera colaborativa 
entre los integrantes del equipo (registrado en results/contributions.md):
- **Coordinación General**: Guió el flujo de integración de la arquitectura 
  y la orquestación global del laboratorio.
- **Codificadores**: Desarrollaron de forma conjunta todo el código, incluyendo
  módulos científicos, lógica de procesamiento y las vistas del dashboard.
- **Control de Calidad**: Verificó la robustez de las pruebas y la correcta 
  gestión de excepciones ante datos anómalos.

## Estado

| Fase | Contenido | Estado |
| :--- | :--- | :--- |
| 1 | Selección, inventario, cargador y validación | Completa |
| 2 | Intervalos de ritmo, calidad y carga anotada de FA | Completa |
| 3 | Preprocesamiento, detección y control de QRS | Completa |
| 4 | Intervalos RR válidos y descriptores | Completa |
| 5 | Figuras, dashboard y las cinco vistas | Completa |
| 6 | `reproduce.py` completo, informe LaTeX y Beamer | Completa |
