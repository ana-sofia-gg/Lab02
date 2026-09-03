# Ficha de formulación — ECG AF Dashboard

Documento exigido por la sección 3.1 de la guía (Control D1). Se completa
antes de programar la interfaz y se actualiza si una decisión cambia.

---

## Problema

Exploración de episodios de fibrilación auricular **previamente anotados** en
registros ambulatorios de ECG de larga duración (≈10 h). Una gráfica estática
de pocos segundos no permite localizar episodios, contrastar segmentos ni
verificar cómo la calidad de la detección QRS afecta los intervalos RR. El
producto es un dashboard de exploración con trazabilidad sobre datos,
procesamiento, unidades y limitaciones.

## Usuario

Estudiante avanzado o investigador en Ingeniería Biomédica que necesita
seleccionar un registro, localizar episodios anotados en una línea de tiempo,
inspeccionar ECG crudo y procesado con marcas QRS, comparar segmentos FA y
no-FA del mismo registro, y reconocer cuándo la calidad impide una
interpretación responsable.

## Registros y criterio de selección

Criterio: se escogieron tres registros con **señal ECG disponible** (se
excluyen 00735 y 03665, que solo tienen anotaciones) que además cubrieran tres
condiciones estructurales distintas, para poner a prueba la robustez del
código y no solo el mejor caso visual.

| Registro | Rol en el conjunto | Condición estructural |
| :--- | :--- | :--- |
| 05091 | Caso base de referencia limpia | Completo, anotaciones de latido auditadas (`.qrsc`) |
| 04043 | Robustez ante huecos de datos | Bloque 39 ilegible (~10.24 s de ceros) |
| 06453 | Robustez ante series más cortas | Grabación incompleta (9 h 15 min) |

Los tres se muestrean a 250 Hz sobre 2 canales en mV. Se excluyó 07859 por su
problema histórico de alineación en las anotaciones QRS.

## Comparación

Segmento anotado como FA frente a segmento no anotado como FA **del mismo
registro**, con ventanas de duración equivalente. No se comparan sujetos
distintos: mezclar registros sin controlar diferencias individuales produce
una comparación metodológicamente débil.

## Ventana

Ventana: Máx 300 segundos. Se fija una duración inicial variable con el fin
de balancear la resolución temporal para ubicar episodios cortos de FA y la 
necesidad estadística de capturar suficientes latidos consecutivos.

## Detector QRS

`wfdb.processing.xqrs_detect`, envuelto en `src/ecg_af_dashboard/qrs.py`.

- **Entrada**: vector 1-D de ECG filtrado, finito, de al menos 2 s.
- **Control posterior** (`qrs_control.py`): descarta picos fuera de los
  límites de la señal, duplicados, los que violan un período refractario
  mínimo de **200 ms**, y los que caen en zonas marcadas como de mala calidad.
  Cada causa de descarte se cuenta por separado.
- **Limitaciones**: un falso positivo divide un intervalo RR; una detección
  perdida fusiona dos. Ambos errores pueden imitar o exagerar irregularidad,
  por lo que las marcas deben superponerse al ECG para ser revisables.

## Métrica principal

Carga anotada de FA en la selección:

$$\text{carga anotada de FA} = \frac{\text{tiempo anotado como (AFIB dentro de la ventana}}{\text{tiempo seleccionable}}$$

Unidad: proporción adimensional en `[0, 1]`. Implementada en
`src/ecg_af_dashboard/annotations.py.py` (`calculate_af_load`).

Descriptores de irregularidad RR que la acompañan: mediana e IQR, media y
desviación estándar, coeficiente de variación, RMSSD, y número y proporción
de intervalos excluidos.

Se recomineda un umbral mínimo de 30 intervalos RR válidos por ventana. Por 
debajo de esa cantidad (por ejemplo, debido a exclusiones por calidad o huecos 
de señal), la ventana se considera estadísticamente inestable.

Regla de asignación RR↔ritmo: un intervalo RR se acepta **solo si ambas
detecciones QRS caen dentro del mismo intervalo de ritmo**. Asignar por un
solo extremo incluiría transiciones y contaminaría la comparación.

## Calidad

Implementada en `src/ecg_af_dashboard/quality.py`. Una ventana se marca como
no comparable si supera alguno de estos umbrales:

| Indicador | Umbral | Justificación |
| :--- | :--- | :--- |
| Proporción de valores no finitos | > 1 % | Los NaN rompen el filtrado y la detección |
| Proporción fuera de rango físico | > 2 % de \|x\| > 5 mV | Amplitud de ECG de superficie por encima de lo fisiológico |
| Línea plana continua | > 1.2 s | 1.2 s equivale a 50 lpm; una pausa mayor sugiere pérdida de señal, no ritmo |

Efecto esperado: en 04043 el bloque 39 debe activar la marca de línea plana y
quedar excluido de la comparación, con el descarte contabilizado y visible.

Mensaje al usuario: «Calidad insuficiente para comparar» / «Ok».

## Criterio de éxito

Propuesta a validar: *el usuario selecciona un registro, localiza un
episodio de FA en la cronología, abre una ventana FA y una ventana no-FA de
igual duración en el mismo registro, y obtiene los descriptores RR de ambas
con el conteo de intervalos excluidos, o un aviso explícito de calidad
insuficiente.*

## Límite clínico

El dashboard es un **prototipo académico de exploración de registros
previamente anotados**. No diagnostica fibrilación auricular, no estima riesgo
individual, no recomienda tratamiento y no sustituye la revisión de un
profesional de la salud.

La etiqueta de FA proviene de las anotaciones `.atr` de referencia del
conjunto de datos; **no** es una conclusión generada por la aplicación. Por
eso la interfaz rotula «FA anotada» y «no-FA anotado», nunca «FA detectada»,
«positivo» o «negativo».

SDNN, RMSSD y medidas relacionadas se interpretan como descriptores de
irregularidad ventricular durante el segmento, **no** como estimación de
modulación autonómica: la FA altera la generación de la serie RR y hace
inapropiado trasladar interpretaciones de HRV obtenidas en ritmo sinusal.
