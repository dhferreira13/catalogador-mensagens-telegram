import os
import sys
import subprocess
from pathlib import Path

def build():
    base_dir = Path(__file__).resolve().parent
    venv_python = base_dir / "venv" / "Scripts" / "python.exe"
    venv_pyinstaller = base_dir / "venv" / "Scripts" / "pyinstaller.exe"

    if not venv_pyinstaller.exists():
        print(f"Erro: PyInstaller não encontrado em {venv_pyinstaller}")
        sys.exit(1)

    # Fecha instâncias abertas do executável para evitar erro de arquivo travado no Windows
    if sys.platform == "win32":
        for proc in ["Catalogador_Telegram_TCC.exe", "Catalogador de Mensagens do Telegram.exe"]:
            try:
                subprocess.run(["taskkill", "/F", "/IM", proc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    print("=== Iniciando compilação do executável (.exe) com PyInstaller ===")
    
    icon_path = base_dir / "assets" / "app_icon.ico"

    cmd = [
        str(venv_pyinstaller),
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "Catalogador de Mensagens do Telegram",
        "--icon", str(icon_path),
        "--collect-all", "customtkinter",
        "--collect-all", "telethon",
        "--hidden-import", "openpyxl",
        "--hidden-import", "pandas",
        "--hidden-import", "sqlalchemy",
        "--hidden-import", "sqlite3",
        "--add-data", f"{base_dir / 'src'}{os.pathsep}src",
        "--add-data", f"{base_dir / 'assets'}{os.pathsep}assets",
        str(base_dir / "main.py")
    ]

    print(f"Executando comando: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(base_dir))
    
    if result.returncode == 0:
        exe_path = base_dir / "dist" / "Catalogador de Mensagens do Telegram.exe"
        print(f"\n[SUCESSO] Executável gerado com sucesso!")
        print(f"Localização do executável: {exe_path}")
    else:
        print(f"\n[ERRO] Falha na compilação do executável (Código: {result.returncode})")
        sys.exit(result.returncode)

if __name__ == "__main__":
    build()
