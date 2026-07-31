"""
Scraper RPA (Selenium) do COR-Rio — Centro de Operações e Resiliência.
Fonte: https://cor.rio/boletins/
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

URL_BOLETINS = "https://cor.rio/boletins/"

PALAVRAS_CHAVE_CLIMA = [
    "chuva", "chuvas", "temporal", "ventania", "vento forte", "rajada",
    "tornado", "granizo", "alagamento", "enchente", "inundação",
    "deslizamento", "risco de temporal", "estágio de mobilização",
]


@dataclass
class BoletimEvento:
    titulo: str
    data_texto: str
    url: str
    resumo: str
    fonte: str = "COR-Rio"

    def menciona_evento_climatico(self) -> bool:
        texto = f"{self.titulo} {self.resumo}".lower()
        return any(palavra in texto for palavra in PALAVRAS_CHAVE_CLIMA)


def _criar_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def coletar_boletins(max_boletins: int = 30, headless: bool = True) -> list[BoletimEvento]:
    driver = _criar_driver(headless=headless)
    boletins: list[BoletimEvento] = []

    try:
        logger.info("Acessando %s", URL_BOLETINS)
        driver.get(URL_BOLETINS)

        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "article")))
        time.sleep(1)

        artigos = driver.find_elements(By.TAG_NAME, "article")
        logger.info("Encontrados %d elementos <article> na página", len(artigos))

        for artigo in artigos[:max_boletins]:
            try:
                link_el = artigo.find_element(By.CSS_SELECTOR, "h2 a, h3 a")
                titulo = link_el.text.strip()
                url = link_el.get_attribute("href")

                try:
                    data_texto = artigo.find_element(
                        By.CSS_SELECTOR, "time, .elementor-post-date, .post-date"
                    ).text.strip()
                except Exception:
                    data_texto = ""

                try:
                    resumo = artigo.find_element(
                        By.CSS_SELECTOR, "p, .elementor-post__excerpt"
                    ).text.strip()
                except Exception:
                    resumo = ""

                if not titulo or not url:
                    continue

                boletins.append(
                    BoletimEvento(titulo=titulo, data_texto=data_texto, url=url, resumo=resumo)
                )
            except Exception as e:
                logger.warning("Falha ao extrair um boletim: %s", e)
                continue

    except TimeoutException:
        logger.error("Timeout esperando a página carregar. O layout do site pode ter mudado.")
    finally:
        driver.quit()

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
