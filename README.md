# IPC Salud y per cápita del PDSS

Análisis del rubro de salud en el Índice de Precios al Consumidor (IPC) del Banco Central de la República Dominicana (BCRD), de enero 2021 a marzo 2026, y sus implicaciones para la indexación del per cápita base del Plan de Servicios de Salud (PDSS), régimen contributivo del Seguro Familiar de Salud.

Trabajo de investigación para la posición de Analista Científico de Datos en Inteligencia PDSS (ARS Humano).

## Qué incluye

| Pieza | Dónde |
| --- | --- |
| Limpieza de los archivos del BCRD → tablas en parquet | `src/01_limpieza.py` |
| Cálculos (inflación, brechas, incidencias, pesos, subyacencia, simulación del per cápita) | `src/02_calculos.py` |
| Control de consistencia: las cifras del ensayo salen de los datos | `src/03_verificacion.py` |
| Dashboard web (Python Dash + Plotly) | `app/app.py` |
| Datos originales del BCRD | `data/raw/` |
| Datos procesados (parquet) | `data/processed/` |

## Cómo correrlo

```bash
python -m venv .venv
# bash/zsh:     source .venv/bin/activate
# fish:         source .venv/bin/activate.fish
# Windows:      .venv\Scripts\activate
pip install -r requirements.txt

python src/01_limpieza.py     # data/raw  → 6 tablas en data/processed
python src/02_calculos.py     # data/processed → 8 tablas de resultados
python src/03_verificacion.py # revisa que las cifras del ensayo coincidan con los datos
python app/app.py             # dashboard en http://127.0.0.1:8050
```

Los parquet ya vienen incluidos en el repositorio, así que el dashboard se puede abrir directamente (`python app/app.py`) sin correr los dos scripts anteriores.

## Dashboard

Siete pestañas: **Resumen**, **Jerarquía de la canasta** (grupo, subgrupo, clase, subclase y artículo), **Peso e incidencia**, **Subyacencia**, **Per cápita PDSS**, **Simulador índice PDSS** y **Metodología**.

El **simulador** arma un índice de precios hipotético para el PDSS: se ajusta con deslizadores el peso de cada subgrupo de Salud (productos médicos, servicios para pacientes externos y hospital) y se ve qué habría dado en las dos indexaciones del per cápita (2022 y 2025) frente a lo aprobado. Los pesos son hipotéticos: los reales saldrían de la siniestralidad por tipo de servicio que las ARS reportan a SISALRIL, que no es pública.

## Publicar en Render

El dashboard está listo para publicarse como servicio web en [Render](https://render.com):

| Campo | Valor |
| --- | --- |
| Tipo | Web Service (conectar este repositorio de GitHub) |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn --chdir app app:server` |
| Python | 3.12 (lo fija el archivo `.python-version`) |

El dashboard lee los parquet de `data/processed/`, que ya están en el repositorio. En el plan gratuito el servicio se duerme tras 15 minutos sin uso y tarda cerca de 1 minuto en despertar.

## Datos

Fuente: BCRD → Estadísticas → Precios → "IPC base anual: octubre 2019 - septiembre 2020 = 100".

### Tablas limpias (`01_limpieza.py`)

| Tabla | Contenido |
| --- | --- |
| `catalogo_ipc` | Jerarquía de la canasta (612 nodos), ponderaciones, bien/servicio, transable y subyacente |
| `ipc_articulos` | Índice mensual de cada nodo de la canasta, octubre 2020 en adelante |
| `ipc_grupos` | Índice mensual de los 12 grupos, 1999 en adelante |
| `ipc_general` | Índice mensual del IPC general, 1984 en adelante |
| `ipc_subyacente` | Índice mensual del IPC subyacente, 2000 en adelante |
| `ipc_general_referencial` | IPC general con la canasta nueva, octubre 2019 – octubre 2021 |

### Tablas de resultados (`02_calculos.py`)

| Tabla | Contenido |
| --- | --- |
| `inflacion_nodos` | Índice e inflación mensual, interanual y acumulada (desde dic 2020) de los 612 nodos |
| `comparacion_salud` | IPC general vs salud (y variantes) con brechas |
| `incidencias` | Puntos de inflación general que aporta cada nodo |
| `peso_efectivo` | Peso real de cada nodo en la canasta, mes a mes |
| `subyacencia_tiempo` | IPC general vs subyacente |
| `subyacencia_peso` | Porción subyacente del peso de cada nodo |
| `simulacion_percapita` | Las dos indexaciones del per cápita (2022 y 2025) vs lo que habría dado el IPC general, el IPC salud, su promedio y salud ampliada, en % y RD$ |
| `historia_percapita` | Los aumentos del per cápita (oct 2021 – nov 2025) y de qué tipo fue cada uno: indexación o coberturas nuevas |

## Notas metodológicas

- **Fórmulas.** Mensual = índice ÷ índice del mes anterior − 1. Interanual = índice ÷ índice de 12 meses atrás − 1. Acumulada = índice ÷ índice de dic 2020 − 1. Peso efectivo = peso base × índice del nodo ÷ índice general. Incidencia = peso efectivo del mes anterior × inflación del nodo.
- **Controles.** Las incidencias de los 12 grupos suman la inflación general (diferencia máxima 0.0008 puntos porcentuales); el peso no subyacente de la canasta da 30.19%, igual que el BCRD; y las variaciones de la simulación del per cápita reproducen las cifras de referencia (±0.01 pp). `02_calculos.py` falla si alguno no se cumple.
- **Artículos desde oct 2020.** El BCRD publica los artículos solo desde octubre 2020; por eso la inflación interanual por subgrupo, clase, subclase o artículo existe desde octubre 2021. Antes se usa la variación acumulada desde dic 2020.
- **Seguro de salud.** El seguro de salud (artículo 1253101, peso 0.35%) está en el grupo 12, Bienes y Servicios Diversos, y no en el grupo Salud. El análisis lo muestra aparte ("salud ampliada").
- **Serie del IPC general.** La serie oficial está empalmada con base 2010; la serie referencial con la canasta nueva difiere hasta 0.88 puntos antes de sep 2020.
- **Periodo.** El BCRD publica datos hasta ago 2026; el análisis se recorta a mar 2026.
- **Per cápita.** Solo 2 de los 5 montos del per cápita (2022 y 2025) son indexación por precios; los demás agregaron coberturas o honorarios. Por eso la simulación compara únicamente los montos de indexación (RD$102.71 y RD$204.32) contra lo que habría dado cada índice en el mismo período (mar 2021 → mar 2022 con base RD$1,327.81; mar 2023 → mar 2025 con base RD$1,683.22), no contra el per cápita total.
