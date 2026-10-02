"""
app.py
Dashboard del IPC de Salud y per cápita del PDSS (Dash + Plotly).

Cómo correrlo (desde la carpeta del proyecto):
    python app/app.py
y abrir http://127.0.0.1:8050 en el navegador.

Lee los parquet que dejan los scripts 01 y 02 (carpeta data/processed).
Los estilos (colores, tarjetas) están en app/assets/style.css.
"""
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, dash_table

PROC = Path(__file__).resolve().parents[1] / "data" / "processed"

# --------------------------------------------------------------------- datos
cat = pd.read_parquet(PROC / "catalogo_ipc.parquet")
inf = pd.read_parquet(PROC / "inflacion_nodos.parquet")
comp = pd.read_parquet(PROC / "comparacion_salud.parquet")
inc = pd.read_parquet(PROC / "incidencias.parquet")
pef = pd.read_parquet(PROC / "peso_efectivo.parquet")
sub_t = pd.read_parquet(PROC / "subyacencia_tiempo.parquet")
sub_p = pd.read_parquet(PROC / "subyacencia_peso.parquet")
sim = pd.read_parquet(PROC / "simulacion_percapita.parquet")

NOMBRE = cat.set_index("codigo")["nombre"].to_dict()
FECHA_FIN = comp["fecha"].max()
MES_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def etiqueta_mes(f: pd.Timestamp) -> str:
    return f"{MES_ES[f.month - 1]} {f.year}"


def opciones_meses(desde=None):
    fechas = comp["fecha"] if desde is None else comp.loc[comp["fecha"] >= desde, "fecha"]
    return [{"label": etiqueta_mes(f), "value": f.strftime("%Y-%m-%d")} for f in fechas]


# ------------------------------------------------------------------- colores
# Paleta validada (ver CLAUDE.md / skill dataviz): el protagonista es Salud (azul);
# lo demás es contexto (gris) o la segunda variante (naranja).
TINTA, TINTA_2 = "#0b0b0b", "#52514e"
GRIS, GRIS_CLARO, REJILLA = "#8a8985", "#c9c8c3", "#ecebe8"
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SERIES = [AZUL, NARANJA, AQUA, "#eda100", "#e87ba4", "#008300"]  # orden fijo
ROJO = "#e34948"
SECUENCIAL = [[0, "#cde2fb"], [0.5, "#5598e7"], [1, "#104281"]]
CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


def figura(alto=380, titulo_y=None, y_cero=False, leyenda=True) -> go.Figure:
    """Figura vacía con el estilo común: fondo blanco, rejilla suave, leyenda arriba."""
    fig = go.Figure()
    fig.update_layout(
        height=alto, margin=dict(l=56, r=16, t=84 if leyenda else 24, b=40),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Calibri, Carlito, Helvetica, Arial, sans-serif", size=13, color=TINTA_2),
        hovermode="x unified", showlegend=leyenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(font_size=12),
        xaxis=dict(showgrid=False, linecolor=GRIS_CLARO, tickformat="%m/%Y", hoverformat="%b %Y"),
        yaxis=dict(gridcolor=REJILLA, zeroline=True, zerolinecolor=GRIS_CLARO,
                   title=titulo_y, rangemode="tozero" if y_cero else "normal"),
    )
    return fig


def linea(fig, x, y, nombre, color, dash=None, ancho=2.5):
    fig.add_trace(go.Scatter(x=x, y=y, name=nombre, mode="lines",
                             line=dict(color=color, width=ancho, dash=dash),
                             hovertemplate="%{y:.2f}"))


# --------------------------------------------------------------- tarjetas / KPI
def tarjeta(titulo, subtitulo, hijo):
    return html.Div(className="card", children=[
        html.H3(titulo), html.P(subtitulo, className="sub"), hijo])


def grafico(id_, **kw):
    return dcc.Graph(id=id_, config=CONFIG, **kw)


