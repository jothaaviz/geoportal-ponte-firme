"""Carregamento, preparação e auditoria da base de passarelas."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


EXTENSOES_SUPORTADAS = ("*.geojson", "*.json", "*.gpkg", "*.shp")


def localizar_arquivo_dados(pasta: Path) -> Path | None:
    """Retorna o primeiro arquivo geográfico em ordem previsível."""
    if not pasta.exists():
        return None
    for extensao in EXTENSOES_SUPORTADAS:
        arquivos = sorted(pasta.glob(extensao), key=lambda item: item.name.lower())
        if arquivos:
            return arquivos[0]
    return None


def carregar_dados(caminho_dados: str | Path) -> gpd.GeoDataFrame:
    """Carrega dados geográficos, valida o CRS e converte para WGS84."""
    gdf = gpd.read_file(caminho_dados)
    if gdf.empty:
        return gdf
    if gdf.crs is None:
        raise ValueError("O arquivo geográfico não informa o sistema de coordenadas (CRS).")
    gdf = gdf.to_crs(epsg=4326)
    try:
        gdf["geometry"] = gdf.geometry.make_valid()
    except (AttributeError, NotImplementedError):
        pass
    return gdf


def autodetectar_coluna(colunas, palavras_chave):
    """Identifica uma coluna por igualdade e, depois, por correspondência parcial."""
    colunas_lista = list(colunas)
    for coluna in colunas_lista:
        texto = str(coluna).lower().strip()
        if any(texto == palavra for palavra in palavras_chave):
            return coluna
    for coluna in colunas_lista:
        texto = str(coluna).lower().strip()
        if any(palavra in texto for palavra in palavras_chave):
            return coluna
    return None


def normalizar_texto(valor) -> str:
    if valor is None or pd.isna(valor) or not str(valor).strip():
        return "Não Informado"
    return str(valor).strip()


def padronizar_municipio(valor) -> str:
    texto = normalizar_texto(valor)
    chave = texto.casefold()
    mapa = {
        "laranjão do jari": "Laranjal do Jari",
        "laranjal do jari": "Laranjal do Jari",
        "macapa": "Macapá",
        "macapá": "Macapá",
        "santana": "Santana",
    }
    return mapa.get(chave, texto)


def converter_numero(serie: pd.Series) -> pd.Series:
    """Converte números reais e textos com vírgula decimal, preservando ausências."""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")
    texto = serie.astype("string").str.strip()
    texto = texto.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(texto, errors="coerce")


def classificar_execucao(previsto, executado, tolerancia: float = 0.10) -> str:
    """Classifica a execução sem considerar diferenças negativas como erro."""
    if pd.isna(previsto) or pd.isna(executado):
        return "Sem informação"
    diferenca = float(executado) - float(previsto)
    if diferenca > tolerancia:
        return "Acima do previsto"
    if diferenca < -tolerancia:
        return "Abaixo do previsto"
    return "Conforme previsto"


def preparar_dados(gdf: gpd.GeoDataFrame, campos: dict[str, str]) -> gpd.GeoDataFrame:
    """Normaliza atributos e adiciona saldo e classificação da execução."""
    saida = gdf.copy()
    for chave in ("extensao", "executado", "saldo_origem"):
        coluna = campos.get(chave)
        if coluna and coluna in saida.columns:
            saida[coluna] = converter_numero(saida[coluna])

    for chave in ("nome", "municipio", "situacao", "bairro"):
        coluna = campos[chave]
        saida[coluna] = saida[coluna].map(normalizar_texto)
    saida[campos["municipio"]] = saida[campos["municipio"]].map(padronizar_municipio)

    previsto = saida[campos["extensao"]]
    executado = saida[campos["executado"]]
    saida["Saldo de extensão (m)"] = previsto - executado
    saida["Variação (%)"] = np.where(previsto > 0, (executado - previsto) / previsto * 100, np.nan)
    saida["Classificação da execução"] = [
        classificar_execucao(p, e) for p, e in zip(previsto, executado)
    ]
    return saida


def auditar_dados(gdf: gpd.GeoDataFrame, campos: dict[str, str]) -> pd.DataFrame:
    """Produz um relatório de qualidade cadastral sem alterar os registros."""
    itens: list[dict[str, object]] = []
    rotulos = {
        "nome": "identificação",
        "municipio": "município",
        "bairro": "bairro",
        "extensao": "extensão prevista",
        "executado": "extensão executada",
    }
    for chave, rotulo in rotulos.items():
        coluna = campos[chave]
        serie = gdf[coluna]
        ausentes = serie.isna() | serie.astype("string").str.strip().isin(["", "Não Informado"])
        quantidade = int(ausentes.sum())
        if quantidade:
            itens.append({"Nível": "Atenção", "Verificação": f"Sem {rotulo}", "Registros": quantidade})

    nomes = gdf[campos["nome"]]
    duplicados = nomes[nomes.ne("Não Informado") & nomes.duplicated(keep=False)].nunique()
    if duplicados:
        itens.append({"Nível": "Revisar", "Verificação": "Identificações repetidas", "Registros": int(duplicados)})

    invalidas = int((~gdf.geometry.is_valid).sum())
    vazias = int((gdf.geometry.is_empty | gdf.geometry.isna()).sum())
    if invalidas:
        itens.append({"Nível": "Erro", "Verificação": "Geometrias inválidas", "Registros": invalidas})
    if vazias:
        itens.append({"Nível": "Erro", "Verificação": "Geometrias vazias", "Registros": vazias})

    return pd.DataFrame(itens, columns=["Nível", "Verificação", "Registros"])

