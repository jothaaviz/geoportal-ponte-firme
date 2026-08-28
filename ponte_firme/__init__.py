"""Núcleo do Geoportal Ponte Firme."""

from .dados import (
    auditar_dados,
    autodetectar_coluna,
    carregar_dados,
    classificar_execucao,
    localizar_arquivo_dados,
    normalizar_texto,
    padronizar_municipio,
    preparar_dados,
)
from .metricas import calcular_indicadores

__all__ = [
    "auditar_dados",
    "autodetectar_coluna",
    "calcular_indicadores",
    "carregar_dados",
    "classificar_execucao",
    "localizar_arquivo_dados",
    "normalizar_texto",
    "padronizar_municipio",
    "preparar_dados",
]

