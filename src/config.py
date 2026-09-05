import os
import json
from pathlib import Path
from dotenv import load_dotenv
from src.utils.paths import get_base_dir, get_data_dir, get_output_dir, get_medias_dir, get_sheets_dir

BASE_DIR = get_base_dir()
DATA_DIR = get_data_dir()
OUTPUT_DIR = get_output_dir()
MEDIAS_DIR = get_medias_dir()
SHEETS_DIR = get_sheets_dir()

# Arquivos de persistência de credenciais e sessão
ENV_FILE = BASE_DIR / ".env"
CONFIG_FILE = DATA_DIR / "app_config.json"

# Tenta carregar do .env se existir
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

def load_saved_credentials() -> dict:
    """Carrega credenciais salvas de CONFIG_FILE ou .env."""
    creds = {
        "api_id": os.getenv("TELEGRAM_API_ID", ""),
        "api_hash": os.getenv("TELEGRAM_API_HASH", ""),
        "phone": os.getenv("TELEGRAM_PHONE", "")
    }

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if saved.get("api_id"):
                    creds["api_id"] = str(saved["api_id"])
                if saved.get("api_hash"):
                    creds["api_hash"] = str(saved["api_hash"])
                if saved.get("phone"):
                    creds["phone"] = str(saved["phone"])
        except Exception:
            pass

    return creds

def save_user_credentials(api_id: str, api_hash: str, phone: str):
    """Persiste as credenciais em app_config.json de forma segura."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "api_id": api_id.strip(),
            "api_hash": api_hash.strip(),
            "phone": phone.strip()
        }, f, indent=2)

# Sessão e Banco de Dados
TELEGRAM_SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "telegram_tcc_session")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'telegram_tcc.db'}")

# Janelas padrão de pesquisa de TCC (Fuso Brasília UTC-3)
DEFAULT_START_DATE = "2026-09-14 00:00:00"
DEFAULT_END_DATE = "2026-09-27 23:59:59"
SEMANA_1_START = "2026-09-14 00:00:00"
SEMANA_1_END = "2026-09-20 23:59:59"
SEMANA_2_START = "2026-09-21 00:00:00"
SEMANA_2_END = "2026-09-27 23:59:59"
