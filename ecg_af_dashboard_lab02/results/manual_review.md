# Bitácora de Revisión Manual

Este documento registra la auditoría visual y cualitativa del tablero de control
de ECG y Fibrilación Auricular, cumpliendo con la sección 6.5 del proyecto.

- **Fecha:** 2026-09-02
- **Revisora:** Jeimmy Andrea Gonzáles G.
- **Entorno:** Windows · Python 3.13.14 · streamlit 1.61.1 · plotly 6.9.0 ·
  wfdb 4.3.1 · numpy 2.5.2 · scipy 1.18.0
- **Canal revisado:** ECG1 [mV] en los tres registros.

Las pruebas automáticas no demuestran legibilidad, honestidad de escala ni
alineación de las marcas. Esta revisión sí encontró un defecto que las 81
pruebas no detectaban; queda registrado en la sección 4.

---

## 1. Inicio, mitad y final de cada registro

| Registro | Ventana | Ritmo | Hallazgo | Acción |
| :--- | :--- | :--- | :--- | :--- |
| 04043 | 0.00–1.00 min (inicio) | No-FA anotado | Trazado legible. 107 QRS aceptados, 106 RR, calidad OK. La app avisa que la ventana contiene una transición No-FA → Sin anotación. | Conforme |
| 04043 | 307 min (mitad) | — | Pendiente | Pendiente |
| 04043 | 612 min (final) | — | Pendiente | Pendiente |
| 05091 | 0.00 min (inicio) | — | Pendiente | Pendiente |
| 05091 | 290.02–291.02 min (mitad) | FA → no-FA | Trazado legible. 86 pares de QRS, 85 aceptados. | Conforme |
| 05091 | 612 min (final) | — | Pendiente | Pendiente |
| 06453 | 0.00 min (inicio) | — | Pendiente | Pendiente |
| 06453 | 296.48 min (mitad) | No-FA anotado | Cronología y carga anotada coherentes con el registro (1.11 % de FA). | Conforme |
| 06453 | 553 min (final) | — | Pendiente | Pendiente |

**Metadatos verificados en 04043:** 250 Hz leídos del encabezado, 10.23 h,
9 205 760 muestras, 2 canales en mV, 0 % de valores no finitos en ambos canales.
Reparto de ritmo anotado: no-FA 83 episodios (8.025 h), FA 82 episodios
(2.1999 h = 21.51 %), Flutter 1 episodio (0.0036 h) y Sin anotación 1 episodio,
**reportados por separado y nunca agrupados dentro de no-FA**.

---

## 2. Una ventana FA y una no-FA por registro

| Registro | Ventana | Ritmo | Hallazgo | Acción |
| :--- | :--- | :--- | :--- | :--- |
| 04043 | 1135.8–1195.8 s (18.93 min) | FA anotada | Título de la figura declara registro, canal, unidad y ritmo de referencia. RR visiblemente irregulares. 120 QRS detectados, 120 aceptados, 0 descartados. | Conforme |
| 04043 | 5773.2–5833.2 s (96.22 min) | No-FA anotado | Trazado claramente más regular que el de FA, con la misma escala y unidades. 99 QRS detectados, 99 aceptados. | Conforme |
| 05091 | 290.02 min | FA + no-FA | Tacograma separa FA anotada (n=66) de No-FA anotado (n=19) por color **y** por leyenda. Poincaré: FA disperso (n=65), no-FA compacto (n=18). Descriptores FA: mediana 0.574 s, IQR 0.179 s, CV 0.3271, RMSSD 0.2799 s. | Conforme |
| 06453 | 8.145 h (FA) vs 4.946 h (no-FA), 120 s cada una | FA / no-FA | Comparación equivalente del mismo registro: FA 136 RR, mediana 0.906 s, IQR 0.276 s, CV 0.2156; no-FA 117 RR, mediana 1.016 s, IQR 0.032 s, CV 0.0981. Poincaré confirma el contraste. | Conforme |

Los descriptores mostrados coinciden con `results/summary.json`, generado de
forma independiente por `scripts/reproduce.py`.

---

## 3. Una transición de ritmo

| Registro | Ventana | Ritmo | Hallazgo | Acción |
| :--- | :--- | :--- | :--- | :--- |
| 05091 | 290.02–291.02 min | FA anotada → No-FA anotado | De 86 pares de QRS, **1 se excluyó por cruzar la transición** (1.2 %). El tacograma lo dibuja como punto hueco «Excluido (n=1)» y el conteo lo atribuye a su causa. | Conforme |
| 04043 | 0.00–1.00 min | No-FA → Sin anotación | La app avisa de la transición aunque ningún RR llegue a cruzarla (0 excluidos). El aviso es correcto: la ventana sí contiene el cambio. | Conforme |

---

## 4. Una ventana de mala calidad — DEFECTO ENCONTRADO Y CORREGIDO

