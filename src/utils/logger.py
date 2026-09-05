import os
import sys
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.paths import get_log_file_path, get_base_dir

_IS_INITIALIZED = False

# Tenta reconfigurar stdout/stderr no Windows para UTF-8 seguro
for s in [sys.stdout, sys.stderr]:
    if s is not None and hasattr(s, "reconfigure"):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

class _SafeConsoleHandler(logging.Handler):
    """Handler de console seguro que nunca falha com UnicodeEncodeError no Windows."""
    def __init__(self, stream):
        super().__init__()
        self.stream = stream

    def emit(self, record):
        try:
            msg = self.format(record)
            if self.stream and hasattr(self.stream, "write"):
                try:
                    self.stream.write(msg + "\n")
                    self.stream.flush()
                except UnicodeEncodeError:
                    enc = getattr(self.stream, "encoding", "ascii") or "ascii"
                    safe_msg = msg.encode(enc, errors="replace").decode(enc)
                    self.stream.write(safe_msg + "\n")
                    self.stream.flush()
        except Exception:
            self.handleError(record)

def setup_logging() -> Path:
    """
    Inicializa a gravação automática no arquivo Log.txt na pasta onde o .exe está instalado.
    Registra inicialização, sucessos, avisos e qualquer erro com traceback detalhado.
    """
    global _IS_INITIALIZED
    log_file = get_log_file_path()

    if _IS_INITIALIZED:
        return log_file

    session_header = (
        f"\n" + "=" * 80 + "\n"
        f"CATALOGADOR DE MENSAGENS DO TELEGRAM — LOG DE EXECUÇÃO\n"
        f"Início da Sessão: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"Arquivo de Log: {log_file}\n"
        f"Diretório do Executável: {get_base_dir()}\n"
        f"Sistema: {sys.platform} | Python: {sys.version.split()[0]}\n"
        f"=" * 80 + "\n"
    )

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(session_header)
            f.flush()
    except Exception:
        pass

    # Configuração do Logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File Handler dedicado gravando em UTF-8 direto no Log.txt
    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console Handler seguro (se houver console anexado)
    if sys.stdout is not None:
        console_handler = _SafeConsoleHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Captura erros não tratados na thread principal
    def _uncaught_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical(
            "ERRO CRÍTICO NÃO TRATADO (Thread Principal):",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = _uncaught_exception

    # Captura erros não tratados em threads secundárias (ex: Telethon worker thread)
    def _thread_exception(args):
        logging.critical(
            f"ERRO CRÍTICO NA THREAD '{args.thread.name}':",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
        )

    threading.excepthook = _thread_exception

    logging.info("Aplicativo inicializado e gravando logs em Log.txt.")
    _IS_INITIALIZED = True
    return log_file

def log_event(message: str, level: str = "INFO", exc: Optional[Exception] = None):
    """Grava mensagem no Log.txt com nível especificado (INFO, SUCESSO, ERRO, AVISO)."""
    setup_logging()
    clean_level = level.upper().strip()

    if clean_level in ["ERRO", "ERROR"]:
        if exc:
            logging.error(f"{message} | Exceção: {exc}", exc_info=True)
        else:
            logging.error(message)
    elif clean_level in ["SUCESSO", "SUCCESS"]:
        logging.info(f"[SUCESSO] {message}")
    elif clean_level in ["AVISO", "WARNING"]:
        logging.warning(message)
    else:
        logging.info(message)