def kpi(etiqueta, valor, detalle):
    return html.Div(className="kpi", children=[
        html.Div(etiqueta, className="kpi-label"),
        html.Div(valor, className="kpi-value"),
        html.Div(detalle, className="kpi-detail")])


def pct(x, signo=False):
    return f"{x:+.1f}%" if signo else f"{x:.1f}%"


# ===================================================================== TAB 1
ult = comp[comp["fecha"] == FECHA_FIN].iloc[0]
peso_base_salud = cat.loc[cat["codigo"] == "06", "ponderacion"].iloc[0]
peso_ef_salud = pef[(pef["codigo"] == "06") & (pef["fecha"] == FECHA_FIN)]["peso_efectivo"].iloc[0]

kpis = html.Div(className="kpis", children=[
    kpi("IPC general, acumulado", pct(ult["acum_general"]), "dic 2020 → mar 2026"),
    kpi("IPC Salud, acumulado", pct(ult["acum_salud"]),
        f"con seguro de salud: {pct(ult['acum_salud_ampliada'])}"),
    kpi("Servicios médicos, acumulado", pct(ult["acum_servicios_medicos"]),
        "el componente que más subió"),
    kpi("Inflación interanual, mar 2026",
        f"{ult['interanual_salud']:.1f}% vs {ult['interanual_general']:.1f}%", "salud vs general"),
    kpi("Peso de Salud en la canasta", f"{peso_base_salud:.2f}%",
        f"peso efectivo mar 2026: {peso_ef_salud:.2f}%"),
])


def fig_indice():
    fig = figura(titulo_y="Índice (dic 2020 = 100)")
    for col, nom, color in [("general", "IPC general", GRIS), ("salud", "IPC Salud", AZUL),
                            ("salud_ampliada", "Salud + seguro de salud", NARANJA)]:
        linea(fig, comp["fecha"], 100 + comp[f"acum_{col}"], nom, color)
    return fig


def fig_interanual():
    fig = figura(titulo_y="Inflación interanual (%)")
    for col, nom, color in [("general", "IPC general", GRIS), ("salud", "IPC Salud", AZUL),
                            ("salud_ampliada", "Salud + seguro de salud", NARANJA)]:
        linea(fig, comp["fecha"], comp[f"interanual_{col}"], nom, color)
    return fig


def fig_brecha():
    b = comp["brecha_interanual_salud_general"]
    fig = figura(titulo_y="Puntos porcentuales", leyenda=False)
    fig.add_trace(go.Bar(x=comp["fecha"], y=b, marker_color=[AZUL if v >= 0 else ROJO for v in b],
                         marker_line=dict(color="white", width=1),
                         hovertemplate="%{y:+.2f} pp"))
    fig.update_layout(bargap=0.15)
    return fig


tab_resumen = html.Div([
    kpis,
    html.Div(className="grid-2", children=[
        tarjeta("Nivel del índice", "Los dos índices reescalados a 100 en dic 2020 para compararlos.",
                dcc.Graph(figure=fig_indice(), config=CONFIG)),
        tarjeta("Inflación interanual", "Variación contra el mismo mes del año anterior. La serie con seguro de salud empieza en oct 2021 (el seguro se publica desde oct 2020).",
                dcc.Graph(figure=fig_interanual(), config=CONFIG)),
    ]),
    tarjeta("Brecha de inflación: salud menos general",
            "Azul: salud subió más que el general. Rojo: subió menos. (Inflación interanual.)",
            dcc.Graph(figure=fig_brecha(), config=CONFIG)),
])

# ===================================================================== TAB 2
NIVELES = [("grupo", "Grupo"), ("subgrupo", "Subgrupo"), ("clase", "Clase"),
           ("subclase", "Subclase"), ("articulo", "Artículo")]
AMBITOS = [("salud", "Solo el grupo Salud"),
           ("ampliada", "Salud + seguro de salud"),
           ("todo", "Todos los grupos")]
