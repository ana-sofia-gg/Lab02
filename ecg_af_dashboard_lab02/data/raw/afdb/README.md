# Datos crudos — MIT-BIH Atrial Fibrillation Database (AFDB)

Esta carpeta contiene los archivos WFDB **originales**, tal como se descargan
de PhysioNet. Nunca se editan, se corrigen a mano ni se sobrescriben: los
derivados van a `data/interim/` y `data/processed/`.

Los archivos `.dat`, `.hea`, `.atr`, `.qrs` y `.qrsc` **no se versionan**
(~77 MB). Se recuperan con:

```bash
uv run python scripts/download_data.py
```

Ese script descarga los tres registros usados y verifica cada archivo contra
los hashes SHA-256 de `results/data_inventory.json`. Si un hash no coincide,
el script termina con código distinto de cero.

## Procedencia

- **Conjunto:** MIT-BIH Atrial Fibrillation Database, versión **1.0.0**
- **DOI:** [10.13026/C2MW2D](https://doi.org/10.13026/C2MW2D)
- **Licencia:** Open Data Commons Attribution License (ODC-By) v1.0 — ver
  `LICENSE.txt`
- **Registros usados:** `04043`, `05091`, `06453`
- **Frecuencia de muestreo:** se lee del encabezado `.hea` de cada registro,
  nunca se asume como constante.

## Anotaciones

- `.atr` — anotaciones **manuales** de ritmo (`(AFIB`, `(AFL`, `(J`, `(N`).
  Son la referencia de FA de este proyecto.
- `.qrs` — anotaciones de latido **no auditadas**. Se usan solo como control
  auxiliar; nunca como verdad clínica.
- `.qrsc` — anotaciones de latido auditadas, cuando el registro las trae.

## Problemas conocidos

- Los registros `00735` y `03665` solo incluyen anotaciones, sin señal ECG.
  Por eso no se seleccionaron.
- El registro `07859` tuvo un problema histórico de alineación en sus
  anotaciones QRS. No se usa en este laboratorio.
