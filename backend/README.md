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
│   ├── geocoding.py
│   └── pipeline.py
├── ai/
│   └── gemini_client.py
├── models/
│   └── evento.py
└── data/
    ├── eventos_mock.geojson
    └── eventos_reais.geojson
```

## Coleta de dados (COR-Rio)

A coleta é feita com um cliente HTTP simples (`requests`), consumindo a REST API
pública do WordPress do COR-Rio (`https://cor.rio/wp-json/wp/v2/posts`), filtrando
por categorias relevantes (`Previsão do Tempo`, `Alagamentos`, `Estágios`).

> **Nota técnica:** a página `/boletins/` do site não tem paginação real — o post
> type "boletim" tem apenas 2 posts em toda a história do site, e
> `/boletins/page/2/` retorna 404. O conteúdo de eventos climáticos está, na
> prática, no blog geral do site, exposto via API JSON com paginação nativa e
> confiável. Isso tornou desnecessária a automação de navegador (Selenium) para
> esta coleta.

## Status atual

- [x] Coleta de boletins via REST API do WordPress (COR-Rio)
- [x] Classificação e extração de localização (município/estado/bairro-zona) via Gemini
- [x] Geocoding por bairro/zona (Nominatim), com fallback para o centro do Rio
- [x] Pipeline ligando coleta -> IA -> geocoding -> GeoJSON real, servido pela API
- [ ] SQLite como storage (v1.1)

## Variáveis de ambiente necessárias

Crie um arquivo `.env` na raiz de `backend/` com:

```
GEMINI_API_KEY=sua-chave-aqui
```

Obtenha uma chave gratuita em https://aistudio.google.com/apikey
