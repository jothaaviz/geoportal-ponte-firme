import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import json
import folium
from folium import plugins
from streamlit_folium import folium_static
import plotly.express as px
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Geoportal Projeto Ponte Firme",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');

    html, body, [data-testid="stSidebar"] {
        font-family: 'Outfit', sans-serif;
    }

    .main-title {
        font-weight: 700;
        color: #31333F;
        margin-bottom: 0px;
        font-size: 2.4rem;
    }

    .subtitle {
        color: #4f5665;
        font-size: 1.05rem;
        margin-bottom: 25px;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #f8f9fa;
        border-radius: 8px 8px 0px 0px;
        padding-left: 15px;
        padding-right: 15px;
        font-weight: 600;
        border: 1px solid rgba(0,0,0,0.1);
        border-bottom: none;
    }

    .stTabs [aria-selected="true"] {
        background-color: white !important;
        border-top: 3px solid #ff4b4b !important;
        color: #ff4b4b !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# CAMINHO DOS DADOS
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
PASTA_DADOS = BASE_DIR / "dados" / "pontes"

# =========================================================
# FUNÇÕES
# =========================================================
@st.cache_data
def localizar_arquivo_dados(pasta: Path):
    """Localiza automaticamente o primeiro arquivo geográfico dentro da pasta dados/pontes."""
    if not pasta.exists():
        return None

    for extensao in ["*.geojson", "*.json", "*.shp", "*.gpkg"]:
        arquivos = list(pasta.glob(extensao))
        if arquivos:
            return arquivos[0]

    return None


@st.cache_data(show_spinner="Carregando dados geoespaciais...")
def carregar_dados(caminho_dados: str):
    """Carrega o arquivo geográfico e prepara coordenadas auxiliares."""
    try:
        gdf = gpd.read_file(caminho_dados)

        if gdf.empty:
            return gdf

        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)

        gdf = gdf.to_crs(epsg=4326)

        # Corrigir geometrias inválidas sem destruir a geometria original
        try:
            gdf["geometry"] = gdf.geometry.make_valid()
        except Exception:
            pass

        # Coordenadas auxiliares apenas para centralização/diagnóstico.
        # A renderização do mapa usa a geometria real do arquivo.
        centroides = gdf.geometry.centroid
        gdf["_lon"] = centroides.x
        gdf["_lat"] = centroides.y

        return gdf

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo geográfico: {e}")
        return None


def autodetectar_coluna(colunas, palavras_chave):
    """Tenta identificar automaticamente colunas importantes."""
    colunas_lista = list(colunas)

    for col in colunas_lista:
        col_lower = str(col).lower().strip()
        for kw in palavras_chave:
            if col_lower == kw:
                return col

    for col in colunas_lista:
        col_lower = str(col).lower().strip()
        for kw in palavras_chave:
            if kw in col_lower:
                return col

    return None


def normalizar_texto(valor):
    if pd.isna(valor) or valor is None or str(valor).strip() == "":
        return "Não Informado"
    return str(valor).strip()


def padronizar_municipio(valor):
    txt = normalizar_texto(valor)

    mapa = {
        "LARANJÃO DO JARI": "LARANJAL DO JARI",
        "Laranjão do Jari": "LARANJAL DO JARI",
        "laranjão do jari": "LARANJAL DO JARI",
        "Laranjal do Jari": "LARANJAL DO JARI",
        "laranjal do jari": "LARANJAL DO JARI",
        "MACAPA": "Macapá",
        "MACAPÁ": "Macapá",
        "Macapa": "Macapá",
        "SANTANA": "SANTANA",
    }

    return mapa.get(txt, txt)


def valor_json_seguro(valor):
    """Converte valores para formatos compatíveis com JSON."""
    if valor is None:
        return None

    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass

    if isinstance(valor, (np.integer,)):
        return int(valor)

    if isinstance(valor, (np.floating,)):
        return float(valor)

    if isinstance(valor, pd.Timestamp):
        return valor.isoformat()

    if isinstance(valor, (str, int, float, bool)):
        return valor

    return str(valor)


def preparar_geojson_seguro(gdf: gpd.GeoDataFrame) -> dict:
    """Prepara GeoDataFrame para GeoJSON sem quebrar por tipos não serializáveis."""
    gdf_saida = gdf.copy()

    for col in gdf_saida.columns:
        if col == gdf_saida.geometry.name:
            continue
        gdf_saida[col] = gdf_saida[col].map(valor_json_seguro)

    return json.loads(gdf_saida.to_json())


def gerar_legenda_html(color_map, titulo):
    itens = []

    for valor, cor in color_map.items():
        texto = str(valor) if valor is not None else "Não Informado"
        itens.append(
            f"""
            <div style="display:flex;align-items:center;margin-bottom:8px;">
                <div style="
                    width:16px;
                    height:16px;
                    background-color:{cor};
                    border-radius:4px;
                    margin-right:10px;
                    border:1px solid rgba(0,0,0,0.25);
                "></div>
                <span style="font-size:0.9rem;font-weight:500;">{texto}</span>
            </div>
            """
        )

    return f"""
    <div style="
        background-color:#f8f9fa;
        padding:15px;
        border-radius:10px;
        border:1px solid rgba(0,0,0,0.1);
        margin-top:15px;
    ">
        <div style="
            font-size:0.8rem;
            font-weight:700;
            text-transform:uppercase;
            opacity:0.75;
            margin-bottom:10px;
            letter-spacing:0.5px;
        ">
            Legenda: {titulo}
        </div>
        {''.join(itens)}
    </div>
    """


def card_metric(titulo, valor, subtitulo, cor, icone):
    return f"""
    <div style="
        background-color:#f8f9fa;
        padding:20px;
        border-radius:12px;
        border:1px solid rgba(0,0,0,0.1);
        border-left:6px solid {cor};
        display:flex;
        align-items:center;
        min-height:110px;
    ">
        <div style="font-size:2.2rem;margin-right:15px;">{icone}</div>
        <div>
            <div style="
                font-size:0.8rem;
                color:#6c757d;
                font-weight:700;
                text-transform:uppercase;
                letter-spacing:0.5px;
            ">{titulo}</div>
            <div style="
                font-size:1.8rem;
                color:#31333F;
                font-weight:700;
                line-height:1.2;
                margin:4px 0;
            ">{valor}</div>
            <div style="font-size:0.8rem;color:#888;">{subtitulo}</div>
        </div>
    </div>
    """


def estilo_geometria_real(feature):
    """Estilo aplicado à geometria real da ponte."""
    props = feature.get("properties", {})
    cor = props.get("_cor_mapa", "#ff0000")
    opacidade = props.get("_opacidade_mapa", 0.9)

    return {
        "color": cor,
        "weight": 7,
        "opacity": float(opacidade) if opacidade is not None else 0.9,
        "fillColor": cor,
        "fillOpacity": 0.35,
    }


def destaque_geometria_real(feature):
    return {
        "color": "#ffff00",
        "weight": 10,
        "opacity": 1,
        "fillOpacity": 0.55,
    }


