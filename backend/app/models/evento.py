"""
Schema do Evento Climático Extremo.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TipoEvento(str, Enum):
    CHUVA_INTENSA = "chuva_intensa"
    VENTO_FORTE = "vento_forte"
    TORNADO = "tornado"
    GRANIZO = "granizo"
    ALAGAMENTO = "alagamento"
    DESLIZAMENTO = "deslizamento"
    OUTRO = "outro"


class Severidade(str, Enum):
    BAIXA = "baixa"
    MODERADA = "moderada"
    ALTA = "alta"
    EXTREMA = "extrema"


class Evento(BaseModel):
    id: str = Field(..., description="Identificador único do evento")
    fonte: str = Field(..., description="Fonte de origem: COR-Rio, INMET, Defesa Civil")
    tipo: TipoEvento
    severidade: Severidade
    municipio: str
    estado: str = Field(..., description="RJ ou SP")
    latitude: float
    longitude: float
    data_ocorrencia: datetime
    descricao: str = Field(..., description="Descrição textual do evento, se disponível")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cemaden-2026-07-28-001",
                "fonte": "COR-Rio",
                "tipo": "vento_forte",
                "severidade": "alta",
                "municipio": "Rio de Janeiro",
                "estado": "RJ",
                "latitude": -22.9068,
                "longitude": -43.1729,
                "data_ocorrencia": "2026-07-28T14:30:00",
                "descricao": "Rajadas de vento de até 100 km/h associadas a frente fria",
            }
        }
