"""Construção do mapa Folium e serialização geográfica."""

from __future__ import annotations

import json

import folium
from folium import plugins
import geopandas as gpd
import numpy as np
import pandas as pd


def valor_json_seguro(valor):
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(valor, np.integer):
        return int(valor)
    if isinstance(valor, np.floating):
        return float(valor)
    if isinstance(valor, pd.Timestamp):
        return valor.isoformat()
    if isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def preparar_geojson_seguro(gdf: gpd.GeoDataFrame) -> dict:
    saida = gdf.copy()
    for coluna in saida.columns:
        if coluna != saida.geometry.name:
            saida[coluna] = saida[coluna].map(valor_json_seguro)
    return json.loads(saida.to_json())


def estilo_geometria(feature):
    propriedades = feature.get("properties", {})
    cor = propriedades.get("_cor_mapa", "#808080")
    opacidade = propriedades.get("_opacidade_mapa", 0.9)
    return {"color": cor, "weight": 7, "opacity": opacidade, "fillColor": cor, "fillOpacity": 0.35}


def destaque_geometria(_feature):
    return {"color": "#ffff00", "weight": 10, "opacity": 1, "fillOpacity": 0.55}


def criar_mapa(gdf: gpd.GeoDataFrame, campo_cor: str, cores: dict, opacidade: float, campos_popup: list[str]):
    dados = gdf.to_crs(epsg=4326).copy()
    dados["_cor_mapa"] = dados[campo_cor].map(lambda valor: cores.get(valor, "#808080"))
    dados["_opacidade_mapa"] = float(opacidade)
    minx, miny, maxx, maxy = dados.total_bounds
    if not np.isfinite([minx, miny, maxx, maxy]).all():
        raise ValueError("A seleção contém coordenadas inválidas.")
    if minx == maxx and miny == maxy:
        minx, maxx, miny, maxy = minx - 0.01, maxx + 0.01, miny - 0.01, maxy + 0.01

    mapa = folium.Map(location=[(miny + maxy) / 2, (minx + maxx) / 2], tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(mapa)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles © Esri",
        name="Satélite Esri",
        show=False,
    ).add_to(mapa)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr="© OpenStreetMap © CARTO",
        name="Mapa claro",
        show=False,
    ).add_to(mapa)

    campos = list(dict.fromkeys(c for c in campos_popup if c in dados.columns))
    folium.GeoJson(
        preparar_geojson_seguro(dados),
        name="Passarelas",
        style_function=estilo_geometria,
        highlight_function=destaque_geometria,
        tooltip=folium.GeoJsonTooltip(fields=campos, aliases=[f"{c}:" for c in campos], sticky=True),
        popup=folium.GeoJsonPopup(fields=campos, aliases=[f"{c}:" for c in campos], max_width=380),
    ).add_to(mapa)
    mapa.fit_bounds([[miny, minx], [maxy, maxx]], padding=(40, 40), max_zoom=17)
    plugins.Fullscreen(position="topleft", title="Expandir mapa", title_cancel="Sair da tela cheia").add_to(mapa)
    folium.LayerControl(position="topright", collapsed=True).add_to(mapa)
    return mapa

