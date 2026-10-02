"""
02_calculos.py
Toma las tablas limpias de data/processed y calcula todo lo que pide el análisis:
inflación, brecha salud/general, incidencias, peso efectivo, subyacencia y la
simulación de indexación del per cápita del PDSS.

Cómo correrlo (desde la carpeta del proyecto):
    python src/02_calculos.py

Tablas que produce (en data/processed):
    inflacion_nodos      índice e inflación (mensual, interanual, acumulada) de los 612 nodos
    comparacion_salud    IPC general vs salud (y variantes) con brechas, ene 2021 - mar 2026
    incidencias          cuántos puntos aporta cada nodo a la inflación general
    peso_efectivo        peso real de cada nodo en la canasta mes a mes
    subyacencia          IPC general vs subyacente, y peso subyacente por nodo
    simulacion_percapita cuánto valdría el per cápita indexado con cada índice

Ideas clave:
  - Inflación mensual      = índice_t / índice_(t-1) - 1
  - Inflación interanual   = índice_t / índice_(t-12) - 1
  - Acumulada              = índice_t / índice_(dic 2020) - 1
  - Peso efectivo          = peso_base * índice_nodo / índice_general
    (si una cosa sube más que el promedio, pesa más en el bolsillo que su peso base)
  - Incidencia             = peso efectivo del mes anterior * inflación del nodo
    (las incidencias de los 12 grupos suman la inflación general)
"""
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
PROC = RAIZ / "data" / "processed"

DESDE = pd.Timestamp("2021-01-01")   # inicio del análisis pedido
HASTA = pd.Timestamp("2026-03-01")   # fin del análisis pedido
BASE_ACUM = pd.Timestamp("2020-12-01")  # mes base de la variación acumulada

SALUD = "06"
SEGURO_SALUD = "1253101"  # vive en el grupo 12, pero es salud de verdad

# --- Per cápita PDSS régimen contributivo (CNSS/SISALRIL) ------------------
# SUPUESTO A CONFIRMAR: el CLAUDE.md no dice desde qué mes rige RD$1,327.81.
# Aquí se toma dic 2020 como punto de partida de la simulación. Si es otra
# fecha, cambia PERCAPITA_BASE_FECHA y vuelve a correr el script.
PERCAPITA_BASE_FECHA = pd.Timestamp("2020-12-01")
PERCAPITA_BASE = 1327.81
PERCAPITA_REAL = {   # valores aprobados con fecha conocida
    pd.Timestamp("2023-02-01"): 1555.14,
    pd.Timestamp("2023-11-01"): 1683.22,
    pd.Timestamp("2025-10-01"): 1887.54,
}


def guardar(df: pd.DataFrame, nombre: str) -> None:
    df.to_parquet(PROC / f"{nombre}.parquet", index=False)
    print(f"  ok  {nombre}.parquet  ({len(df):,} filas)")


# ------------------------------------------------------------ series de índices
def armar_series(catalogo, articulos, grupos, general):
    """Una tabla larga (fecha, codigo, indice) con TODOS los nodos.
    Para el general y los 12 grupos usa la serie larga (desde 1999/1984), así
    la inflación interanual de 2021 se puede calcular. Para el resto de nodos
    solo hay datos desde oct 2020."""
    # control: grupos de la serie larga deben coincidir con los de la serie de artículos
    comun = grupos.merge(articulos, on=["fecha", "codigo"], suffixes=("_l", "_a"))
    dif = (comun["indice_l"] - comun["indice_a"]).abs().max()
    assert dif < 0.01, f"grupos no coinciden entre archivos (dif máx {dif})"

    largas = pd.concat([
        grupos[["fecha", "codigo", "indice"]],
        general.assign(codigo="00")[["fecha", "codigo", "indice"]],
    ])
    resto = articulos[~articulos["codigo"].isin(largas["codigo"].unique())]
    series = pd.concat([largas, resto[["fecha", "codigo", "indice"]]])
    return series.sort_values(["codigo", "fecha"]).reset_index(drop=True)


def calcular_inflacion(series, catalogo):
    series = series.copy()
    g = series.groupby("codigo")["indice"]
    series["var_mensual"] = g.pct_change(1) * 100
    series["var_interanual"] = g.pct_change(12) * 100
    base = (series[series["fecha"] == BASE_ACUM].set_index("codigo")["indice"])
    series["var_acum_dic2020"] = (series["indice"] / series["codigo"].map(base) - 1) * 100
    series = series[(series["fecha"] >= DESDE) & (series["fecha"] <= HASTA)]
    return series.merge(
        catalogo[["codigo", "nombre", "nivel", "grupo", "ponderacion"]],
        on="codigo", how="left")


