"""
Monitor de Eventos Climáticos Extremos - API
"""

import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Monitor de Eventos Climáticos Extremos",
    description="API que expõe eventos climáticos extremos coletados no RJ/SP",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DATA_DIR = Path(__file__).parent / "data"
DATA_PATH_REAL = DATA_DIR / "eventos_reais.geojson"
DATA_PATH_MOCK = DATA_DIR / "eventos_mock.geojson"
DATA_PATH_TEMPERATURAS = DATA_DIR / "temperaturas_estacoes.json"


def carregar_eventos() -> dict:
    caminho = DATA_PATH_REAL if DATA_PATH_REAL.exists() else DATA_PATH_MOCK
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Arquivo de eventos não encontrado")
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


@app.get("/")
def raiz():
    return {"status": "ok", "servico": "Monitor de Eventos Climáticos Extremos"}


@app.get("/eventos")
def listar_eventos(
    estado: str | None = Query(None, description="Filtrar por estado: RJ ou SP"),
    tipo: str | None = Query(None, description="Filtrar por tipo de evento"),
):
    geojson = carregar_eventos()
    features = geojson["features"]
    if estado:
        features = [f for f in features if f["properties"]["estado"].upper() == estado.upper()]
    if tipo:
        features = [f for f in features if f["properties"]["tipo"] == tipo]
    return {"type": "FeatureCollection", "features": features}


@app.get("/eventos/{evento_id}")
def obter_evento(evento_id: str):
    geojson = carregar_eventos()
    for feature in geojson["features"]:
        if feature["properties"]["id"] == evento_id:
            return feature
    raise HTTPException(status_code=404, detail="Evento não encontrado")


@app.get("/temperaturas")
def listar_temperaturas():
    if not DATA_PATH_TEMPERATURAS.exists():
        logger.warning(
            "Arquivo de temperaturas não encontrado em %s", DATA_PATH_TEMPERATURAS
        )
        return []
    with open(DATA_PATH_TEMPERATURAS, encoding="utf-8") as f:
        return json.load(f)