def criar_mapa_geometria_real(gdf_mapa, campo_cor, color_map, opacidade, campos_popup):
    """Cria mapa Folium preservando a geometria real do arquivo: linhas, polígonos ou pontos."""
    gdf_mapa = gdf_mapa.copy()

    if gdf_mapa.crs is None:
        gdf_mapa = gdf_mapa.set_crs(epsg=4326)

    gdf_mapa = gdf_mapa.to_crs(epsg=4326)

    gdf_mapa["_cor_mapa"] = gdf_mapa[campo_cor].apply(
        lambda v: color_map.get(v, color_map.get(None, "#808080"))
    )
    gdf_mapa["_opacidade_mapa"] = float(opacidade)

    minx, miny, maxx, maxy = gdf_mapa.total_bounds

    if not np.isfinite([minx, miny, maxx, maxy]).all():
        raise ValueError("Coordenadas inválidas no arquivo geográfico.")

    # Evita erro quando a seleção tem apenas um ponto/linha muito pequena
    if minx == maxx and miny == maxy:
        minx -= 0.01
        maxx += 0.01
        miny -= 0.01
        maxy += 0.01

    center_lat = (miny + maxy) / 2
    center_lon = (minx + maxx) / 2

    mapa = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=True,
    )

    # Basemaps
    folium.TileLayer(
        "OpenStreetMap",
        name="OpenStreetMap",
        overlay=False,
        control=True,
    ).add_to(mapa)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Satélite Esri",
        overlay=False,
        control=True,
        show=False,
    ).add_to(mapa)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr="&copy; OpenStreetMap &copy; CARTO",
        name="Mapa Claro",
        overlay=False,
        control=True,
        show=False,
    ).add_to(mapa)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="&copy; OpenStreetMap &copy; CARTO",
        name="Mapa Escuro",
        overlay=False,
        control=True,
        show=False,
    ).add_to(mapa)

    # GeoJSON preservando a geometria real
    geojson_data = preparar_geojson_seguro(
        gdf_mapa.drop(columns=["_lat", "_lon", "_centroide"], errors="ignore")
    )

    campos_disponiveis = [c for c in campos_popup if c in gdf_mapa.columns]

    camada_pontes = folium.GeoJson(
        data=geojson_data,
        name="Pontes - geometria real",
        style_function=estilo_geometria_real,
        highlight_function=destaque_geometria_real,
        tooltip=folium.GeoJsonTooltip(
            fields=campos_disponiveis,
            aliases=[f"{c}:" for c in campos_disponiveis],
            localize=True,
            sticky=True,
            labels=True,
            style="""
                background-color:white;
                color:#333;
                font-family:Arial;
                font-size:12px;
                padding:10px;
                border-radius:5px;
            """,
        ),
        popup=folium.GeoJsonPopup(
            fields=campos_disponiveis,
            aliases=[f"{c}:" for c in campos_disponiveis],
            localize=True,
            labels=True,
            max_width=350,
        ),
        marker=folium.CircleMarker(
            radius=7,
            weight=2,
            color="#222222",
            fill=True,
            fill_opacity=0.9,
        ),
    )

    camada_pontes.add_to(mapa)

    # Enquadramento geral
    mapa.fit_bounds(
        [[miny, minx], [maxy, maxx]],
        padding=(40, 40),
        max_zoom=17,
    )

    plugins.Fullscreen(
        position="topleft",
        title="Expandir mapa",
        title_cancel="Sair da tela cheia",
        force_separate_button=True,
    ).add_to(mapa)

    folium.LayerControl(position="topright", collapsed=True).add_to(mapa)

    return mapa


# =========================================================
# CABEÇALHO
# =========================================================
st.markdown(
    '<h1 class="main-title">🗺️ Geoportal WebGIS - Projeto Ponte Firme</h1>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="subtitle">Plataforma interativa para monitoramento, análise e gestão das pontes municipais</p>',
    unsafe_allow_html=True,
)

# =========================================================
# CARREGAMENTO DOS DADOS
# =========================================================
if not PASTA_DADOS.exists():
    st.error("❌ A pasta `dados/pontes` não foi encontrada.")
    st.info("Crie a pasta `dados/pontes` e coloque nela seu arquivo `.geojson`, `.shp` ou `.gpkg`.")
    st.stop()

caminho_dados = localizar_arquivo_dados(PASTA_DADOS)

if caminho_dados is None:
    st.error("❌ Nenhum arquivo geográfico foi encontrado em `dados/pontes`.")
    st.stop()

gdf = carregar_dados(str(caminho_dados))

if gdf is None or gdf.empty:
    st.error("❌ O arquivo foi carregado, mas está vazio ou com erro.")
    st.stop()

# =========================================================
# DETECÇÃO DE COLUNAS
# =========================================================
colunas_todas = [c for c in gdf.columns if c not in ["geometry", "_lat", "_lon", "_centroide"]]

if not colunas_todas:
    st.error("O arquivo não possui colunas de atributos além da geometria.")
    st.stop()

col_nome_detect = autodetectar_coluna(colunas_todas, ["nome", "ponte", "name", "obra", "estrutura", "id", "codigo", "código"])
col_mun_detect = autodetectar_coluna(colunas_todas, ["município", "municipio", "municipío", "nm_mun", "cidade", "mun"])
col_sit_detect = autodetectar_coluna(colunas_todas, ["status", "situacao", "situação", "fase", "estado", "condicao", "condição"])
col_ext_detect = autodetectar_coluna(colunas_todas, ["tamannho", "tamanho", "extensao", "extensão", "comprimento", "length", "metros"])
col_exec_detect = autodetectar_coluna(colunas_todas, ["executado", "exec", "concluido", "concluído"])
col_falta_detect = autodetectar_coluna(colunas_todas, ["faltaexe", "falta_exe", "restante", "a_executar", "falta"])
col_bairro_detect = autodetectar_coluna(colunas_todas, ["bairro", "distrito", "localidade", "setor"])

