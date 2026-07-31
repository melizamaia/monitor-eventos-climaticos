"""
Cliente do COR-Rio — Centro de Operações e Resiliência.
Fonte: REST API do WordPress (https://cor.rio/wp-json/wp/v2/posts).

Antes este módulo usava Selenium para raspar a página /boletins/, mas o
post type "boletim" tem apenas 2 posts em toda a história do site, e
/boletins/page/2/ retorna 404 (não há paginação real ali). O conteúdo
real de eventos climáticos vive no blog geral do site, em categorias
específicas ("Previsão do Tempo", "Estágios", "Alagamentos") que somam
milhares de posts e são atualizadas diariamente. A REST API do WordPress
expõe esse conteúdo diretamente em JSON, com paginação nativa e confiável
(parâmetros page/per_page), então não é mais necessário automatizar um
navegador para esta coleta.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = "https://cor.rio/wp-json/wp/v2/posts"

# IDs das categorias do WordPress relacionadas a eventos climáticos.
# Ver GET https://cor.rio/wp-json/wp/v2/categories
CATEGORIAS_CLIMA = {
    29: "Previsão do Tempo",
    32: "Alagamentos",
    44: "Estágios",
}

PALAVRAS_CHAVE_CLIMA = [
    "chuva", "chuvas", "temporal", "ventania", "vento forte", "rajada",
    "tornado", "granizo", "alagamento", "enchente", "inundação",
    "deslizamento", "risco de temporal", "estágio de mobilização",
    "estágio", "calor extremo", "onda de calor", "protocolo de calor",
]

# O Alerta Rio publica boletins diários de previsão do tempo que sempre
# citam "chuva", mesmo quando a mensagem é justamente que NÃO vai chover
# (ex.: "sem previsão de chuva"). Sem isso, ~60% dos boletins de rotina
# seriam tratados como eventos climáticos. Removemos essas menções
# negadas antes de checar as palavras-chave, mas mantemos qualquer outro
# sinal positivo (ex.: "ventos fortes") que apareça no mesmo texto.
PADRAO_CHUVA_NEGADA = re.compile(
    r"(sem|n[ãa]o\s+h[áa])\s+"
    r"(previs[ãa]o\s+de\s+|possibilidade\s+de\s+|ocorr[êe]ncia\s+de\s+)?"
    r"chuvas?",
    re.IGNORECASE,
)


@dataclass
class BoletimEvento:
    titulo: str
    data_texto: str
    url: str
    resumo: str
    fonte: str = "COR-Rio"
    # Preenchidos apenas por fontes que já trazem severidade estruturada (ex.: INMET).
    # O COR-Rio não tem esse campo na origem, então o pipeline recorre à heurística
    # de palavras-chave nesse caso.
    severidade_origem: str | None = None
    area_texto: str | None = None

    def menciona_evento_climatico(self) -> bool:
        texto = f"{self.titulo} {self.resumo}".lower()
        texto = PADRAO_CHUVA_NEGADA.sub(" ", texto)
        return any(palavra in texto for palavra in PALAVRAS_CHAVE_CLIMA)


def _limpar_html(texto: str) -> str:
    return re.sub(r"<[^>]+>", " ", texto or "").strip()


def _buscar_pagina(categoria_id: int, pagina: int, por_pagina: int) -> list[dict]:
    params = {
        "categories": categoria_id,
        "page": pagina,
        "per_page": por_pagina,
        "orderby": "date",
        "order": "desc",
    }
    resposta = requests.get(BASE_URL, params=params, timeout=15)
    if resposta.status_code == 400:
        # WordPress retorna 400 quando a página solicitada excede o total
        # disponível — sinal de que a paginação acabou.
        return []
    resposta.raise_for_status()
    return resposta.json()


def coletar_boletins(max_boletins: int = 30, max_paginas: int = 5) -> list[BoletimEvento]:
    boletins: list[BoletimEvento] = []
    urls_vistas: set[str] = set()
    por_pagina = 10

    # Cada categoria tem seu próprio orçamento de max_boletins. Sem isso,
    # "Previsão do Tempo" (milhares de posts) esgotaria o limite global
    # antes mesmo de "Estágios" ou "Alagamentos" (dezenas de posts, mas
    # sinais muito mais fortes de evento real) serem consultadas.
    for categoria_id, nome_categoria in CATEGORIAS_CLIMA.items():
        coletados_da_categoria = 0

        for pagina in range(1, max_paginas + 1):
            if coletados_da_categoria >= max_boletins:
                break

            if pagina > 1:
                time.sleep(1.5)

            try:
                posts = _buscar_pagina(categoria_id, pagina, por_pagina)
            except requests.RequestException as e:
                logger.error(
                    "Erro ao acessar página %d da categoria '%s': %s", pagina, nome_categoria, e
                )
                break

            if not posts:
                logger.info(
                    "Categoria '%s': fim da paginação na página %d.", nome_categoria, pagina
                )
                break

            logger.info("Categoria '%s', página %d: %d posts", nome_categoria, pagina, len(posts))

            for post in posts:
                url = post.get("link", "")
                if not url or url in urls_vistas:
                    continue

                titulo = _limpar_html(post.get("title", {}).get("rendered", ""))
                resumo = _limpar_html(post.get("excerpt", {}).get("rendered", ""))
                data_texto = post.get("date", "")

                if not titulo:
                    continue

                urls_vistas.add(url)
                boletins.append(
                    BoletimEvento(titulo=titulo, data_texto=data_texto, url=url, resumo=resumo)
                )
                coletados_da_categoria += 1

                if coletados_da_categoria >= max_boletins:
                    break

    logger.info("Total de boletins coletados: %d", len(boletins))
    return boletins


def filtrar_eventos_climaticos(boletins: list[BoletimEvento]) -> list[BoletimEvento]:
    filtrados = [b for b in boletins if b.menciona_evento_climatico()]
    logger.info("Boletins com menção a evento climático: %d de %d", len(filtrados), len(boletins))
    return filtrados


if __name__ == "__main__":
    todos = coletar_boletins()
    climaticos = filtrar_eventos_climaticos(todos)

    print(f"\n{'=' * 60}")
    print(f"BOLETINS COM EVENTOS CLIMÁTICOS ({len(climaticos)})")
    print(f"{'=' * 60}\n")
    for b in climaticos:
        print(f"[{b.data_texto}] {b.titulo}")
        print(f"  {b.url}")
        print(f"  {b.resumo[:120]}...\n")

    resultado = [asdict(b) for b in climaticos]
