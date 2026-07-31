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

# Centro da cidade do Rio de Janeiro, usado como fallback quando a
# geocodificação falha ou a cidade não é encontrada.
COORDENADAS_PADRAO = (-22.9068, -43.1729)

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

    try:
        localizacao = _geolocator.geocode(query, timeout=10)
        time.sleep(1)  # respeita o limite de uso justo do Nominatim (1 req/s)

        if localizacao is None:
            logger.warning(
                "Não foi possível geocodificar '%s'. Usando coordenadas padrão do Rio de Janeiro.",
                query,
            )
            coordenadas = COORDENADAS_PADRAO
        else:
            coordenadas = (localizacao.latitude, localizacao.longitude)

    except GeopyError as e:
        logger.warning(
            "Erro ao geocodificar '%s': %s. Usando coordenadas padrão do Rio de Janeiro.",
            query,
            e,
        )
        coordenadas = COORDENADAS_PADRAO

    _cache[chave] = coordenadas
    return coordenadas