# ------------------------------------------------------------- peso e incidencia
def peso_e_incidencias(inflacion, articulos, catalogo):
    """Peso efectivo e incidencias para todos los nodos (desde oct 2020, que
    es cuando existen los índices de todos los nodos)."""
    ind = articulos.pivot(index="fecha", columns="codigo", values="indice")
    peso_base = catalogo.set_index("codigo")["ponderacion"].reindex(ind.columns)
    general = ind["00"]
    # peso efectivo en % de la canasta de cada mes
    efectivo = ind.mul(peso_base, axis=1).div(general, axis=0)

    var_mes = ind.pct_change(1) * 100
    var_anio = ind.pct_change(12) * 100
    inc_mes = efectivo.shift(1) * var_mes / 100       # en puntos porcentuales
    inc_anio = efectivo.shift(12) * var_anio / 100

    def largo(df, nombre):
        return (df.stack().rename(nombre).reset_index()
                  .rename(columns={"level_0": "fecha"}))
    ef = largo(efectivo, "peso_efectivo")
    inc = (largo(inc_mes, "incidencia_mensual")
           .merge(largo(inc_anio, "incidencia_interanual"), on=["fecha", "codigo"], how="left"))
    for t in (ef, inc):
        t.drop(t[(t["fecha"] < DESDE) | (t["fecha"] > HASTA)].index, inplace=True)
    cols = ["codigo", "nombre", "nivel", "grupo"]
    ef = ef.merge(catalogo[cols + ["ponderacion"]], on="codigo")
    inc = inc.merge(catalogo[cols], on="codigo")

    # control: las incidencias de los 12 grupos deben sumar la inflación mensual general
    grupos = catalogo.loc[catalogo["nivel"] == "grupo", "codigo"]
    suma = inc[inc["codigo"].isin(grupos)].groupby("fecha")["incidencia_mensual"].sum()
    oficial = inflacion[inflacion["codigo"] == "00"].set_index("fecha")["var_mensual"]
    dif = (suma - oficial.reindex(suma.index)).abs().max()
    print(f"  control incidencias: dif. máx. entre suma de grupos y general = {dif:.4f} pp")
    return ef, inc


# ------------------------------------------------------ comparación salud/general
def comparar_salud(series, desde=DESDE):
    """Tabla ancha: general, salud, salud ampliada (con seguro), y sus brechas."""
    ind = series.pivot(index="fecha", columns="codigo", values="indice")
    cat = pd.read_parquet(PROC / "catalogo_ipc.parquet").set_index("codigo")["ponderacion"]
    w_s, w_seg = cat[SALUD], cat[SEGURO_SALUD]
    # salud ampliada = salud + seguro de salud, promedio ponderado por peso base
    ind["amp"] = (w_s * ind[SALUD] + w_seg * ind[SEGURO_SALUD]) / (w_s + w_seg)
    cols = {"00": "general", SALUD: "salud", "amp": "salud_ampliada",
            SEGURO_SALUD: "seguro_salud", "0621": "servicios_medicos",
            "0611": "farmaceuticos", "0631": "hospital"}
    out = pd.DataFrame(index=ind.index)
    for cod, nom in cols.items():
        s = ind[cod]
        out[f"indice_{nom}"] = s
        out[f"mensual_{nom}"] = s.pct_change(1) * 100
        out[f"interanual_{nom}"] = s.pct_change(12) * 100
        out[f"acum_{nom}"] = (s / s.loc[BASE_ACUM] - 1) * 100
    out["brecha_interanual_salud_general"] = out["interanual_salud"] - out["interanual_general"]
    out["brecha_acum_salud_general"] = out["acum_salud"] - out["acum_general"]
    out["brecha_interanual_ampliada_general"] = (
        out["interanual_salud_ampliada"] - out["interanual_general"])
    out = out.reset_index().rename(columns={"index": "fecha"})
    return out[(out["fecha"] >= desde) & (out["fecha"] <= HASTA)].reset_index(drop=True)


