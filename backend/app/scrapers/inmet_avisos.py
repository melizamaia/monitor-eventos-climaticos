"""
Cliente dos avisos meteorológicos oficiais do INMET.
Fonte: feed RSS público (https://apiprevmet3.inmet.gov.br/avisos/rss).

O feed cobre o Brasil inteiro; cada item traz uma tabela HTML (dentro de um
CDATA) com Evento, Severidade, Início, Fim, Descrição e Área. Como o pipeline
só cobre RJ/SP, filtramos pela Área, que o INMET expressa como mesorregiões
do IBGE (ex.: "Litoral Sul Fluminense", "Metropolitana de São Paulo"), não
como nomes de estado.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import requests

from app.scrapers.cor_rio_scraper import BoletimEvento

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RSS_URL = "https://apiprevmet3.inmet.gov.br/avisos/rss"

# Substrings (case-insensitive) que identificam áreas de RJ/SP nos nomes de
# mesorregião usados pelo INMET.
TERMOS_RJ_SP = ["rio de janeiro", "fluminense", "são paulo", "sao paulo", "paulista"]

MAPA_SEVERIDADE_INMET = {
    "perigo potencial": "moderada",
    "perigo": "alta",
    "grande perigo": "extrema",
}

_LINHA_TABELA = re.compile(r"<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_PREFIXO_AREA = re.compile(r"^aviso para as áreas?:\s*", re.IGNORECASE)


def mapear_severidade_inmet(severidade_inmet: str) -> str:
    chave = (severidade_inmet or "").strip().lower()
    return MAPA_SEVERIDADE_INMET.get(chave, "moderada")


def _limpar_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", " ", texto or "").strip()


def _limpar_area(area: str) -> str:
    return _PREFIXO_AREA.sub("", area or "").strip()


def _parsear_campos(descricao_html: str) -> dict[str, str]:
    campos = {}
    for rotulo, valor in _LINHA_TABELA.findall(descricao_html or ""):
        campos[_limpar_html(rotulo)] = _limpar_html(valor)
    return campos


def _regioes_relevantes(area: str) -> list[str]:
    # Um mesmo aviso costuma listar dezenas de mesorregiões de todo o Brasil (ex.:
    # avisos de baixa umidade ou tempestades regionais). Reduzimos a Área às
    # mesorregiões de RJ/SP para não vazar regiões de outros estados no título nem
    # no contexto passado ao Gemini para geolocalização.
    regioes = [r.strip() for r in (area or "").split(",") if r.strip()]
    return [r for r in regioes if any(termo in r.lower() for termo in TERMOS_RJ_SP)]


def coletar_avisos_inmet() -> list[BoletimEvento]:
    try:
        resposta = requests.get(
            RSS_URL, headers={"User-Agent": "monitor-eventos-climaticos-app"}, timeout=15
        )
        resposta.raise_for_status()
        raiz = ET.fromstring(resposta.content)
    except requests.RequestException as e:
        logger.error("Erro ao acessar o feed RSS do INMET: %s", e)
        return []
    except ET.ParseError as e:
        logger.error("Erro ao parsear o XML do feed RSS do INMET: %s", e)
        return []

    avisos: list[BoletimEvento] = []

    for item in raiz.findall(".//item"):
        try:
            link_el = item.find("link")
            descricao_el = item.find("description")
            url = link_el.text.strip() if link_el is not None and link_el.text else ""
            campos = _parsear_campos(descricao_el.text if descricao_el is not None else "")

            area = _limpar_area(campos.get("Área", ""))
            regioes_relevantes = _regioes_relevantes(area)
            if not regioes_relevantes:
                continue
            area_rj_sp = ", ".join(regioes_relevantes)

            evento_nome = campos.get("Evento") or "Aviso Meteorológico"
            severidade_texto = campos.get("Severidade", "")
            inicio = campos.get("Início", "")
            descricao = campos.get("Descrição", "")

            avisos.append(
                BoletimEvento(
                    titulo=f"{evento_nome} - {area_rj_sp}",
                    data_texto=inicio,
                    url=url,
                    resumo=descricao,
                    fonte="INMET",
                    severidade_origem=mapear_severidade_inmet(severidade_texto),
                    area_texto=area_rj_sp,
                )
            )
        except Exception as e:
            logger.warning("Falha ao processar item do feed do INMET. Pulando. Erro: %s", e)
            continue

    logger.info("Avisos do INMET relevantes para RJ/SP: %d", len(avisos))
    return avisos


if __name__ == "__main__":
    resultado = coletar_avisos_inmet()

    print(f"\n{'=' * 60}")
    print(f"AVISOS DO INMET — RJ/SP ({len(resultado)})")
    print(f"{'=' * 60}\n")
    for aviso in resultado:
        print(f"[{aviso.data_texto}] {aviso.titulo} (severidade: {aviso.severidade_origem})")
        print(f"  {aviso.url}")
        print(f"  {aviso.resumo[:120]}...\n")
