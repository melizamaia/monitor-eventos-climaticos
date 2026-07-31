"""
Geocodificação de município/estado em latitude/longitude via Nominatim (OpenStreetMap).
"""

from __future__ import annotations

import logging
import time

from geopy.exc import GeopyError
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

USER_AGENT = "monitor-eventos-climaticos-app"

# Centro da cidade-sede de cada UF coberta pelo app, usado como fallback quando a
# geocodificação falha ou a cidade não é encontrada. Fixar sempre no Rio faria
# eventos de SP aparecerem no mapa como se fossem do Rio quando o Nominatim não
# reconhece a consulta (ex.: mesorregiões do INMET como "Litoral Sul Paulista").
COORDENADAS_PADRAO_POR_ESTADO = {
    "RJ": (-22.9068, -43.1729),
    "SP": (-23.5505, -46.6333),
}
COORDENADAS_PADRAO = COORDENADAS_PADRAO_POR_ESTADO["RJ"]

_geolocator = Nominatim(user_agent=USER_AGENT)
_cache: dict[str, tuple[float, float]] = {}


def geocodificar(
    municipio: str, estado: str, bairro_ou_zona: str | None = None
) -> tuple[float, float]:
    chave = f"{(bairro_ou_zona or '').strip().lower()}, {municipio.strip().lower()}, {estado.strip().lower()}"

    if chave in _cache:
        return _cache[chave]

    if bairro_ou_zona:
        query = f"{bairro_ou_zona}, {municipio}, {estado}, Brasil"
    else:
        query = f"{municipio}, {estado}, Brasil"

    coordenadas_padrao_estado = COORDENADAS_PADRAO_POR_ESTADO.get(estado.strip().upper(), COORDENADAS_PADRAO)

    try:
        localizacao = _geolocator.geocode(query, timeout=10)
        time.sleep(1)  # respeita o limite de uso justo do Nominatim (1 req/s)

        if localizacao is None:
            logger.warning(
                "Não foi possível geocodificar '%s'. Usando coordenadas padrão de %s.",
                query,
                estado,
            )
            coordenadas = coordenadas_padrao_estado
        else:
            coordenadas = (localizacao.latitude, localizacao.longitude)

    except GeopyError as e:
        logger.warning(
            "Erro ao geocodificar '%s': %s. Usando coordenadas padrão de %s.",
            query,
            e,
            estado,
        )
        coordenadas = coordenadas_padrao_estado

    _cache[chave] = coordenadas
    return coordenadas
