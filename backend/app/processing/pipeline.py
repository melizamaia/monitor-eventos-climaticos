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
    bairro_ou_zona = localizacao.get("bairro_ou_zona")
    latitude, longitude = geocodificar(municipio, estado, bairro_ou_zona)

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


def gerar_eventos_reais() -> dict:
    logger.info("Iniciando pipeline de geração de eventos reais")

    # O histórico gerado antes da extração de bairro/zona tem todas as coordenadas
    # concentradas no centro do Rio (fallback genérico), então não faz sentido mesclar
    # com ele. Descartamos o eventos_reais.geojson existente e reprocessamos todos os
    # boletins do zero com a nova extração de localização.
    urls_existentes: set[str] = set()

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
        "Novos eventos: %d | Duplicados (nesta mesma execução): %d | Falhas: %d",
        len(novos_eventos),
        duplicados,
        falhas,
    )

    features_combinadas = [_evento_para_feature(evento) for evento in novos_eventos]

    logger.info("Histórico final (reprocessado do zero): %d eventos salvos", len(features_combinadas))

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