METRICAS = {"var_interanual": "Inflación interanual (%)",
            "var_mensual": "Inflación mensual (%)",
            "var_acum_dic2020": "Variación acumulada desde dic 2020 (%)"}
SEGURO = {"1253", "12531", "1253101"}  # clase, subclase, artículo del seguro de salud


def nodos_del_ambito(nivel: str, ambito: str) -> pd.DataFrame:
    df = cat[cat["nivel"] == nivel]
    if ambito == "salud":
        return df[df["grupo"] == "06"]
    if ambito == "ampliada":
        return df[(df["grupo"] == "06") | df["codigo"].isin(SEGURO)]
    return df


def etiqueta_nodo(cod: str) -> str:
    n = NOMBRE[cod]
    return f"{cod} · {n if len(n) <= 42 else n[:41] + '…'}"


controles_jerarquia = html.Div(className="controls", children=[
    html.Div([html.Label("Nivel"), dcc.Dropdown(
        id="j-nivel", clearable=False, value="subclase",
        options=[{"label": l, "value": v} for v, l in NIVELES])]),
    html.Div([html.Label("Qué nodos mostrar"), dcc.Dropdown(
        id="j-ambito", clearable=False, value="ampliada",
        options=[{"label": l, "value": v} for v, l in AMBITOS])]),
    html.Div([html.Label("Medida"), dcc.Dropdown(
        id="j-metrica", clearable=False, value="var_interanual",
        options=[{"label": l, "value": v} for v, l in METRICAS.items()])]),
    html.Div([html.Label("Mes"), dcc.Dropdown(
        id="j-mes", clearable=False, value=FECHA_FIN.strftime("%Y-%m-%d"),
        options=opciones_meses(pd.Timestamp("2021-01-01")))]),
])

tab_jerarquia = html.Div([
    html.P("Elige un nivel de la canasta (grupo, subgrupo, clase, subclase o artículo). "
           "Nota: el BCRD publica los artículos desde oct 2020, así que la inflación interanual "
           "por subgrupo, clase, subclase o artículo existe desde oct 2021; antes de eso usa la "
           "variación acumulada.", className="nota"),
    controles_jerarquia,
    tarjeta("Ranking en el mes elegido", "La línea punteada es el IPC general en ese mismo mes.",
            grafico("j-barras")),
    tarjeta("Evolución en el tiempo", "Elige hasta 6 nodos. Cada uno conserva su color.",
            html.Div([
                dcc.Dropdown(id="j-nodos", multi=True, placeholder="Elige nodos…"),
                dcc.Checklist(id="j-general", value=["si"], className="check",
                              options=[{"label": " Incluir IPC general", "value": "si"}]),
                dcc.Store(id="j-colores", data={}),
                grafico("j-series"),
            ])),
    tarjeta("Composición de Salud por ponderación",
            "Tamaño = peso en la canasta. Color = variación acumulada dic 2020 → mes elegido (más oscuro = subió más).",
            grafico("j-treemap")),
    tarjeta("Tabla del ranking", "Los mismos datos del gráfico, con la ponderación de cada nodo.",
            dash_table.DataTable(id="j-tabla", page_size=12, sort_action="native",
                                 style_header={"fontWeight": "600", "backgroundColor": "#f4f3f0"},
                                 style_cell={"fontFamily": "inherit", "padding": "6px 10px",
                                             "textAlign": "left", "fontSize": 13},
                                 style_data_conditional=[{"if": {"row_index": "odd"},
                                                          "backgroundColor": "#fafaf8"}])),
])


def fecha_ts(texto: str) -> pd.Timestamp:
    return pd.Timestamp(texto)


