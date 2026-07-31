# Backend — Monitor de Eventos Climáticos Extremos

API em FastAPI que serve dados de eventos climáticos extremos (RJ/SP)
coletados de fontes públicas (COR-Rio, INMET).

## Setup

```bash
pyenv activate monitor-eventos-climaticos
pip install -r requirements.txt
uvicorn app.main:app --reload
```

A API sobe em `http://localhost:8000`.
Documentação interativa (Swagger): `http://localhost:8000/docs`

## Endpoints (MVP)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Healthcheck |
| GET | `/eventos` | Lista todos os eventos (GeoJSON). Filtros: `?estado=RJ`, `?tipo=vento_forte` |
| GET | `/eventos/{id}` | Retorna um evento específico |

## Estrutura

```
app/
├── main.py
├── scrapers/
│   └── cor_rio_scraper.py
├── processing/
├── ai/
│   └── gemini_client.py
├── models/
│   └── evento.py
└── data/
    └── eventos_mock.geojson
```

## Status atual

- [x] Endpoint `/eventos` servindo dados mockados
- [x] Scraper COR-Rio (Selenium)
- [x] Cliente Gemini (resumo + classificação)
- [ ] Pipeline pandas/geopandas ligando scraper -> IA -> GeoJSON real
- [ ] SQLite como storage (v1.1)

## Variáveis de ambiente necessárias

Crie um arquivo `.env` na raiz de `backend/` com:

```
GEMINI_API_KEY=sua-chave-aqui
```

Obtenha uma chave gratuita em https://aistudio.google.com/apikey
