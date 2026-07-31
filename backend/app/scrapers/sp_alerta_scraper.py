"""
Cliente do SP Sempre Alerta — Defesa Civil do Estado de São Paulo.
Fonte: REST API do WordPress (post type customizado "defesa-civil-alerta").

A API padrão de posts (/wp-json/wp/v2/posts) não tem nenhum conteúdo neste site
— todos os alertas vivem no post type customizado "defesa-civil-alerta" (mesmo
nome da seção "Defesa Civil Alerta" do menu do site). A taxonomia "category"
está atribuída a menos de 1 em cada 4 posts desse tipo, então filtrar por
categoria descartaria a maior parte dos alertas reais; por isso coletamos
todos os posts do CPT (paginados) e aplicamos o mesmo filtro por palavra-chave
usado no COR-Rio.

O site também não expõe "content" nem "excerpt" para esse post type — o corpo
do alerta é montado pelo Elementor fora do schema padrão do REST. O título é
o único texto disponível, mas já é bastante descritivo (ex.: "Defesa Civil
alerta para chuva, queda nas temperaturas e ventos com avanço de frente fria
em São Paulo").

O site exige um User-Agent não vazio: sem esse header a API responde 500 em
vez de 200.
"""

from __future__ import annotations

import logging
import time

import requests

from app.scrapers.cor_rio_scraper import BoletimEvento, filtrar_eventos_climaticos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://www.spsemprealerta.sp.gov.br/wp-json/wp/v2/defesa-civil-alerta"
HEADERS = {"User-Agent": "monitor-eventos-climaticos-app"}

# Termos da taxonomia "indices_alerta", exclusiva desse post type.
# Ver GET https://www.spsemprealerta.sp.gov.br/wp-json/wp/v2/indices_alerta
MAPA_SEVERIDADE_SP = {33: "alta", 34: "moderada", 35: "baixa"}


def mapear_severidade_sp(indices_alerta: list[int] | None) -> str | None:
    for indice_id in indices_alerta or []:
        if indice_id in MAPA_SEVERIDADE_SP:
            return MAPA_SEVERIDADE_SP[indice_id]
    return None


def _buscar_pagina(pagina: int, por_pagina: int) -> list[dict]:
    params = {"page": pagina, "per_page": por_pagina, "orderby": "date", "order": "desc"}
    resposta = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    if resposta.status_code == 400:
        # A API retorna 400 quando a página solicitada excede o total disponível.
        return []
    resposta.raise_for_status()
    return resposta.json()


def coletar_boletins_sp(max_boletins: int = 30, max_paginas: int = 5) -> list[BoletimEvento]:
    boletins: list[BoletimEvento] = []
    urls_vistas: set[str] = set()
    por_pagina = 10

    for pagina in range(1, max_paginas + 1):
        if len(boletins) >= max_boletins:
            break

        if pagina > 1:
            time.sleep(1.5)

        try:
            posts = _buscar_pagina(pagina, por_pagina)
        except requests.RequestException as e:
            logger.error("Erro ao acessar página %d do SP Sempre Alerta: %s", pagina, e)
            break

        if not posts:
            logger.info("SP Sempre Alerta: fim da paginação na página %d.", pagina)
            break

        logger.info("SP Sempre Alerta, página %d: %d posts", pagina, len(posts))

        for post in posts:
            url = post.get("link", "")
            if not url or url in urls_vistas:
                continue

            titulo = (post.get("title", {}).get("rendered", "") or "").strip()
            if not titulo:
                continue

            urls_vistas.add(url)
            boletins.append(
                BoletimEvento(
                    titulo=titulo,
                    data_texto=post.get("date", ""),
                    url=url,
                    resumo="",
                    fonte="SP Sempre Alerta",
                    severidade_origem=mapear_severidade_sp(post.get("indices_alerta")),
                )
            )

            if len(boletins) >= max_boletins:
                break

    logger.info("Total de boletins coletados do SP Sempre Alerta: %d", len(boletins))
    climaticos = filtrar_eventos_climaticos(boletins)
    return climaticos


if __name__ == "__main__":
    resultado = coletar_boletins_sp()

    print(f"\n{'=' * 60}")
    print(f"SP SEMPRE ALERTA — EVENTOS CLIMÁTICOS ({len(resultado)})")
    print(f"{'=' * 60}\n")
    for b in resultado:
        print(f"[{b.data_texto}] {b.titulo} (severidade origem: {b.severidade_origem})")
        print(f"  {b.url}\n")
