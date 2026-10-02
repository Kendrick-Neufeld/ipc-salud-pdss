"""
01_limpieza.py
Lee los archivos originales del BCRD (carpeta data/raw) y los convierte en
tablas ordenadas en data/processed.

Cómo correrlo (desde la carpeta del proyecto):
    python src/01_limpieza.py

Tablas que produce:
    catalogo_ipc        una fila por nodo de la canasta (grupo ... artículo)
    ipc_articulos       índice mensual de cada nodo, oct 2020 en adelante
    ipc_grupos          índice mensual de los 12 grupos, 1999 en adelante
    ipc_general         índice mensual del IPC general, 1984 en adelante
    ipc_subyacente      índice mensual del IPC subyacente, 2000 en adelante
    ipc_general_referencial  IPC general con la canasta nueva, oct 2019 - oct 2021

Nota: el BCRD solo publica artículos desde oct 2020. Por eso la inflación
interanual por artículo/subgrupo/clase existe desde oct 2021; para ene-sep 2021
se usa la variación acumulada desde dic 2020. A nivel de grupo sí hay serie completa.
"""
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
OUT = RAIZ / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
         "noviembre": 11, "diciembre": 12}
NIVELES = ["grupo", "subgrupo", "clase", "subclase", "articulo"]


def guardar(df: pd.DataFrame, nombre: str) -> None:
    """Guarda en parquet; si falta pyarrow, guarda en CSV y avisa."""
    try:
        df.to_parquet(OUT / f"{nombre}.parquet", index=False)
        print(f"  ok  {nombre}.parquet  ({len(df):,} filas)")
    except ImportError:
        df.to_csv(OUT / f"{nombre}.csv", index=False)
        print(f"  ok  {nombre}.csv  ({len(df):,} filas)  [instala pyarrow para parquet]")


def mes_a_numero(texto) -> int | None:
    if texto is None or pd.isna(texto):
        return None
    return MESES.get(str(texto).strip().lower())


# ---------------------------------------------------------------- artículos
def leer_articulos():
    """Hoja '2020-2026': columnas A-E = jerarquía, F = ponderación,
    G en adelante = un mes cada columna, empezando en octubre 2020."""
    hoja = pd.read_excel(RAW / "ipc_articulos_base_2019-2020.xlsx",
                         sheet_name="2020-2026", header=None)
    meses = hoja.iloc[3, 6:]                      # fila 4: nombres de meses
    meses = meses[meses.notna()]
    fechas = pd.date_range("2020-10-01", periods=len(meses), freq="MS")
    # verificación: cada encabezado debe coincidir con el mes calculado
    for f, m in zip(fechas, meses):
        assert mes_a_numero(m) == f.month, f"Mes inesperado: {m} vs {f:%Y-%m}"

    catalogo, series = [], []
    padres = {}                                   # último código visto por nivel
    for _, fila in hoja.iloc[4:].iterrows():
        textos = fila.iloc[:5]
        if textos.notna().sum() == 0:
            continue
        nivel_i = int(textos.notna().values.argmax())
        texto = str(textos.iloc[nivel_i]).strip()
        if texto.lower().startswith("indice general"):
            codigo, nombre, nivel = "00", "Índice General", "general"
            padre = None
        else:
            codigo, nombre = texto.split(" ", 1)
            nivel = NIVELES[nivel_i]
            padre = padres.get(nivel_i - 1)
            padres[nivel_i] = codigo
        catalogo.append({"codigo": codigo, "nombre": nombre.strip(),
                         "nivel": nivel, "padre": padre,
                         "grupo": codigo[:2], "ponderacion": float(fila.iloc[5])})
        valores = pd.to_numeric(fila.iloc[6:6 + len(fechas)], errors="coerce").values
        series.append(pd.DataFrame({"fecha": fechas, "codigo": codigo,
                                    "indice": valores}))

    catalogo = pd.DataFrame(catalogo)
    series = pd.concat(series, ignore_index=True).dropna(subset=["indice"])
    return catalogo, series