def registrar_callbacks_jerarquia(app):
    @app.callback(Output("j-nodos", "options"), Output("j-nodos", "value"),
                  Input("j-nivel", "value"), Input("j-ambito", "value"))
    def opciones_nodos(nivel, ambito):
        df = nodos_del_ambito(nivel, ambito).sort_values("ponderacion", ascending=False)
        opciones = [{"label": etiqueta_nodo(c), "value": c} for c in df["codigo"]]
        return opciones, list(df["codigo"].head(3))

    @app.callback(Output("j-barras", "figure"), Output("j-tabla", "data"),
                  Output("j-tabla", "columns"),
                  Input("j-nivel", "value"), Input("j-ambito", "value"),
                  Input("j-metrica", "value"), Input("j-mes", "value"))
    def ranking(nivel, ambito, metrica, mes):
        f = fecha_ts(mes)
        nodos = nodos_del_ambito(nivel, ambito)
        d = inf[(inf["fecha"] == f) & inf["codigo"].isin(nodos["codigo"])].dropna(subset=[metrica])
        # con cientos de artículos, mostrar solo los 40 de mayor peso
        recorte = len(d) > 40
        if recorte:
            d = d.nlargest(40, "ponderacion")
        d = d.sort_values(metrica)
        es_salud = d["grupo"].eq("06") | d["codigo"].isin(SEGURO)
        colores = [AZUL if s else GRIS_CLARO for s in es_salud] if ambito == "todo" else [AZUL] * len(d)
        etiquetas = [etiqueta_nodo(c) for c in d["codigo"]]

        fig = figura(alto=max(300, 26 * len(d) + 90), leyenda=False)
        fig.update_layout(hovermode="closest", margin=dict(l=300, r=24, t=28, b=40),
                          xaxis=dict(title=METRICAS[metrica], gridcolor=REJILLA, zeroline=True,
                                     zerolinecolor=GRIS_CLARO, tickformat=None, hoverformat=None),
                          yaxis=dict(automargin=True, gridcolor="white"))
        fig.add_trace(go.Bar(x=d[metrica], y=etiquetas, orientation="h", marker_color=colores,
                             marker_line=dict(color="white", width=1),
                             customdata=d[["ponderacion"]],
                             hovertemplate="<b>%{y}</b><br>%{x:.2f}%<br>peso base %{customdata[0]:.3f}%<extra></extra>"))
        gen = inf[(inf["fecha"] == f) & (inf["codigo"] == "00")][metrica].iloc[0]
        if pd.notna(gen):
            fig.add_vline(x=gen, line=dict(color=TINTA, width=1.5, dash="dot"),
                          annotation_text=f"IPC general {gen:.2f}%", annotation_position="top")
        if recorte:
            fig.add_annotation(text="Se muestran los 40 nodos de mayor peso", xref="paper", yref="paper",
                               x=1, y=-0.12, showarrow=False, font=dict(size=11, color=GRIS))

        t = d.sort_values(metrica, ascending=False)
        tabla = pd.DataFrame({"Código": t["codigo"], "Nodo": t["nombre"],
                              "Peso base (%)": t["ponderacion"].round(3),
                              METRICAS[metrica]: t[metrica].round(2)})
        columnas = [{"name": c, "id": c} for c in tabla.columns]
        return fig, tabla.to_dict("records"), columnas

    @app.callback(Output("j-series", "figure"), Output("j-colores", "data"),
                  Input("j-nodos", "value"), Input("j-metrica", "value"),
                  Input("j-general", "value"), State("j-colores", "data"))
    def series(nodos, metrica, general, colores_previos):
        nodos = (nodos or [])[:len(SERIES)]
        # cada nodo conserva su color: los que siguen elegidos mantienen su casilla
        colores = {k: v for k, v in (colores_previos or {}).items() if k in nodos}
        libres = [i for i in range(len(SERIES)) if i not in colores.values()]
        for n in nodos:
            if n not in colores:
                colores[n] = libres.pop(0)
        fig = figura(titulo_y=METRICAS[metrica])
        if general:
            g = inf[inf["codigo"] == "00"]
            linea(fig, g["fecha"], g[metrica], "IPC general", TINTA_2, dash="dot", ancho=2)
        for n in nodos:
            d = inf[inf["codigo"] == n]
            linea(fig, d["fecha"], d[metrica], etiqueta_nodo(n), SERIES[colores[n]])
        return fig, colores

    @app.callback(Output("j-treemap", "figure"), Input("j-mes", "value"))
    def treemap(mes):
        f = fecha_ts(mes)
        n = cat[cat["grupo"] == "06"].merge(
            inf[inf["fecha"] == f][["codigo", "var_acum_dic2020"]], on="codigo")
        hoja = n["nivel"] == "articulo"
        fig = go.Figure(go.Treemap(
            ids=n["codigo"], labels=n["nombre"], parents=n["padre"].fillna("").where(n["nivel"] != "grupo", ""),
            values=n["ponderacion"].where(hoja, 0), branchvalues="remainder",
            marker=dict(colors=n["var_acum_dic2020"], colorscale=SECUENCIAL, cmin=0,
                        cmax=float(n["var_acum_dic2020"].max()),
                        colorbar=dict(title="Acum. %", thickness=12), line=dict(color="white", width=1)),
            customdata=n[["ponderacion", "var_acum_dic2020"]],
            hovertemplate="<b>%{label}</b><br>peso base %{customdata[0]:.3f}%<br>"
                          "acumulada %{customdata[1]:.1f}%<extra></extra>",
            textfont=dict(size=13), pathbar=dict(visible=True)))
        fig.update_layout(height=520, margin=dict(l=8, r=8, t=8, b=8),
                          font=dict(family="Calibri, Carlito, Helvetica, Arial, sans-serif"))
        return fig


# ===================================================================== TAB 3
def fig_peso_efectivo():
    s = pef[pef["codigo"] == "06"].set_index("fecha")["peso_efectivo"]
    g = pef[pef["codigo"] == SEGURO_ART].set_index("fecha")["peso_efectivo"]
    base_s = cat.loc[cat["codigo"] == "06", "ponderacion"].iloc[0]
    base_g = cat.loc[cat["codigo"] == SEGURO_ART, "ponderacion"].iloc[0]
    fig = figura(titulo_y="% de la canasta")
    linea(fig, s.index, s, "Salud (peso efectivo)", AZUL)
    linea(fig, s.index, [base_s] * len(s), "Salud (peso base)", AZUL, dash="dot", ancho=1.5)
    linea(fig, s.index, s + g, "Salud + seguro (peso efectivo)", NARANJA)
    linea(fig, s.index, [base_s + base_g] * len(s), "Salud + seguro (peso base)", NARANJA, dash="dot", ancho=1.5)
    return fig


SEGURO_ART = "1253101"


def fig_incidencia_tiempo():
    gr = inc[inc["nivel"] == "grupo"].dropna(subset=["incidencia_interanual"])
    total = gr.groupby("fecha")["incidencia_interanual"].sum()
    salud = gr[gr["codigo"] == "06"].set_index("fecha")["incidencia_interanual"]
    seg = inc[inc["codigo"] == SEGURO_ART].set_index("fecha")["incidencia_interanual"].reindex(total.index)
    resto = total - salud.reindex(total.index) - seg
    fig = figura(titulo_y="Puntos porcentuales")
    fig.update_layout(barmode="relative", bargap=0.15)
    for nom, y, color in [("Salud", salud.reindex(total.index), AZUL),
                          ("Seguro de salud", seg, NARANJA),
                          ("Resto de la canasta", resto, GRIS_CLARO)]:
        fig.add_trace(go.Bar(x=total.index, y=y, name=nom, marker_color=color,
                             marker_line=dict(color="white", width=1), hovertemplate="%{y:.2f} pp"))
    linea(fig, total.index, total, "Inflación general interanual", TINTA, ancho=2)
    return fig


tab_peso = html.Div([
    html.P("El peso base es la ponderación fija de la canasta (año 2019-2020). El peso efectivo "
           "es lo que realmente pesa cada mes: si algo sube más que el promedio, pesa más. "
           "La incidencia es cuántos puntos de la inflación general aporta cada componente.",
           className="nota"),
    html.Div(className="grid-2", children=[
        tarjeta("Peso de salud en la canasta", "Línea punteada: peso base. Línea continua: peso efectivo.",
                dcc.Graph(figure=fig_peso_efectivo(), config=CONFIG)),
        tarjeta("Cuánto aporta salud a la inflación general",
                "Inflación interanual de la canasta descompuesta (desde oct 2021, primer mes con datos de 12 meses atrás).",
                dcc.Graph(figure=fig_incidencia_tiempo(), config=CONFIG)),
    ]),
    tarjeta("Incidencia por grupo en un mes", "Aporte de cada grupo a la inflación interanual general. Salud en azul.",
            html.Div([
                html.Div(className="controls one", children=[html.Div([
                    html.Label("Mes"), dcc.Dropdown(
                        id="p-mes", clearable=False, value=FECHA_FIN.strftime("%Y-%m-%d"),
                        options=opciones_meses(pd.Timestamp("2021-10-01")))])]),
                grafico("p-grupos")])),
])


def registrar_callbacks_peso(app):
    @app.callback(Output("p-grupos", "figure"), Input("p-mes", "value"))
    def incidencia_grupos(mes):
        d = inc[(inc["fecha"] == fecha_ts(mes)) & (inc["nivel"] == "grupo")].sort_values("incidencia_interanual")
        fig = figura(alto=420, leyenda=False)
        fig.update_layout(hovermode="closest", margin=dict(l=260, r=24, t=16, b=40),
                          xaxis=dict(title="Puntos porcentuales", gridcolor=REJILLA, tickformat=None, hoverformat=None),
                          yaxis=dict(automargin=True, gridcolor="white"))
        fig.add_trace(go.Bar(
            x=d["incidencia_interanual"], y=d["nombre"], orientation="h",
            marker_color=[AZUL if c == "06" else GRIS_CLARO for c in d["codigo"]],
            marker_line=dict(color="white", width=1),
            hovertemplate="<b>%{y}</b><br>%{x:.2f} pp<extra></extra>"))
        return fig


# ===================================================================== TAB 4
def fig_subyacente_tiempo():
    fig = figura(titulo_y="Inflación interanual (%)")
    linea(fig, sub_t["fecha"], sub_t["interanual_general"], "IPC general", GRIS)
    linea(fig, sub_t["fecha"], sub_t["interanual_subyacente"], "IPC subyacente", NARANJA)
    linea(fig, comp["fecha"], comp["interanual_salud"], "IPC Salud (100% subyacente)", AZUL)
    return fig


def fig_subyacente_peso():
    d = sub_p[sub_p["nivel"] == "grupo"].sort_values("pct_subyacente")
    fig = figura(alto=420, leyenda=False)
    fig.update_layout(hovermode="closest", margin=dict(l=260, r=24, t=16, b=40),
                      xaxis=dict(title="% subyacente del peso del grupo", range=[0, 105],
                                 gridcolor=REJILLA, tickformat=None, hoverformat=None),
                      yaxis=dict(automargin=True, gridcolor="white"))
    fig.add_trace(go.Bar(x=d["pct_subyacente"], y=d["nombre"], orientation="h",
                         marker_color=[AZUL if c == "06" else GRIS_CLARO for c in d["codigo"]],
                         marker_line=dict(color="white", width=1),
                         hovertemplate="<b>%{y}</b><br>%{x:.1f}% subyacente<extra></extra>"))
    return fig


