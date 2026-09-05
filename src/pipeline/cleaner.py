import re
import hashlib
from typing import Optional

URL_PATTERN = re.compile(
    r'(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
    r'www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|'
    r'https?:\/\/[a-zA-Z0-9]+\.[^\s]{2,}|'
    r't\.me\/[a-zA-Z0-9_+\/]+)'
)

_ANON_SALT = "tcc_netnografia_telegram_2026"

def anonymize_user(user_id: Optional[object] = None, name: Optional[str] = None) -> tuple[str, str]:
    """Gera um ID e pseudônimo anônimo determinístico para o usuário."""
    if not user_id:
        return "User_Anon", "Participante Anônimo"
    
    raw = f"{_ANON_SALT}_{user_id}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:6].upper()
    anon_id = f"User_{digest}"
    return anon_id, anon_id

def extract_urls(text: Optional[str]) -> list[str]:
    """Extrai URLs contidas no texto."""
    if not text:
        return []
    return URL_PATTERN.findall(text)

def clean_text_for_nlp(text: Optional[str]) -> str:
    """Remove links, espaços excessivos e caracteres de controle para análise de conteúdo."""
    if not text:
        return ""
    # Remove URLs
    cleaned = URL_PATTERN.sub("", text)
    # Remove múltiplos espaços e quebras repetidas
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned
