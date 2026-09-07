import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

def get_base_dir() -> Path:
    """
    Retorna o diretório base da aplicação.
    Quando empacotado pelo PyInstaller (sys.frozen), retorna a pasta onde o .exe está localizado.
    Em ambiente de desenvolvimento, retorna a pasta raiz do repositório.
    """
    if getattr(sys, "frozen", False):
        # Executável compilado (.exe)
        return Path(sys.executable).resolve().parent
    else:
        # Script em execução no ambiente de desenvolvimento
        return Path(__file__).resolve().parent.parent.parent

def get_output_dir() -> Path:
    """
    Retorna o diretório 'output' ao lado do executável ou na raiz do projeto.
    Garante a existência das subpastas 'Mídias' e 'Planilhas de Catalogação'.
    """
    base_dir = get_base_dir()
    output_dir = base_dir / "output"
    medias_dir = output_dir / "Mídias"
    sheets_dir = output_dir / "Planilhas de Catalogação"

    for d in [output_dir, medias_dir, sheets_dir]:
        d.mkdir(parents=True, exist_ok=True)

    return output_dir

def get_medias_dir() -> Path:
    """Retorna a pasta output/Mídias."""
    get_output_dir()
    return get_base_dir() / "output" / "Mídias"

def get_media_subfolder_name(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> str:
    """
    Retorna o nome padronizado da subpasta de mídias conforme o período solicitado.
    Substitui barras '/' por hífens '-' para garantir compatibilidade com o sistema de arquivos do Windows.
    Exemplos:
        - Coleta diária (ex: 02/09/2026 a 02/09/2026): 'Mídias 02-09'
        - Coleta entre dias no mesmo ano (ex: 02/09/2026 a 05/09/2026): 'Mídias 02-09 a 05-09'
        - Coleta entre anos distintos: 'Mídias 02-09-2025 a 05-09-2026'
    """
    if not start_dt or not end_dt:
        return "Mídias Gerais"

    if start_dt.date() == end_dt.date():
        return f"Mídias {start_dt.strftime('%d-%m')}"
    elif start_dt.year == end_dt.year:
        return f"Mídias {start_dt.strftime('%d-%m')} a {end_dt.strftime('%d-%m')}"
    else:
        return f"Mídias {start_dt.strftime('%d-%m-%Y')} a {end_dt.strftime('%d-%m-%Y')}"

def get_media_subfolder(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> Path:
    """
    Retorna o caminho da subpasta dentro de output/Mídias correspondente ao período de coleta.
    Garante a criação automática da pasta no disco.
    """
    medias_dir = get_medias_dir()
    subfolder_name = get_media_subfolder_name(start_dt, end_dt)
    target_dir = medias_dir / subfolder_name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir

def get_sheets_dir() -> Path:
    """Retorna a pasta output/Planilhas de Catalogação."""
    get_output_dir()
    return get_base_dir() / "output" / "Planilhas de Catalogação"

def get_data_dir() -> Path:
    """
    Retorna o diretório de dados internos (banco SQLite e sessões do Telegram).
    """
    base_dir = get_base_dir()
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_logs_dir() -> Path:
    """
    Retorna o diretório 'logs' ao lado do executável ou na raiz do projeto.
    """
    base_dir = get_base_dir()
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir

def get_log_file_path() -> Path:
    """
    Retorna o caminho do arquivo 'Log.txt' exatamente na pasta onde o .exe está instalado.
    """
    return get_base_dir() / "Log.txt"

def get_resource_path(relative_path: str) -> Path:
    """
    Retorna o caminho de um recurso interno (bundled no PyInstaller via sys._MEIPASS ou relativo na raiz).
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / relative_path
    return Path(__file__).resolve().parent.parent.parent / relative_path

def get_app_icon_path() -> Path:
    """Retorna o caminho do arquivo de ícone app_icon.ico."""
    return get_resource_path("assets/app_icon.ico")