tab_subyacencia = html.Div([
    html.P("La inflación subyacente excluye los productos más volátiles (por ejemplo, ciertos "
           "alimentos, bebidas alcohólicas y combustibles). Todos los artículos de Salud son "
           "subyacentes, así que su inflación no viene de los productos más volátiles.", className="nota"),
    html.Div(className="grid-2", children=[
        tarjeta("General vs subyacente vs salud", "Inflación interanual.",
                dcc.Graph(figure=fig_subyacente_tiempo(), config=CONFIG)),
        tarjeta("Subyacencia por grupo", "Qué parte del peso de cada grupo es subyacente.",
                dcc.Graph(figure=fig_subyacente_peso(), config=CONFIG)),
    ]),
])

# ===================================================================== TAB 5
ESQUEMAS = [("IPC general", GRIS), ("IPC salud", AZUL), ("IPC salud ampliada", NARANJA),
            ("Servicios médicos", AQUA), ("Productos farmacéuticos", "#eda100"),
            ("Servicios de hospital", "#4a3aa7")]
COLOR_ESQUEMA = dict(ESQUEMAS)
PC_BASE = sim.loc[sim["fecha"] == sim["fecha"].min(), "per_capita"].iloc[0]
PC_FECHA = sim["fecha"].min()

tab_percapita = html.Div([
    html.Div(className="aviso", children=[
        html.Strong("Supuesto de la simulación: "),
        f"se parte del per cápita de RD${PC_BASE:,.2f} en {etiqueta_mes(PC_FECHA)} y se indexa con cada índice. "
        "Falta confirmar desde qué mes rige ese monto (se asume dic 2020, ver CLAUDE.md)."]),
    html.Div(className="controls one", children=[html.Div([
        html.Label("Índices con los que indexar"),
        dcc.Checklist(id="c-esquemas", className="check",
                      value=["IPC general", "IPC salud", "IPC salud ampliada", "Servicios médicos"],
                      options=[{"label": " " + n, "value": n} for n, _ in ESQUEMAS],
                      inline=True)])]),
    tarjeta("¿Cuánto valdría el per cápita (RD$)?",
            "Cada línea indexa el per cápita base con un índice distinto. Los rombos son los montos aprobados por el CNSS.",
            grafico("c-grafico")),
    tarjeta("Aprobado vs simulado en las fechas conocidas",
            "Diferencia = monto aprobado menos simulado. Positivo: lo aprobado quedó por encima de ese índice.",
            dash_table.DataTable(id="c-tabla", style_header={"fontWeight": "600", "backgroundColor": "#f4f3f0"},
                                 style_cell={"fontFamily": "inherit", "padding": "6px 10px",
                                             "textAlign": "right", "fontSize": 13})),
])


def registrar_callbacks_percapita(app):
    @app.callback(Output("c-grafico", "figure"), Output("c-tabla", "data"), Output("c-tabla", "columns"),
                  Input("c-esquemas", "value"))
    def percapita(esquemas):
        esquemas = [e for e, _ in ESQUEMAS if e in (esquemas or [])]
        fig = figura(titulo_y="RD$ por afiliado al mes")
        for e in esquemas:
            d = sim[sim["esquema"] == e]
            linea(fig, d["fecha"], d["per_capita"], e, COLOR_ESQUEMA[e])
        ap = sim.dropna(subset=["per_capita_aprobado"]).drop_duplicates("fecha")
        fig.add_trace(go.Scatter(x=ap["fecha"], y=ap["per_capita_aprobado"], name="Aprobado CNSS",
                                 mode="markers", marker=dict(symbol="diamond", size=11, color=TINTA,
                                                             line=dict(color="white", width=2)),
                                 hovertemplate="%{y:,.2f}"))
        fig.update_yaxes(tickformat=",.0f")

        ancho = sim.pivot(index="fecha", columns="esquema", values="per_capita")
        filas = []
        for _, r in ap.iterrows():
            fila = {"Fecha": etiqueta_mes(r["fecha"]), "Aprobado": f"{r['per_capita_aprobado']:,.2f}"}
            for e in esquemas:
                v = ancho.loc[r["fecha"], e]
                fila[e] = f"{v:,.2f}  ({r['per_capita_aprobado'] - v:+,.2f})"
            filas.append(fila)
        columnas = [{"name": c, "id": c} for c in ["Fecha", "Aprobado", *esquemas]]
        return fig, filas, columnas


