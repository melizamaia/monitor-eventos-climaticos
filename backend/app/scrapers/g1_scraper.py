"""
Cliente do G1 — feeds RSS regionais do Rio de Janeiro e São Paulo.
Fonte: RSS 2.0 público (https://g1.globo.com/rss/g1/<regiao>/).

As URLs no formato /dynamo/<regiao>/rss2.xml e /rss/g1/<regiao>/ servem
exatamente o mesmo conteúdo (mesmos itens, na mesma ordem) — usamos apenas o
segundo formato para não coletar a mesma notícia duas vezes. O feed geral
(/dynamo/rss2.xml, sem região) não é usado porque os dois feeds regionais já
respondem normalmente e cobrem RJ e SP diretamente, sem precisar filtrar
notícias de outros estados por menção a RJ/SP no texto.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET

import requests

from app.scrapers.cor_rio_scraper import BoletimEvento, filtrar_eventos_climaticos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "monitor-eventos-climaticos-app"}

FEEDS_G1 = {
    "rio-de-janeiro": "https://g1.globo.com/rss/g1/rio-de-janeiro/",
    "sao-paulo": "https://g1.globo.com/rss/g1/sao-paulo/",
}

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _limpar_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", " ", texto or "").strip()


def _resumo_do_item(item: ET.Element) -> str:
    # atom:subtitle já vem como texto puro; description traz HTML (imagem +
    # texto) e só é usada como alternativa quando subtitle está ausente.
    subtitle = item.find("atom:subtitle", ATOM_NS)
    if subtitle is not None and subtitle.text:
        return subtitle.text.strip()
    return _limpar_html(item.findtext("description", ""))


def _buscar_feed(url: str) -> list[ET.Element]:
    resposta = requests.get(url, headers=HEADERS, timeout=15)
    resposta.raise_for_status()
    root = ET.fromstring(resposta.content)
    channel = root.find("channel")
    return channel.findall("item") if channel is not None else []


def coletar_noticias_g1() -> list[BoletimEvento]:
    boletins: list[BoletimEvento] = []
    urls_vistas: set[str] = set()

    for regiao, feed_url in FEEDS_G1.items():
        try:
            items = _buscar_feed(feed_url)
        except requests.RequestException as e:
            logger.error("Erro ao acessar o feed RSS do G1 (%s): %s", regiao, e)
            continue
        except ET.ParseError as e:
            logger.error("Erro ao parsear o feed RSS do G1 (%s): %s", regiao, e)
            continue

        logger.info("Feed G1 '%s': %d itens", regiao, len(items))

        for item in items:
            url = (item.findtext("link", "") or "").strip()
            if not url or url in urls_vistas:
                continue

            titulo = (item.findtext("title", "") or "").strip()
            if not titulo:
                continue

            urls_vistas.add(url)
            boletins.append(
                BoletimEvento(
                    titulo=titulo,
                    data_texto=(item.findtext("pubDate", "") or "").strip(),
                    url=url,
                    resumo=_resumo_do_item(item),
                    fonte="G1",
                )
            )

    logger.info("Total de notícias coletadas do G1: %d", len(boletins))
    climaticas = filtrar_eventos_climaticos(boletins)
    return climaticas


if __name__ == "__main__":
    resultado = coletar_noticias_g1()

    print(f"\n{'=' * 60}")
    print(f"G1 — EVENTOS CLIMÁTICOS ({len(resultado)})")
    print(f"{'=' * 60}\n")
    for b in resultado:
        print(f"[{b.data_texto}] {b.titulo}")
        print(f"  {b.url}")
        print(f"  {b.resumo[:120]}...\n")