# Fallbacks para evitar quebra
col_nome_detect = col_nome_detect or colunas_todas[0]
col_mun_detect = col_mun_detect or colunas_todas[0]
col_sit_detect = col_sit_detect or colunas_todas[0]
col_ext_detect = col_ext_detect or colunas_todas[0]
col_exec_detect = col_exec_detect or col_ext_detect
col_falta_detect = col_falta_detect or col_ext_detect
col_bairro_detect = col_bairro_detect or colunas_todas[0]

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.image("https://img.icons8.com/color/96/000000/bridge.png", width=90)
st.sidebar.title("Configurações do Geoportal")

with st.sidebar.expander("🛠️ Mapeamento de Colunas", expanded=False):
    st.caption("Ajuste os campos caso a detecção automática não esteja correta.")

    col_nome = st.selectbox(
        "Identificação da Ponte",
        colunas_todas,
        index=colunas_todas.index(col_nome_detect),
    )

    col_municipio = st.selectbox(
        "Município",
        colunas_todas,
        index=colunas_todas.index(col_mun_detect),
    )

    col_situacao = st.selectbox(
        "Situação/Status",
        colunas_todas,
        index=colunas_todas.index(col_sit_detect),
    )

    col_extensao = st.selectbox(
        "Extensão Total",
        colunas_todas,
        index=colunas_todas.index(col_ext_detect),
    )

    col_executado = st.selectbox(
        "Extensão Executada",
        colunas_todas,
        index=colunas_todas.index(col_exec_detect),
    )

    col_faltaexe = st.selectbox(
        "Restante a Executar",
        colunas_todas,
        index=colunas_todas.index(col_falta_detect),
    )

    col_bairro = st.selectbox(
        "Bairro",
        colunas_todas,
        index=colunas_todas.index(col_bairro_detect),
    )

# Conversões numéricas
gdf[col_extensao] = pd.to_numeric(gdf[col_extensao], errors="coerce").fillna(0.0)
gdf[col_executado] = pd.to_numeric(gdf[col_executado], errors="coerce").fillna(0.0)
gdf[col_faltaexe] = pd.to_numeric(gdf[col_faltaexe], errors="coerce").fillna(0.0)

# Padronização textual
for col_txt in [col_nome, col_municipio, col_situacao, col_bairro]:
    gdf[col_txt] = gdf[col_txt].apply(normalizar_texto)

gdf[col_municipio] = gdf[col_municipio].apply(padronizar_municipio)

# =========================================================
# FILTROS
# =========================================================
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Filtros de Busca")

busca_nome = st.sidebar.text_input("Buscar ponte por nome/código", placeholder="Digite o nome...")

valores_municipio = sorted(gdf[col_municipio].dropna().unique().tolist())
municipios_selecionados = st.sidebar.multiselect(
    "Filtrar por Município",
    options=valores_municipio,
    default=valores_municipio,
)

valores_bairro = sorted(gdf[col_bairro].dropna().unique().tolist())
bairros_selecionados = st.sidebar.multiselect(
    "Filtrar por Bairro",
    options=valores_bairro,
    default=valores_bairro,
)

valores_situacao = sorted(gdf[col_situacao].dropna().unique().tolist())
situacoes_selecionadas = st.sidebar.multiselect(
    "Filtrar por Situação/Status",
    options=valores_situacao,
    default=valores_situacao,
)

min_ext = float(gdf[col_extensao].min())
max_ext = float(gdf[col_extensao].max())

if min_ext == max_ext:
    max_ext = min_ext + 1.0

extensao_selecionada = st.sidebar.slider(
    "Filtrar por Extensão (metros)",
    min_value=min_ext,
    max_value=max_ext,
    value=(min_ext, max_ext),
    step=1.0,
)

# Aplicar filtros
gdf_filtrado = gdf.copy()

if busca_nome:
    gdf_filtrado = gdf_filtrado[
        gdf_filtrado[col_nome].astype(str).str.contains(busca_nome, case=False, na=False)
    ]

if municipios_selecionados:
    gdf_filtrado = gdf_filtrado[gdf_filtrado[col_municipio].isin(municipios_selecionados)]
else:
    gdf_filtrado = gdf_filtrado.iloc[0:0]

if bairros_selecionados:
    gdf_filtrado = gdf_filtrado[gdf_filtrado[col_bairro].isin(bairros_selecionados)]
else:
    gdf_filtrado = gdf_filtrado.iloc[0:0]

if situacoes_selecionadas:
    gdf_filtrado = gdf_filtrado[gdf_filtrado[col_situacao].isin(situacoes_selecionadas)]
else:
    gdf_filtrado = gdf_filtrado.iloc[0:0]

gdf_filtrado = gdf_filtrado[
    (gdf_filtrado[col_extensao] >= extensao_selecionada[0])
    & (gdf_filtrado[col_extensao] <= extensao_selecionada[1])
]

# =========================================================
# SIMBOLOGIA
# =========================================================
st.sidebar.markdown("---")
st.sidebar.subheader("🎨 Estilo e Simbologia")

campo_cor = st.sidebar.selectbox(
    "Colorir mapa por",
    options=[col_situacao, col_municipio, col_bairro],
    index=0,
)

opacidade = st.sidebar.slider(
    "Opacidade da camada",
    min_value=0.1,
    max_value=1.0,
    value=0.9,
    step=0.1,
)

palette = px.colors.qualitative.Bold
valores_unicos = list(gdf_filtrado[campo_cor].dropna().unique())
color_map = {valor: palette[i % len(palette)] for i, valor in enumerate(valores_unicos)}
color_map[None] = "#808080"
color_map["Não Informado"] = color_map.get("Não Informado", "#808080")

st.sidebar.markdown(gerar_legenda_html(color_map, campo_cor), unsafe_allow_html=True)

# =========================================================
# ABAS
# =========================================================
tab_mapa, tab_stats, tab_dados, tab_sobre = st.tabs(
    [
        "🗺️ Geoportal WebGIS",
        "📊 Indicadores & Estatísticas",
        "📁 Tabela de Atributos",
        "ℹ️ Sobre o Projeto",
    ]
)

# =========================================================
# ABA 1: MAPA
# =========================================================
with tab_mapa:
    st.markdown("### Mapa de Distribuição Geográfica")
    st.caption(f"Pontes filtradas: {len(gdf_filtrado)}")

    if gdf_filtrado.empty:
        st.warning("Nenhuma ponte encontrada com os filtros selecionados.")
    else:
        campos_popup = [
            col_nome,
            col_municipio,
            col_bairro,
            col_situacao,
            col_extensao,
            col_executado,
            col_faltaexe,
        ]

        # Remove duplicatas preservando ordem
        campos_popup = list(dict.fromkeys([c for c in campos_popup if c in gdf_filtrado.columns]))

        try:
            mapa = criar_mapa_geometria_real(
                gdf_mapa=gdf_filtrado,
                campo_cor=campo_cor,
                color_map=color_map,
                opacidade=opacidade,
                campos_popup=campos_popup,
            )

            folium_static(mapa, width=1250, height=720)

        except Exception as e:
            st.error(f"Erro ao renderizar o mapa: {e}")

# =========================================================
# ABA 2: INDICADORES E ESTATÍSTICAS
# =========================================================
with tab_stats:
    st.markdown("### Painel Analítico & KPIs")

    qtd_pontes = len(gdf_filtrado)
    ext_total = float(gdf_filtrado[col_extensao].sum()) if not gdf_filtrado.empty else 0.0
    ext_executada = float(gdf_filtrado[col_executado].sum()) if not gdf_filtrado.empty else 0.0
    progresso_geral = (ext_executada / ext_total * 100) if ext_total > 0 else 0.0

    met1, met2, met3, met4 = st.columns(4)

    with met1:
        st.markdown(
            card_metric("Total de Pontes", f"{qtd_pontes}", "Pontes filtradas", "#ff4b4b", "🌉"),
            unsafe_allow_html=True,
        )

    with met2:
        st.markdown(
            card_metric("Extensão Total", f"{ext_total:,.1f} m", "Comprimento planejado", "#00c0f2", "📐"),
            unsafe_allow_html=True,
        )

    with met3:
        st.markdown(
            card_metric("Executado", f"{ext_executada:,.1f} m", "Comprimento concluído", "#00a65a", "📏"),
            unsafe_allow_html=True,
        )

    with met4:
        st.markdown(
            card_metric("Progresso Geral", f"{progresso_geral:.1f}%", "Avanço físico total", "#f39c12", "📈"),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    graf1, graf2 = st.columns(2)

    with graf1:
        st.markdown("##### Distribuição de Pontes por Bairro")

        if gdf_filtrado.empty:
            st.info("Sem dados para exibir.")
        else:
            df_bairro = gdf_filtrado[col_bairro].value_counts().reset_index()
            df_bairro.columns = ["Bairro", "Quantidade"]

            fig_bairro = px.bar(
                df_bairro,
                x="Bairro",
                y="Quantidade",
                text="Quantidade",
                color="Bairro",
                color_discrete_sequence=px.colors.qualitative.Bold,
                template="plotly_white",
            )

            fig_bairro.update_traces(textposition="outside")
            fig_bairro.update_layout(
                showlegend=False,
                margin=dict(l=20, r=20, t=20, b=20),
                height=360,
            )

            st.plotly_chart(fig_bairro, use_container_width=True)

    with graf2:
        st.markdown("##### Status das Obras das Pontes")

        if gdf_filtrado.empty:
            st.info("Sem dados para exibir.")
        else:
            df_status = gdf_filtrado[col_situacao].value_counts().reset_index()
            df_status.columns = ["Situação", "Quantidade"]

            fig_status = px.pie(
                df_status,
                names="Situação",
                values="Quantidade",
                color="Situação",
                color_discrete_map=color_map,
                hole=0.4,
                template="plotly_white",
            )

            fig_status.update_traces(textinfo="percent+value")
            fig_status.update_layout(
                margin=dict(l=20, r=20, t=20, b=20),
                height=360,
                legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5),
            )

            st.plotly_chart(fig_status, use_container_width=True)

