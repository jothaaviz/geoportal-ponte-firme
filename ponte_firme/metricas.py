"""Cálculos consolidados do painel."""

from __future__ import annotations

import pandas as pd


def calcular_indicadores(df: pd.DataFrame, col_extensao: str, col_executado: str) -> dict[str, float | int]:
    previsto = float(df[col_extensao].sum()) if not df.empty else 0.0
    executado = float(df[col_executado].sum()) if not df.empty else 0.0
    return {
        "quantidade": int(len(df)),
        "previsto": previsto,
        "executado": executado,
        "saldo": previsto - executado,
        "progresso": executado / previsto * 100 if previsto > 0 else 0.0,
    }

