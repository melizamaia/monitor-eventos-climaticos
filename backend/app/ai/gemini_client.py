"""
Camada de IA — Google Gemini (tier gratuito).
SDK: google-genai (o pacote antigo google-generativeai foi descontinuado).
"""

from __future__ import annotations

import json
import logging
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

MODELO_PADRAO = "gemini-3.5-flash-lite"

# Tier gratuito do gemini-3.5-flash-lite permite 15 requisições/minuto.
# Espaçamos as chamadas em ~4s para não estourar a cota e degradar a
# classificação para os valores de fallback.
_INTERVALO_MINIMO_ENTRE_CHAMADAS = 4.5
_ultima_chamada = 0.0


def _respeitar_limite_de_taxa() -> None:
    global _ultima_chamada
    agora = time.monotonic()
    espera = _INTERVALO_MINIMO_ENTRE_CHAMADAS - (agora - _ultima_chamada)
    if espera > 0:
        time.sleep(espera)
    _ultima_chamada = time.monotonic()

TIPOS_EVENTO_VALIDOS = [
    "chuva_intensa", "vento_forte", "tornado", "granizo",
    "alagamento", "deslizamento", "outro",
]

CAUSAS_PROVAVEIS = [
    "frente_fria", "el_nino", "la_nina",
    "zona_de_convergencia", "temporal_isolado", "nao_identificada",
]


def _criar_cliente() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não definida. Crie uma chave gratuita em "
            "https://aistudio.google.com/apikey e exporte como variável de ambiente."
        )
    return genai.Client(api_key=api_key)


def gerar_resumo_semanal(boletins: list[dict]) -> str:
    if not boletins:
        return "Nenhum evento climático extremo foi registrado no período analisado."

    cliente = _criar_cliente()

    eventos_texto = "\n".join(
        f"- [{b.get('data_texto', 'data não informada')}] {b['titulo']}: {b.get('resumo', '')}"
        for b in boletins
    )

    prompt = f"""Você é um analista de dados climáticos. Com base nos boletins abaixo,
escreva um resumo curto (máximo 4 frases), em português, em tom informativo e neutro,
sobre os eventos climáticos extremos ocorridos no Rio de Janeiro/São Paulo no período.

Não invente dados que não estejam nos boletins. Se não houver informação suficiente
sobre causa meteorológica, não afirme uma causa.

Boletins:
{eventos_texto}

Resumo:"""

    try:
        _respeitar_limite_de_taxa()
        resposta = cliente.models.generate_content(model=MODELO_PADRAO, contents=prompt)
        return resposta.text.strip()
    except Exception as e:
        logger.error("Erro ao gerar resumo com Gemini: %s", e)
        return "Não foi possível gerar o resumo automático no momento."


def classificar_evento(titulo: str, resumo: str) -> dict:
    cliente = _criar_cliente()

    prompt = f"""Classifique o evento climático abaixo.

Título: {titulo}
Descrição: {resumo}

Responda APENAS em JSON, no formato:
{{"tipo": "...", "causa_provavel": "..."}}

Onde "tipo" deve ser um destes valores: {TIPOS_EVENTO_VALIDOS}
E "causa_provavel" deve ser um destes valores: {CAUSAS_PROVAVEIS}

Use "nao_identificada" para causa_provavel se o texto não permitir inferir a causa
com segurança. Não invente informação que não esteja no texto."""

    try:
        _respeitar_limite_de_taxa()
        resposta = cliente.models.generate_content(
            model=MODELO_PADRAO,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        dados = json.loads(resposta.text)

        tipo = dados.get("tipo", "outro")
        causa = dados.get("causa_provavel", "nao_identificada")

        if tipo not in TIPOS_EVENTO_VALIDOS:
            tipo = "outro"
        if causa not in CAUSAS_PROVAVEIS:
            causa = "nao_identificada"

        return {"tipo": tipo, "causa_provavel": causa}
    except Exception as e:
        logger.error("Erro ao classificar evento com Gemini: %s", e)
        return {"tipo": "outro", "causa_provavel": "nao_identificada"}


def extrair_localizacao(titulo: str, resumo: str) -> dict:
    cliente = _criar_cliente()

    prompt = f"""Leia o boletim abaixo, emitido pelo COR-Rio (Centro de Operações e
Resiliência da cidade do Rio de Janeiro).

Título: {titulo}
Descrição: {resumo}

Extraia o município e o estado (UF) mencionados no texto.

Responda APENAS em JSON, no formato:
{{"municipio": "...", "estado": "..."}}

Regras:
- Se o texto mencionar um bairro, zona (ex: "Zona Oeste", "Zona Sul") ou região da
  cidade do Rio de Janeiro, o município é "Rio de Janeiro" e o estado é "RJ".
- Se o texto não mencionar nenhuma cidade específica, responda
  {{"municipio": "Rio de Janeiro", "estado": "RJ"}}, pois a fonte é focada na
  cidade do Rio de Janeiro.
- Nunca invente uma cidade que não esteja implícita no texto."""

    try:
        _respeitar_limite_de_taxa()
        resposta = cliente.models.generate_content(
            model=MODELO_PADRAO,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        dados = json.loads(resposta.text)

        municipio = dados.get("municipio") or "Rio de Janeiro"
        estado = dados.get("estado") or "RJ"

        return {"municipio": municipio, "estado": estado}
    except Exception as e:
        logger.error("Erro ao extrair localização com Gemini: %s", e)
        return {"municipio": "Rio de Janeiro", "estado": "RJ"}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    boletins_exemplo = [
        {
            "titulo": "Rajadas de vento de até 100 km/h atingem a cidade",
            "data_texto": "28/07/2026",
            "resumo": "Frente fria provoca ventania forte na Zona Oeste do Rio de Janeiro.",
        },
        {
            "titulo": "Chuva forte causa alagamentos pontuais",
            "data_texto": "27/07/2026",
            "resumo": "Acumulado de 60mm em 3 horas provoca alagamentos na Zona Sul.",
        },
    ]

    print("=== Resumo semanal ===")
    print(gerar_resumo_semanal(boletins_exemplo))

    print("\n=== Classificação ===")
    for b in boletins_exemplo:
        classificacao = classificar_evento(b["titulo"], b["resumo"])
        print(f"{b['titulo']} -> {classificacao}")