| Registro | Ventana | Ritmo | Hallazgo | Acción |
| :--- | :--- | :--- | :--- | :--- |
| 04043 | 5.83–6.83 min (tramo plano de 10.24 s desde 358.4 s) | No-FA anotado | El banner respondió bien: «Calidad: Requiere revisión, respecto a las líneas planas. Los descriptores de esta ventana no deben usarse para comparar», con «Línea plana continua: sí». **Pero los descriptores se calcularon igual y quedaron contaminados:** el hueco sin latidos produjo un intervalo RR de 11.15 s que fue **aceptado**, con 0 exclusiones por calidad. Resultado: SDNN 1.1356 s, CV 1.6643 y RMSSD 1.6144 s en una ventana no-FA, valores imposibles. | **Corregido** |

**Causa.** `build_quality_mask()` marcaba una muestra como no utilizable solo si
era no finita o salía del rango físico. Una línea plana en ceros cumple ambas
condiciones, así que la máscara no marcaba nada y el RR que cruzaba el hueco
pasaba el control. Además la interfaz no entregaba la máscara a
`build_rr_intervals()`.

**Corrección.** Se añadió `flat_run_mask()` en `quality.py` (marca las muestras
de un tramo plano prolongado), `build_quality_mask()` la incorpora, y tanto
`ui.py` como `scripts/reproduce.py` pasan ahora la máscara a
`build_rr_intervals()`.

**Verificación posterior sobre la misma ventana:** 2 560 muestras (10.24 s)
marcadas como no utilizables, 1 RR excluido por calidad, RR máximo 0.58 s, y los
descriptores pasan a SDNN 0.0104 s, CV 0.0185 y RMSSD 0.015 s. Las 81 pruebas
siguen pasando y `results/summary.json` no cambia: las ventanas de comparación
no contienen tramos planos.

---

## 5. Superposición QRS

| Registro | Ventana | Ritmo | Hallazgo | Acción |
| :--- | :--- | :--- | :--- | :--- |
| 04043 | 1135.8–1195.8 s | FA anotada | El conteo de control se muestra desglosado: 120 detectados, 120 aceptados, 0 fuera de límites, 0 duplicados, 0 refractarios. | Conforme |
| 04043 | 5773.2–5833.2 s | No-FA anotado | 99 detectados, 99 aceptados, 0 descartados. | Conforme |

**Observación de usabilidad.** Con una ventana de 60 s a 250 Hz (15 000 muestras)
la vista pasa a envolvente mínimo-máximo de 3 750 puntos y las marcas QRS dejan
de dibujarse. La app lo explica y dice cómo resolverlo. Para revisar la
superposición marca a marca hay que usar ventanas de unos 16 s o subir el
control «Puntos dibujados». **El cálculo de QRS y RR se hace siempre sobre la
señal completa, no sobre la versión reducida.**

---

## 6. Coherencia entre ECG, RR, Poincaré y cronología

| Hallazgo | Acción |
| :--- | :--- |
| La selección de registro, canal y ventana se conserva al cambiar de página. Las cinco vistas muestran el mismo intervalo, las mismas unidades (mV, s, h) y la misma etiqueta de ritmo. En 05091 el tacograma, el histograma y el Poincaré reflejan la misma partición FA/no-FA y el mismo intervalo excluido. | Conforme |
| Con 19 intervalos válidos en no-FA, la app **impide** el resumen y muestra «Por debajo del mínimo de 30 RR válidos — No-FA anotado: 19», en vez de publicar descriptores inestables. | Conforme |
| En 06453 el control de duración de las ventanas se limita a 120 s, porque el episodio de FA disponible no admite más. La comparación se mantiene equivalente en lugar de comparar duraciones distintas. | Conforme |

---

## 7. Legibilidad, contraste y límites clínicos

| Hallazgo | Acción |
| :--- | :--- |
| Las etiquetas visibles son «FA anotada» y «no-FA anotado». No aparece «positivo», «negativo» ni «FA detectada» en ninguna vista. | Conforme |
| `AFL` («Flutter anotado») y «Sin anotación» se reportan en filas propias y quedan fuera de la comparación FA/no-FA, con nota explícita. | Conforme |
| El color nunca es el único portador de significado: cada serie lleva nombre en la leyenda y, en el Poincaré, la recta de identidad como referencia. | Conforme |
| El aviso de alcance clínico aparece en las cinco páginas. «Métodos y límites» lista los seis límites, incluida la advertencia de que SDNN, RMSSD y CV **no** se interpretan como modulación autonómica. | Conforme |
| Los parámetros mostrados (banda 0.5–40.0 Hz orden 4 fase cero, xqrs_detect, refractario 200 ms, umbrales de calidad, mínimo de 30 RR) provienen de `src/ecg_af_dashboard/config.py`; la interfaz no los redefine. | Conforme |

---

## Pendiente

Las seis ventanas marcadas «Pendiente» en la sección 1 (mitad y final de 04043,
inicio y final de 05091, inicio y final de 06453). Se completan fijando el
Inicio indicado con Duración 60 s y anotando el banner de calidad y el conteo de
RR de cada una.