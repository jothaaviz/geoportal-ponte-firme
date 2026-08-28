# Geoportal Ponte Firme

Aplicação WebGIS para visualizar, filtrar e acompanhar a execução física das passarelas do Projeto Ponte Firme.

## O que o sistema oferece

- mapa interativo com a geometria real das passarelas;
- filtros por identificação, município, bairro, situação e extensão;
- comparação entre extensão prevista e executada;
- indicadores, gráficos e auditoria de qualidade cadastral;
- exportação da seleção em CSV, GeoJSON e XLSX.

## Regra de execução física

O sistema calcula o saldo como:

```text
saldo = extensão prevista - extensão executada
```

- saldo positivo: execução abaixo do previsto;
- saldo zero: execução conforme o previsto;
- saldo negativo: execução acima do previsto.

Uma execução acima ou abaixo do tamanho recomendado é uma informação de gestão, não um erro cadastral. O status da obra é mantido como informação administrativa independente.

## Estrutura

```text
app.py                    Interface Streamlit
ponte_firme/dados.py      Carregamento, normalização e auditoria
ponte_firme/metricas.py   Indicadores consolidados
ponte_firme/mapa.py       Mapa Folium e exportação GeoJSON
dados/pontes/             Base geográfica
tests/                    Testes automatizados
```

## Executar no Windows

Com o ambiente já preparado neste projeto:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Para recriar o ambiente com Python 3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Abra `http://localhost:8501` no navegador.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Atualizar a base

Coloque um arquivo `.geojson`, `.json`, `.gpkg` ou `.shp` em `dados/pontes`. Quando houver mais de um arquivo, o sistema usa o primeiro nome encontrado dentro da prioridade de formatos documentada no código.

Na barra lateral, revise o mapeamento automático dos campos. Os atributos mínimos esperados são identificação, município, bairro, situação, extensão prevista e extensão executada.

## Qualidade cadastral

A aba **Qualidade** apresenta campos ausentes, identificações repetidas e problemas geométricos. Nenhum registro é alterado ou descartado pela auditoria.
