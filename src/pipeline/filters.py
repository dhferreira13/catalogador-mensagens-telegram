from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from src.config import (
    SEMANA_1_START, SEMANA_1_END,
    SEMANA_2_START, SEMANA_2_END
)

BRT = timezone(timedelta(hours=-3))

def parse_date_to_brt(dt: datetime) -> datetime:
    """Converte datetime para o fuso de Brasília (UTC-3)."""
    if dt.tzinfo is None:
        # Se for ingênuo, assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BRT).replace(tzinfo=None)

def classify_week(dt_brt: datetime) -> Optional[str]:
    """
    Retorna o rótulo da semana em que a mensagem se encaixa:
    - 'Semana 1 (14 a 20 set)'
    - 'Semana 2 (21 a 27 set)'
    - None (fora do período da pesquisa)
    """
    s1_start = datetime.strptime(SEMANA_1_START, "%Y-%m-%d %H:%M:%S")
    s1_end = datetime.strptime(SEMANA_1_END, "%Y-%m-%d %H:%M:%S")
    s2_start = datetime.strptime(SEMANA_2_START, "%Y-%m-%d %H:%M:%S")
    s2_end = datetime.strptime(SEMANA_2_END, "%Y-%m-%d %H:%M:%S")

    if s1_start <= dt_brt <= s1_end:
        return "Semana 1 (14 a 20 set)"
    elif s2_start <= dt_brt <= s2_end:
        return "Semana 2 (21 a 27 set)"
    return None