# ===================================================================== TAB 6
tab_metodologia = html.Div(className="card texto", children=[
    html.H3("Metodología y fuentes"),
    html.H4("De dónde salen los datos"),
    html.P("Banco Central de la República Dominicana (BCRD), sección Estadísticas → Precios → "
           "«IPC base anual: octubre 2019 – septiembre 2020 = 100». Los archivos originales se "
           "convierten a tablas ordenadas en formato parquet (src/01_limpieza.py)."),
    html.H4("Cómo se calcula"),
    html.Ul([
        html.Li("Inflación mensual = índice del mes ÷ índice del mes anterior − 1."),
        html.Li("Inflación interanual = índice del mes ÷ índice del mismo mes del año anterior − 1."),
        html.Li("Variación acumulada = índice del mes ÷ índice de dic 2020 − 1."),
        html.Li("Peso efectivo = peso base × índice del nodo ÷ índice general."),
        html.Li("Incidencia = peso efectivo del mes anterior × inflación del nodo. Las incidencias "
                "de los 12 grupos suman la inflación general (diferencia máxima 0.0008 pp)."),
        html.Li("Salud + seguro de salud: el seguro de salud (artículo 1253101, peso 0.35%) está en el grupo "
                "12 (Bienes y Servicios Diversos), no en Salud; aquí se agrega para ver el costo de la salud completo."),
    ]),
    html.H4("Limitaciones"),
    html.Ul([
        html.Li("Los artículos se publican solo desde oct 2020: la inflación interanual por artículo, "
                "clase o subgrupo existe desde oct 2021."),
        html.Li("La serie oficial del IPC general está empalmada con la base 2010; la serie referencial "
                "con la canasta nueva difiere hasta 0.88 puntos antes de sep 2020."),
        html.Li("El análisis cubre ene 2021 – mar 2026, aunque el BCRD ya publica datos hasta ago 2026."),
    ]),
    html.H4("Per cápita del PDSS"),
    html.P("Régimen contributivo (CNSS/SISALRIL): RD$1,327.81 → 1,490.14 (2022) → 1,555.14 (feb 2023) → "
           "1,683.22 (nov 2023) → 1,887.54 indexado (aprobado oct 2025). El CNSS usa el IPC general "
           "para indexar (Res. 624-02 y anteriores); el IPC Salud queda solo como referencia."),
])

# ===================================================================== APP
app = Dash(__name__, title="IPC Salud y per cápita PDSS", suppress_callback_exceptions=True)
server = app.server

TABS = [("resumen", "Resumen", tab_resumen),
        ("jerarquia", "Jerarquía de la canasta", tab_jerarquia),
        ("peso", "Peso e incidencia", tab_peso),
        ("subyacencia", "Subyacencia", tab_subyacencia),
        ("percapita", "Per cápita PDSS", tab_percapita),
        ("metodologia", "Metodología", tab_metodologia)]

app.layout = html.Div(className="page", children=[
    html.Header(children=[
        html.H1("IPC de Salud y per cápita del PDSS"),
        html.P("Evolución del rubro salud en el IPC del BCRD, enero 2021 – marzo 2026, "
               "e implicaciones para indexar el per cápita base (régimen contributivo, SFS).")]),
    dcc.Tabs(id="tabs", value="resumen", className="tabs",
             children=[dcc.Tab(label=l, value=v, className="tab", selected_className="tab--sel",
                               children=html.Div(c, className="tab-body")) for v, l, c in TABS]),
])

registrar_callbacks_jerarquia(app)
registrar_callbacks_peso(app)
registrar_callbacks_percapita(app)

if __name__ == "__main__":
    app.run(debug=False, port=8050)