# ------------------------------------------------------------------ subyacencia
def subyacencia(general, subyacente, catalogo):
    """(a) inflación general vs subyacente; (b) cuánto de cada nodo es subyacente."""
    t = general.rename(columns={"indice": "indice_general"}).merge(
        subyacente.rename(columns={"indice": "indice_subyacente"}), on="fecha")
    for c in ("general", "subyacente"):
        t[f"mensual_{c}"] = t[f"indice_{c}"].pct_change(1) * 100
        t[f"interanual_{c}"] = t[f"indice_{c}"].pct_change(12) * 100
    t["brecha_interanual_gen_sub"] = t["interanual_general"] - t["interanual_subyacente"]
    t = t[(t["fecha"] >= DESDE) & (t["fecha"] <= HASTA)].reset_index(drop=True)

    # peso subyacente de cada nodo = suma del peso de sus artículos subyacentes.
    # Cada artículo "reparte" su peso a todos sus ancestros (subclase, clase, ...).
    padre = catalogo.set_index("codigo")["padre"]
    filas = []
    for art in catalogo[catalogo["nivel"] == "articulo"].itertuples():
        es_sub = art.subyacente is True
        nodo = art.codigo
        while isinstance(nodo, str):  # sube por padre hasta llegar al grupo
            filas.append((nodo, art.ponderacion, art.ponderacion if es_sub else 0.0))
            nodo = padre[nodo]
    p = (pd.DataFrame(filas, columns=["codigo", "peso_total", "peso_subyacente"])
           .groupby("codigo").sum().reset_index())
    p["pct_subyacente"] = p["peso_subyacente"] / p["peso_total"] * 100
    p = catalogo[["codigo", "nombre", "nivel", "grupo"]].merge(p, on="codigo", how="inner")
    return t, p


# ---------------------------------------------------------- simulación per cápita
def simular_percapita(comparacion_larga):
    """¿Cuánto valdría el per cápita si se hubiera indexado con cada índice?
    valor_t = PERCAPITA_BASE * índice_t / índice_(fecha base)"""
    ind = comparacion_larga.set_index("fecha")
    i0 = PERCAPITA_BASE_FECHA
    esquemas = {"IPC general": "indice_general", "IPC salud": "indice_salud",
                "IPC salud ampliada": "indice_salud_ampliada",
                "Servicios médicos": "indice_servicios_medicos",
                "Productos farmacéuticos": "indice_farmaceuticos",
                "Servicios de hospital": "indice_hospital"}
    filas = []
    for nombre, col in esquemas.items():
        s = ind[col]
        valor = PERCAPITA_BASE * s / s.loc[i0]
        for f, v in valor[valor.index >= i0].items():
            filas.append((f, nombre, v))
    out = pd.DataFrame(filas, columns=["fecha", "esquema", "per_capita"])
    real = pd.Series(PERCAPITA_REAL, name="per_capita_aprobado")
    out = out.merge(real, left_on="fecha", right_index=True, how="left")
    return out


def main():
    print("Leyendo tablas limpias...")
    catalogo = pd.read_parquet(PROC / "catalogo_ipc.parquet")
    articulos = pd.read_parquet(PROC / "ipc_articulos.parquet")
    grupos = pd.read_parquet(PROC / "ipc_grupos.parquet")
    general = pd.read_parquet(PROC / "ipc_general.parquet")
    subyacente = pd.read_parquet(PROC / "ipc_subyacente.parquet")

    print("Calculando...")
    series = armar_series(catalogo, articulos, grupos, general)
    inflacion = calcular_inflacion(series, catalogo)
    efectivo, incidencias = peso_e_incidencias(inflacion, articulos, catalogo)
    comparacion = comparar_salud(series)
    sub_tiempo, sub_peso = subyacencia(general, subyacente, catalogo)
    # la simulación necesita desde dic 2020, así que usa la serie sin recortar
    comp_larga = comparar_salud(series, desde=BASE_ACUM)
    percapita = simular_percapita(comp_larga)

    print("Guardando en data/processed...")
    guardar(inflacion, "inflacion_nodos")
    guardar(comparacion, "comparacion_salud")
    guardar(incidencias, "incidencias")
    guardar(efectivo, "peso_efectivo")
    guardar(sub_tiempo, "subyacencia_tiempo")
    guardar(sub_peso, "subyacencia_peso")
    guardar(percapita, "simulacion_percapita")


if __name__ == "__main__":
    main()
