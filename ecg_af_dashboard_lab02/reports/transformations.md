# Tabla de transformaciones (Actividad 3.1)

Cada operación aplicada a la señal responde a una interferencia concreta o a
una etapa analítica. Ninguna se aplica para que el trazado «se vea mejor».

Los parámetros viven en `src/ecg_af_dashboard/config.py` y se vuelcan a
`results/parameters.json` en cada reproducción.

---

| Operación | Entrada | Parámetros | Salida | Justificación | Riesgo |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Filtro de inspección** | ECG físico validado (mV) | Butterworth pasabanda, 0.5–40 Hz, orden 4, fase cero (`sosfiltfilt`) | ECG procesado (mV) | Atenúa deriva de línea base e interferencia de alta frecuencia sin desplazar temporalmente los complejos. Los cortes se mantienen dentro del ancho de banda de adquisición del AFDB (≈0.1–40 Hz). | El corte inferior de 0.5 Hz puede atenuar el segmento ST y componentes lentas de la onda T; el trazado no sirve para morfología ST. |
| **Transformación QRS** | ECG procesado | `wfdb.processing.xqrs_detect` con la `fs` del encabezado | Índices de muestra de picos candidatos | Detector de referencia documentado, revisable contra las anotaciones `.qrs` como control auxiliar. | Falsos positivos por artefacto y detecciones perdidas en complejos atípicos. Un falso positivo divide un RR; una pérdida fusiona dos. Ambos imitan o exageran irregularidad. |
| **Máscara de calidad** | Ventana de ECG físico | No finitos > 1 %; \|x\| > 5 mV en > 2 % de las muestras; línea plana continua > 1.2 s | Booleano por ventana + mensaje | Impide comparar segmentos cuya señal no soporta la comparación. Los tres indicadores miden fenómenos distintos: datos ausentes, saturación y pérdida de señal. | Exclusión sesgada si un registro concentra los descartes. Por eso el conteo por causa queda visible y no se agrega silenciosamente. |
| **Control de detecciones QRS** | Picos candidatos + máscara | Período refractario mínimo 200 ms; límites de la señal; unicidad | Índices aceptados + conteo por causa | Elimina duplicados, marcas fuera de la señal y pares fisiológicamente imposibles. | Descartar por período refractario puede perder latidos reales muy prematuros. El conteo separado permite auditarlo. |
| **Construcción de RR** | Picos aceptados + intervalos de ritmo | Ambos extremos en el mismo intervalo de ritmo; sin muestras marcadas como no válidas; límites fisiológicos **desactivados** | Serie RR etiquetada + causa de exclusión | Un RR que cruza una transición no representa a ninguno de los dos ritmos. La calidad se evalúa sobre todo el tramo, no solo en los extremos. | Descartar RR por ser extremos borraría justamente la irregularidad estudiada. Por eso los límites fisiológicos están apagados por defecto. |
| **Reducción para pantalla** | Ventana ya seleccionada | Envolvente mínimo-máximo por bloques, solo si quedan demasiados puntos | Serie dibujable | Un registro de 10 h no cabe en una figura. Se selecciona primero la ventana y después se reduce. | Ocultar eventos breves si se diezma sin criterio. **Nunca se usa para calcular métricas**: QRS y RR se computan sobre datos completos. |

---

## Tres representaciones separadas

El proyecto mantiene diferenciadas, y nunca las intercambia:

1. **Señal física original** leída de WFDB, en mV, tal como está en `data/raw/`.
2. **Señal procesada** para inspección visual (filtro de la primera fila).
3. **Transformación interna del detector**, que XQRS aplica por su cuenta.

El filtrado del detector no se presenta como un ECG equivalente al original.
Cuando ambas se dibujan juntas, la leyenda las distingue explícitamente.

## Por qué el filtrado no es causal

`sosfiltfilt` aplica el filtro hacia adelante y hacia atrás. El resultado no
tiene desfase, lo que permite superponer las marcas QRS sobre el trazado sin
corregir un retardo. A cambio, cada muestra de salida depende de muestras
futuras: el método sirve para análisis fuera de línea y **no** describe una
operación en tiempo real. Tampoco recupera contenido espectral que la cadena
de adquisición analógica nunca registró.