# =========================================================
# ABA 3: TABELA
# =========================================================
with tab_dados:
    st.markdown("### Tabela de Dados Geográficos")

    df_exibicao = gdf_filtrado.drop(columns=["geometry", "_lat", "_lon", "_centroide"], errors="ignore")

    termo_pesquisa = st.text_input(
        "Filtrar registros na tabela",
        placeholder="Digite um valor para buscar na tabela...",
    )

    if termo_pesquisa:
        mask = df_exibicao.astype(str).apply(
            lambda x: x.str.contains(termo_pesquisa, case=False, na=False)
        ).any(axis=1)
        df_exibicao = df_exibicao[mask]

    st.markdown(f"Exibindo **{len(df_exibicao)}** de **{len(gdf_filtrado)}** registros filtrados.")

    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### 📥 Exportar Dados")

    exp1, exp2, exp3 = st.columns(3)

    csv_data = df_exibicao.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")

    with exp1:
        st.download_button(
            label="📄 Baixar CSV",
            data=csv_data,
            file_name="pontes_filtradas.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with exp2:
        gdf_export = gdf_filtrado.drop(columns=["_lat", "_lon", "_centroide"], errors="ignore").copy()
        geojson_export = preparar_geojson_seguro(gdf_export)

        st.download_button(
            label="🌍 Baixar GeoJSON",
            data=json.dumps(geojson_export, ensure_ascii=False),
            file_name="pontes_filtradas.geojson",
            mime="application/json",
            use_container_width=True,
        )

    with exp3:
        try:
            import io

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_exibicao.to_excel(writer, index=False, sheet_name="Pontes")

            st.download_button(
                label="📊 Baixar XLSX",
                data=output.getvalue(),
                file_name="pontes_filtradas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        except Exception:
            st.info("Instale `openpyxl` para exportar em XLSX.")

# =========================================================
# ABA 4: SOBRE
# =========================================================
with tab_sobre:
    st.markdown("### Sobre o Geoportal")

    tipos_geometria = ", ".join(sorted(gdf.geom_type.dropna().unique()))

    st.markdown(
        f"""
        Este **Geoportal WebGIS** foi construído para apoiar a visualização,
        o planejamento e o controle de execução física das pontes do Projeto Ponte Firme.

        #### ⚙️ Dados carregados

        - **Arquivo:** `{caminho_dados.name}`
        - **CRS:** `{gdf.crs}`
        - **Total de feições:** `{len(gdf)}`
        - **Tipos de geometria:** `{tipos_geometria}`

        #### 🗺️ Observação importante

        O mapa renderiza a **geometria real do arquivo geográfico**.
        Portanto, se a ponte estiver desenhada como linha ou polígono no GeoJSON/Shapefile,
        ela aparecerá no formato original, e não como bolinha.
        """
    )

# =========================================================
# RODAPÉ
# =========================================================
st.markdown("---")
st.caption(f"Geoportal Ponte Firme © {pd.Timestamp.now().year} - Desenvolvido em Streamlit, GeoPandas e Folium.")
