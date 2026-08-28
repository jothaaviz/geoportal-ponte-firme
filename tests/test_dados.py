import math

import geopandas as gpd
from shapely.geometry import LineString

from ponte_firme.dados import auditar_dados, classificar_execucao, preparar_dados
from ponte_firme.metricas import calcular_indicadores


CAMPOS = {
    "nome": "Nome",
    "municipio": "Municipio",
    "bairro": "Bairro",
    "situacao": "Status",
    "extensao": "Previsto",
    "executado": "Executado",
}


def criar_base():
    return gpd.GeoDataFrame(
        {
            "Nome": ["A", "B", None],
            "Municipio": ["Macapa", "SANTANA", None],
            "Bairro": ["Centro", "Centro", None],
            "Status": ["Concluída", "Concluída", "Em Execução"],
            "Previsto": [100, 100, None],
            "Executado": [110, 90, None],
        },
        geometry=[LineString([(0, 0), (1, 1)])] * 3,
        crs="EPSG:4326",
    )


def test_classificacao_aceita_execucao_acima_e_abaixo():
    assert classificar_execucao(100, 110) == "Acima do previsto"
    assert classificar_execucao(100, 90) == "Abaixo do previsto"
    assert classificar_execucao(100, 100) == "Conforme previsto"


def test_preparacao_calcula_saldo_sem_tratar_negativo_como_erro():
    dados = preparar_dados(criar_base(), CAMPOS)
    assert dados["Saldo de extensão (m)"].iloc[0] == -10
    assert dados["Saldo de extensão (m)"].iloc[1] == 10
    assert math.isnan(dados["Saldo de extensão (m)"].iloc[2])


def test_indicadores_usam_previsto_e_executado():
    dados = preparar_dados(criar_base(), CAMPOS)
    indicadores = calcular_indicadores(dados, "Previsto", "Executado")
    assert indicadores == {"quantidade": 3, "previsto": 200.0, "executado": 200.0, "saldo": 0.0, "progresso": 100.0}


def test_auditoria_aponta_ausencias_cadastrais():
    dados = preparar_dados(criar_base(), CAMPOS)
    auditoria = auditar_dados(dados, CAMPOS)
    assert "Sem identificação" in auditoria["Verificação"].tolist()
    assert "Geometrias inválidas" not in auditoria["Verificação"].tolist()

