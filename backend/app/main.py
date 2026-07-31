"""
Monitor de Eventos Climáticos Extremos - API
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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

DATA_PATH = Path(__file__).parent / "data" / "eventos_mock.geojson"


def carregar_eventos() -> dict:
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="Arquivo de eventos não encontrado")
    with open(DATA_PATH, encoding="utf-8") as f:
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
