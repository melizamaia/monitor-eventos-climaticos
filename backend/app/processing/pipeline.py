"""
Pipeline principal: coleta boletins do COR-Rio, classifica e geolocaliza cada um
com o Gemini, e gera o GeoJSON de eventos reais consumido pela API.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from dateutil import parser as date_parser

from app.ai.gemini_client import classificar_evento, extrair_localizacao
from app.models.evento import Evento
from app.processing.geocoding import geocodificar
from app.scrapers.cor_rio_scraper import BoletimEvento, coletar_boletins, filtrar_eventos_climaticos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent.parent / "data" / "eventos_reais.geojson"

PALAVRAS_SEVERIDADE_ALTA = ["extrem", "grave", "crític", "critic"]
PALAVRAS_SEVERIDADE_MODERADA = ["risco", "atenção", "atencao"]


def _severidade_heuristica(titulo: str, resumo: str) -> str:
    texto = f"{titulo} {resumo}".lower()
    if any(palavra in texto for palavra in PALAVRAS_SEVERIDADE_ALTA):
        return "alta"
    if any(palavra in texto for palavra in PALAVRAS_SEVERIDADE_MODERADA):
        return "moderada"
    return "baixa"


def _parsear_data(data_texto: str) -> datetime:
    if data_texto:
        try:
            return date_parser.parse(data_texto, dayfirst=True, fuzzy=True)
        except (ValueError, OverflowError):
            logger.warning("Não foi possível parsear a data '%s'. Usando data de hoje.", data_texto)
    return datetime.now()


def _boletim_para_evento(boletim: BoletimEvento, indice: int) -> Evento:
    classificacao = classificar_evento(boletim.titulo, boletim.resumo)
    localizacao = extrair_localizacao(boletim.titulo, boletim.resumo)

    municipio = localizacao["municipio"]
    estado = localizacao["estado"]
    latitude, longitude = geocodificar(municipio, estado)

    severidade = _severidade_heuristica(boletim.titulo, boletim.resumo)
    data_ocorrencia = _parsear_data(boletim.data_texto)

    return Evento(
        id=f"cor-rio-{data_ocorrencia.strftime('%Y-%m-%d')}-{indice:03d}",
        fonte=boletim.fonte,
        tipo=classificacao["tipo"],
        severidade=severidade,
        municipio=municipio,
        estado=estado,
        latitude=latitude,
        longitude=longitude,
        data_ocorrencia=data_ocorrencia,
        descricao=boletim.resumo or boletim.titulo,
        url=boletim.url,
    )


def _evento_para_feature(evento: Evento) -> dict:
    propriedades = json.loads(evento.model_dump_json())
    latitude = propriedades.pop("latitude")
    longitude = propriedades.pop("longitude")

    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
        "properties": propriedades,
    }


def _carregar_historico() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            geojson_existente = json.load(f)
        return geojson_existente.get("features", [])
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(
            "Não foi possível ler o histórico existente em %s (%s). Iniciando do zero.",
            DATA_PATH,
            e,
        )
        return []


def gerar_eventos_reais() -> dict:
    logger.info("Iniciando pipeline de geração de eventos reais")

    features_existentes = _carregar_historico()
    urls_existentes = {
        feature["properties"]["url"]
        for feature in features_existentes
        if feature.get("properties", {}).get("url")
    }
    logger.info("Eventos já existentes no histórico: %d", len(features_existentes))

    boletins = coletar_boletins()
    climaticos = filtrar_eventos_climaticos(boletins)
    logger.info("Boletins a processar nesta execução: %d", len(climaticos))

    novos_eventos: list[Evento] = []
    duplicados = 0
    falhas = 0

    for indice, boletim in enumerate(climaticos, start=1):
        if boletim.url in urls_existentes:
            duplicados += 1
            continue
        try:
            evento = _boletim_para_evento(boletim, indice)
            novos_eventos.append(evento)
            urls_existentes.add(boletim.url)
        except Exception as e:
            falhas += 1
            logger.warning("Falha ao processar boletim '%s': %s. Pulando.", boletim.titulo, e)
            continue

    logger.info(
        "Novos eventos: %d | Duplicados (já existiam): %d | Falhas: %d",
        len(novos_eventos),
        duplicados,
        falhas,
    )

    novas_features = [_evento_para_feature(evento) for evento in novos_eventos]
    features_combinadas = features_existentes + novas_features

    logger.info(
        "Histórico final: %d existentes + %d novos = %d eventos salvos",
        len(features_existentes),
        len(novas_features),
        len(features_combinadas),
    )

    geojson = {"type": "FeatureCollection", "features": features_combinadas}

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    logger.info("GeoJSON salvo em %s", DATA_PATH)

    return geojson


if __name__ == "__main__":
    resultado = gerar_eventos_reais()

    print(f"\n{'=' * 60}")
    print("PIPELINE DE EVENTOS REAIS CONCLUÍDO")
    print(f"{'=' * 60}")
    print(f"Eventos gerados: {len(resultado['features'])}")
    print(f"Arquivo salvo em: {DATA_PATH}")
