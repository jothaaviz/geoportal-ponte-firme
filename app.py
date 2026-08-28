"""Interface Streamlit do Geoportal Ponte Firme."""

from __future__ import annotations

import io
import json
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from ponte_firme.dados import (
    auditar_dados,
    autodetectar_coluna,
    carregar_dados,
    localizar_arquivo_dados,
    preparar_dados,
)
from ponte_firme.mapa import criar_mapa, preparar_geojson_seguro
from ponte_firme.metricas import calcular_indicadores


st.set_page_config(
    page_title="Geoportal Ponte Firme",
    page_icon="🌉",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
      [data-testid="stMetric"] {
        background: color-mix(in srgb, var(--secondary-background-color) 92%, transparent);
        border: 1px solid rgba(128,128,128,.22); border-radius: 12px; padding: 16px;
      }
      [data-testid="stMetricValue"] {font-size: 1.65rem;}
      iframe {max-width: 100%;}
      @media (max-width: 700px) {
        .block-container {padding-left: .8rem; padding-right: .8rem;}
        h1 {font-size: 1.75rem !important;}
      }
    </style>
    """,
    unsafe_allow_html=True,
)

BASE_DIR = Path(__file__).resolve().parent
PASTA_DADOS = BASE_DIR / "dados" / "pontes"


@st.cache_data(show_spinner="Carregando dados geográficos...")
def obter_dados(caminho: str):
    return carregar_dados(caminho)


def detectar_ou_usar_primeira(colunas, palavras):
    return autodetectar_coluna(colunas, palavras) or colunas[0]


def legenda_html(cores: dict, titulo: str) -> str:
    itens = "".join(
        f'<div style="display:flex;gap:8px;align-items:center;margin:6px 0">'
        f'<span style="width:14px;height:14px;border-radius:3px;background:{escape(cor)}"></span>'
        f'<span>{escape(str(valor))}</span></div>'
        for valor, cor in cores.items()
    )
    return f"<div><strong>{escape(titulo)}</strong>{itens}</div>"


def formatar_metros(valor: float) -> str:
    return f"{valor:,.1f} m".replace(",", "X").replace(".", ",").replace("X", ".")


st.title("🌉 Geoportal Ponte Firme")
st.caption("Monitoramento geográfico e físico das passarelas municipais")

caminho_dados = localizar_arquivo_dados(PASTA_DADOS)
if caminho_dados is None:
    st.error("Nenhum arquivo geográfico foi encontrado em `dados/pontes`.")
    st.stop()

try:
    gdf_original = obter_dados(str(caminho_dados))
except Exception as erro:
    st.error(f"Não foi possível carregar a base geográfica: {erro}")
    st.stop()

if gdf_original.empty:
    st.error("A base geográfica está vazia.")
    st.stop()

colunas = [coluna for coluna in gdf_original.columns if coluna != gdf_original.geometry.name]
if not colunas:
    st.error("A base não possui atributos além da geometria.")
    st.stop()

detectadas = {
    "nome": detectar_ou_usar_primeira(colunas, ["nome", "ponte", "passarela", "name", "id", "codigo", "código"]),
    "municipio": detectar_ou_usar_primeira(colunas, ["município", "municipio", "municipío", "nm_mun", "cidade", "mun"]),
    "situacao": detectar_ou_usar_primeira(colunas, ["status", "situacao", "situação", "fase", "estado", "condicao", "condição"]),
    "extensao": detectar_ou_usar_primeira(colunas, ["tamannho", "tamanho", "extensao", "extensão", "comprimento", "length", "metros"]),
    "executado": detectar_ou_usar_primeira(colunas, ["executado", "exec", "concluido", "concluído"]),
    "saldo_origem": autodetectar_coluna(colunas, ["faltaexe", "falta_exe", "restante", "a_executar", "falta"]),
    "bairro": detectar_ou_usar_primeira(colunas, ["bairro", "distrito", "localidade", "setor"]),
}

st.sidebar.markdown("## ⚙️ Configurações")
with st.sidebar.expander("Mapeamento dos campos"):
    st.caption("Revise somente se a detecção automática estiver incorreta.")
    campos = {
        "nome": st.selectbox("Identificação", colunas, index=colunas.index(detectadas["nome"])),
        "municipio": st.selectbox("Município", colunas, index=colunas.index(detectadas["municipio"])),
        "bairro": st.selectbox("Bairro", colunas, index=colunas.index(detectadas["bairro"])),
        "situacao": st.selectbox("Situação", colunas, index=colunas.index(detectadas["situacao"])),
        "extensao": st.selectbox("Extensão prevista", colunas, index=colunas.index(detectadas["extensao"])),
        "executado": st.selectbox("Extensão executada", colunas, index=colunas.index(detectadas["executado"])),
    }
campos["saldo_origem"] = detectadas["saldo_origem"]

try:
    gdf = preparar_dados(gdf_original, campos)
except Exception as erro:
    st.error(f"O mapeamento escolhido não pôde ser aplicado: {erro}")
    st.stop()

st.sidebar.markdown("### 🔎 Filtros")
busca = st.sidebar.text_input("Nome ou código", placeholder="Digite para localizar...")


def filtro_multisselecao(rotulo, coluna):
    opcoes = sorted(gdf[coluna].dropna().unique().tolist(), key=str)
    return st.sidebar.multiselect(rotulo, opcoes, default=opcoes)


municipios = filtro_multisselecao("Município", campos["municipio"])
bairros = filtro_multisselecao("Bairro", campos["bairro"])
situacoes = filtro_multisselecao("Situação", campos["situacao"])
classificacoes = filtro_multisselecao("Execução física", "Classificação da execução")

extensoes_validas = gdf[campos["extensao"]].dropna()
if extensoes_validas.empty:
    faixa_extensao = None
else:
    minimo = float(extensoes_validas.min())
    maximo = float(extensoes_validas.max())
    limite_maximo = maximo if maximo > minimo else minimo + 1.0
    faixa_extensao = st.sidebar.slider(
        "Extensão prevista (m)", minimo, limite_maximo, (minimo, limite_maximo), step=1.0
    )
incluir_sem_extensao = st.sidebar.checkbox("Incluir registros sem extensão", value=True)

filtrado = gdf.copy()
if busca:
    filtrado = filtrado[filtrado[campos["nome"]].str.contains(busca, case=False, na=False)]
filtrado = filtrado[
    filtrado[campos["municipio"]].isin(municipios)
    & filtrado[campos["bairro"]].isin(bairros)
    & filtrado[campos["situacao"]].isin(situacoes)
    & filtrado["Classificação da execução"].isin(classificacoes)
]
if faixa_extensao:
    dentro_faixa = filtrado[campos["extensao"]].between(*faixa_extensao)
    if incluir_sem_extensao:
        dentro_faixa |= filtrado[campos["extensao"]].isna()
    filtrado = filtrado[dentro_faixa]

st.sidebar.markdown("### 🎨 Mapa")
campos_cor = [campos["situacao"], "Classificação da execução", campos["municipio"], campos["bairro"]]
campo_cor = st.sidebar.selectbox("Colorir por", list(dict.fromkeys(campos_cor)))
opacidade = st.sidebar.slider("Opacidade", 0.1, 1.0, 0.9, 0.1)
paleta = px.colors.qualitative.Bold
valores_cor = sorted(filtrado[campo_cor].dropna().unique().tolist(), key=str)
cores = {valor: paleta[indice % len(paleta)] for indice, valor in enumerate(valores_cor)}
st.sidebar.markdown(legenda_html(cores, campo_cor), unsafe_allow_html=True)

tab_mapa, tab_indicadores, tab_dados, tab_qualidade, tab_sobre = st.tabs(
    ["🗺️ Mapa", "📊 Indicadores", "📋 Dados", "✅ Qualidade", "ℹ️ Sobre"]
)

with tab_mapa:
    st.subheader("Distribuição geográfica")
    st.caption(f"{len(filtrado)} de {len(gdf)} passarelas visíveis")
    if filtrado.empty:
        st.warning("Nenhuma passarela corresponde aos filtros selecionados.")
    else:
        popup = [
            campos["nome"], campos["municipio"], campos["bairro"], campos["situacao"],
            campos["extensao"], campos["executado"], "Saldo de extensão (m)",
            "Variação (%)", "Classificação da execução",
        ]
        try:
            mapa = criar_mapa(filtrado, campo_cor, cores, opacidade, popup)
            st_folium(mapa, height=700, width="stretch", returned_objects=[])
        except Exception as erro:
            st.error(f"Não foi possível renderizar o mapa: {erro}")

with tab_indicadores:
    st.subheader("Execução física")
    indicadores = calcular_indicadores(filtrado, campos["extensao"], campos["executado"])
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Passarelas", indicadores["quantidade"])
    col2.metric("Extensão prevista", formatar_metros(indicadores["previsto"]))
    col3.metric("Extensão executada", formatar_metros(indicadores["executado"]))
    col4.metric("Saldo", formatar_metros(indicadores["saldo"]), help="Previsto menos executado. Pode ser negativo.")
    col5.metric("Execução / previsto", f'{indicadores["progresso"]:.1f}%'.replace(".", ","))
    st.info(
        "O saldo negativo indica que a empresa construiu uma extensão maior que a prevista; "
        "o saldo positivo indica execução menor. Nenhuma das situações é tratada automaticamente como erro."
    )

    graf1, graf2 = st.columns(2)
    with graf1:
        contagem = filtrado[campos["situacao"]].value_counts().rename_axis("Situação").reset_index(name="Quantidade")
        fig = px.pie(contagem, names="Situação", values="Quantidade", hole=0.45, template="plotly_white")
        st.plotly_chart(fig, width="stretch")
    with graf2:
        contagem = filtrado["Classificação da execução"].value_counts().rename_axis("Classificação").reset_index(name="Quantidade")
        fig = px.bar(contagem, x="Classificação", y="Quantidade", text_auto=True, template="plotly_white")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, width="stretch")

with tab_dados:
    st.subheader("Tabela de atributos")
    exibicao = filtrado.drop(columns=[filtrado.geometry.name], errors="ignore")
    pesquisa = st.text_input("Pesquisar em todos os campos", placeholder="Nome, bairro, situação...")
    if pesquisa:
        mascara = exibicao.astype("string").apply(
            lambda coluna: coluna.str.contains(pesquisa, case=False, na=False)
        ).any(axis=1)
        exibicao = exibicao[mascara]
    st.dataframe(exibicao, width="stretch", hide_index=True)

    exp1, exp2, exp3 = st.columns(3)
    csv = exibicao.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    exp1.download_button("Baixar CSV", csv, "passarelas_filtradas.csv", "text/csv", width="stretch")
    geojson = json.dumps(preparar_geojson_seguro(filtrado), ensure_ascii=False)
    exp2.download_button("Baixar GeoJSON", geojson, "passarelas_filtradas.geojson", "application/geo+json", width="stretch")
    planilha = io.BytesIO()
    with pd.ExcelWriter(planilha, engine="openpyxl") as writer:
        exibicao.to_excel(writer, index=False, sheet_name="Passarelas")
    exp3.download_button(
        "Baixar XLSX", planilha.getvalue(), "passarelas_filtradas.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch",
    )

with tab_qualidade:
    st.subheader("Qualidade cadastral")
    st.caption("As verificações não alteram nem descartam registros da base original.")
    auditoria = auditar_dados(gdf, campos)
    if auditoria.empty:
        st.success("Nenhuma pendência cadastral foi identificada.")
    else:
        st.dataframe(auditoria, width="stretch", hide_index=True)
    st.markdown("#### Distribuição da execução")
    distribuicao = gdf["Classificação da execução"].value_counts().rename_axis("Classificação").reset_index(name="Registros")
    st.dataframe(distribuicao, width="stretch", hide_index=True)
    st.caption("Diferenças entre previsto e executado são informações de gestão, não erros cadastrais.")

with tab_sobre:
    st.subheader("Sobre o projeto")
    tipos = ", ".join(sorted(gdf.geom_type.dropna().unique()))
    st.markdown(
        f"""
        O Geoportal Ponte Firme apoia o acompanhamento territorial e físico das passarelas.

        - **Arquivo carregado:** `{caminho_dados.name}`
        - **Sistema de coordenadas:** `{gdf.crs}`
        - **Feições:** `{len(gdf)}`
        - **Geometrias:** `{tipos}`

        **Regra do saldo:** extensão prevista menos extensão executada. Um saldo negativo representa
        construção acima do tamanho recomendado; um saldo positivo representa construção abaixo do previsto.
        """
    )

st.divider()
st.caption(f"Geoportal Ponte Firme © {pd.Timestamp.now().year}")
