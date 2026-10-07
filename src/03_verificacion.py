"""
03_verificacion.py
Revisa que las cifras que cita el ensayo salgan de los datos. Si alguna cifra
no coincide, el script lo dice y termina con error (así nadie publica números
que no cuadran).

Cómo correrlo (desde la carpeta del proyecto, después de 02_calculos.py):
    python src/03_verificacion.py
"""
import sys
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"
sys.path.insert(0, str(RAIZ / "app"))

comp = pd.read_parquet(PROC / "comparacion_salud.parquet").set_index("fecha")
inf = pd.read_parquet(PROC / "inflacion_nodos.parquet")
pef = pd.read_parquet(PROC / "peso_efectivo.parquet")
MAR26 = pd.Timestamp("2026-03-01")

resultados = []  # (nombre, valor calculado, valor esperado, ok)


def revisar(nombre, calculado, esperado, decimales):
    """Compara el valor calculado (redondeado) con el que cita el ensayo."""
    ok = abs(round(float(calculado), decimales) - esperado) < 1e-9
    resultados.append((nombre, round(float(calculado), decimales), esperado, ok))


# 1) Inflación acumulada dic 2020 → mar 2026 (%, 1 decimal)
for col, nombre, esperado in [("acum_general", "IPC general", 32.3), ("acum_salud", "IPC salud", 30.3),
                              ("acum_seguro_salud", "Seguro de salud", 57.4),
                              ("acum_servicios_medicos", "Servicios médicos", 53.2),
                              ("acum_farmaceuticos", "Productos farmacéuticos", 29.6),
                              ("acum_hospital", "Servicios de hospital", 22.9)]:
    revisar(f"Acumulado dic 2020→mar 2026: {nombre}", comp.loc[MAR26, col], esperado, 1)

# 2) Inflación interanual en marzo 2026 (%, 2 decimales)
revisar("Interanual mar 2026: IPC salud", comp.loc[MAR26, "interanual_salud"], 5.53, 2)
revisar("Interanual mar 2026: IPC general", comp.loc[MAR26, "interanual_general"], 4.63, 2)

# 3) Peso efectivo de salud en marzo 2026 (% de la canasta, 2 decimales)
peso = pef[(pef["codigo"] == "06") & (pef["fecha"] == MAR26)]["peso_efectivo"].iloc[0]
revisar("Peso efectivo de Salud, mar 2026", peso, 4.69, 2)

# 4) Inflación diciembre contra diciembre, 2021 a 2025 (%, 2 decimales)
general = {2021: 8.50, 2022: 7.83, 2023: 3.57, 2024: 3.35, 2025: 4.95}
salud = {2021: 4.85, 2022: 5.19, 2023: 4.84, 2024: 5.30, 2025: 5.10}
for anio in general:
    f = pd.Timestamp(f"{anio}-12-01")
    revisar(f"Dic {anio}: IPC general", comp.loc[f, "interanual_general"], general[anio], 2)
    revisar(f"Dic {anio}: IPC salud", comp.loc[f, "interanual_salud"], salud[anio], 2)

# 5) Cifras que usa el dashboard (KPI y simulador)
u = inf[(inf["fecha"] == MAR26) & (inf["grupo"] == "06") & (inf["nivel"] == "clase")]
mejor = u.loc[u["var_acum_dic2020"].idxmax()]
resultados.append(("La clase de Salud que más subió es 'Servicios médicos'", mejor["nombre"],
                   "Servicios médicos", mejor["nombre"] == "Servicios médicos"))

import app as dash_app  # el dashboard; aquí solo se usan sus funciones de cálculo

for cod, esperado in zip(("061", "062", "063"), (69.87, 19.35, 10.78)):
    revisar(f"Peso del subgrupo {cod} dentro de Salud (%)", dash_app.PESOS_IPC[cod], esperado, 2)

# con los pesos del IPC, el índice PDSS debe quedar muy cerca del IPC salud
pdss = dash_app.indice_pdss(dash_app.PESOS_IPC)
dif = abs((pdss.loc[MAR26] - 100) - comp.loc[MAR26, "acum_salud"])
resultados.append(("Simulador con pesos IPC ≈ IPC salud (dif. en pp de acumulada < 0.5)",
                   round(dif, 3), "< 0.5", dif < 0.5))

# ------------------------------------------------------------------- resultado
print(f"{'':2}{'Control':72} {'Calculado':>12} {'Esperado':>10}")
for nombre, calc, esp, ok in resultados:
    print(f"{'ok' if ok else 'XX':2}{nombre:72} {str(calc):>12} {str(esp):>10}")
print("\nNota: los pesos exactos de los subgrupos de Salud son 69.87 / 19.35 / 10.78. A un decimal quedan\n"
      "69.9 / 19.3 / 10.8 (suman 100.0), que son los que usan el ensayo y el simulador.")
fallos = [r for r in resultados if not r[3]]
print(f"\n{len(resultados) - len(fallos)} de {len(resultados)} controles pasan.")
if fallos:
    sys.exit(f"FALLARON {len(fallos)} controles: revisar antes de publicar.")