def agregar_atributos(catalogo: pd.DataFrame) -> pd.DataFrame:
    """Del anexo metodológico: bien/servicio, transable y subyacente."""
    anexo = pd.read_excel(RAW / "anexos_metodologia_ipc_2019-2020.xlsx",
                          sheet_name="Ponderadores por componentes", header=None)
    attrs = anexo.iloc[3:, 4:9].dropna(subset=[4])
    attrs.columns = ["texto", "pond_anexo", "bien_servicio", "transable", "subyacente"]
    attrs["codigo"] = attrs["texto"].astype(str).str.split(" ").str[0]
    attrs["subyacente"] = attrs["subyacente"].astype(str).str.strip().map(
        {"Suby": True, "Ex": False})
    attrs["bien_servicio"] = attrs["bien_servicio"].map({"B": "Bien", "S": "Servicio"})
    attrs["transable"] = attrs["transable"].map({"T": True, "NT": False})
    return catalogo.merge(attrs[["codigo", "bien_servicio", "transable", "subyacente"]],
                          on="codigo", how="left")


# --------------------------------------------------- series largas (año/mes)
def leer_serie_anio_mes(archivo, col_anio, col_mes, columnas, saltar):
    """Lee hojas donde el año aparece una vez y luego vienen los meses."""
    hoja = pd.read_excel(RAW / archivo, header=None)
    filas, anio = [], None
    for _, fila in hoja.iloc[saltar:].iterrows():
        a = fila.iloc[col_anio]
        if isinstance(a, (int, float)) and not pd.isna(a) and 1900 < a < 2100:
            anio = int(a)
        elif isinstance(a, str) and a.strip().isdigit():
            anio = int(a.strip())
        mes = mes_a_numero(fila.iloc[col_mes])
        if anio and mes:
            reg = {"fecha": pd.Timestamp(anio, mes, 1)}
            for nombre, j in columnas.items():
                reg[nombre] = pd.to_numeric(fila.iloc[j], errors="coerce")
            filas.append(reg)
    return pd.DataFrame(filas).dropna()


def leer_grupos():
    hoja = pd.read_excel(RAW / "ipc_grupos_base_2019-2020.xls", header=None)
    nombres = {j: str(v).strip() for j, v in hoja.iloc[3].items() if j > 0 and pd.notna(v)}
    ancho = leer_serie_anio_mes("ipc_grupos_base_2019-2020.xls", 0, 0,
                                {n: j for j, n in nombres.items()}, saltar=6)
    largo = ancho.melt(id_vars="fecha", var_name="grupo_nombre", value_name="indice")
    codigos = {n: f"{i + 1:02d}" for i, n in enumerate(nombres.values())}
    largo["codigo"] = largo["grupo_nombre"].map(codigos)
    return largo[["fecha", "codigo", "grupo_nombre", "indice"]]


def main():
    print("Leyendo archivos del BCRD...")
    catalogo, articulos = leer_articulos()
    catalogo = agregar_atributos(catalogo)

    general = leer_serie_anio_mes("ipc_base_2019-2020.xls", 0, 1,
                                  {"indice": 2}, saltar=7)
    subyacente = leer_serie_anio_mes("ipc_subyacente_base_2019-2020.xlsx", 0, 1,
                                     {"indice": 2}, saltar=32)
    grupos = leer_grupos()
    # IPC general calculado con la canasta nueva desde oct 2019 (sin empalme)
    referencial = leer_serie_anio_mes("ipc_base_2019-2020_serie_referencial.xlsx",
                                      0, 1, {"indice": 2}, saltar=6)

    # --- validaciones -------------------------------------------------------
    hijos = catalogo[catalogo["padre"].notna()].groupby("padre")["ponderacion"].sum()
    padres = catalogo.set_index("codigo")["ponderacion"]
    diferencia = (hijos - padres.reindex(hijos.index)).abs()
    assert diferencia.max() < 0.001, f"Ponderaciones no cuadran:\n{diferencia.nlargest(5)}"
    total = catalogo.loc[catalogo["nivel"] == "grupo", "ponderacion"].sum()
    assert abs(total - 100) < 0.001, f"Los grupos suman {total}, no 100"
    # el índice general del archivo de artículos debe coincidir con el IPC general
    comp = articulos[articulos["codigo"] == "00"].merge(general, on="fecha",
                                                       suffixes=("_art", "_gen"))
    assert (comp["indice_art"] - comp["indice_gen"]).abs().max() < 0.01
    print(f"Validaciones OK: {len(catalogo)} nodos, grupos suman {total:.4f}")

    print("Guardando en data/processed...")
    guardar(catalogo, "catalogo_ipc")
    guardar(articulos, "ipc_articulos")
    guardar(grupos, "ipc_grupos")
    guardar(general, "ipc_general")
    guardar(subyacente, "ipc_subyacente")
    guardar(referencial, "ipc_general_referencial")


if __name__ == "__main__":
    main()
