"""
Coletor Diário Automatizado do Telegram para TCC.
Executa a coleta das mensagens, baixa mídias em subpastas organizadas por data,
exibe um mini-card moderno com ícone na Barra de Tarefas do Windows durante a execução,
e gera a planilha Excel (.xlsx) na pasta output/Planilhas de Catalogação.
"""

import os
import sys
import json
import time
import asyncio
import threading
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Fuso horário de Brasília (BRT UTC-3)
BRT = timezone(timedelta(hours=-3))

def parse_args():
    parser = argparse.ArgumentParser(description="Coletor Diário Automatizado do Telegram para TCC")
    parser.add_argument("--date", type=str, default=None, help="Data alvo no formato YYYY-MM-DD (padrão: ontem)")
    parser.add_argument("--start-time", type=str, default=None, help="Horário inicial no formato HH:MM:SS (padrão: 00:00:00)")
    parser.add_argument("--end-time", type=str, default=None, help="Horário final no formato HH:MM:SS (padrão: 23:59:59)")
    parser.add_argument("--target", type=str, default="-1301887300", help="ID ou username do grupo (padrão: -1301887300)")
    parser.add_argument("--limit", type=int, default=None, help="Limite máximo de mensagens para coletar (para testes rápidos)")
    parser.add_argument("--no-media", action="store_true", help="Desabilitar download de mídias")
    parser.add_argument("--headless", action="store_true", help="Executar sem mini-janela gráfica")
    parser.add_argument("--base-dir", type=str, default=None, help="Diretório base do app (padrão: dist se existir)")
    return parser.parse_args()

def get_target_interval(date_str: str = None, start_time_str: str = None, end_time_str: str = None) -> tuple[datetime, datetime]:
    if date_str:
        target_day = datetime.strptime(date_str, "%Y-%m-%d").date()
    else:
        now_brt = datetime.now(BRT)
        target_day = (now_brt - timedelta(days=1)).date()

    t_start = datetime.strptime(start_time_str, "%H:%M:%S").time() if start_time_str else datetime.min.time()
    t_end = datetime.strptime(end_time_str, "%H:%M:%S").time() if end_time_str else datetime.max.time().replace(microsecond=0)

    start_dt = datetime.combine(target_day, t_start)
    end_dt = datetime.combine(target_day, t_end)
    return start_dt, end_dt

def run_collection_logic(base_dir: Path, target: str, start_dt: datetime, end_dt: datetime, download_media: bool, limit: int = None, update_cb=None, log_fn=print):
    from telethon import TelegramClient
    from src.collectors.telegram_collector import collect_messages
    from src.exporter.excel_exporter import export_to_tcc_spreadsheet

    config_file = base_dir / "data" / "app_config.json"
    session_file = base_dir / "data" / "telegram_tcc_session"

    if not config_file.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_file}")

    with open(config_file, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    api_id = int(config_data.get("api_id", 0))
    api_hash = config_data.get("api_hash", "")

    if not api_id or not api_hash:
        raise ValueError("api_id ou api_hash ausentes em app_config.json")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(str(session_file), api_id, api_hash)

    try:
        log_fn("Conectando ao Telegram...")
        loop.run_until_complete(client.connect())

        if not loop.run_until_complete(client.is_user_authorized()):
            raise PermissionError("Sessão do Telegram não autorizada. Abra o aplicativo gráfico para conectar.")

        log_fn("Sessão autenticada com sucesso no Telegram.")

        cancel_event = None
        if limit:
            cancel_event = asyncio.Event()

        def progress_cb(scanned, saved, media, dt, status):
            if update_cb:
                update_cb(scanned, saved, media, status)
            if status and (scanned % 10 == 0 or "Baixando" in status):
                log_fn(f"[Progresso] {status} ({saved} salvas, {media} mídias)")
            if limit and saved >= limit and cancel_event and not cancel_event.is_set():
                log_fn(f"Limite de {limit} mensagens atingido para teste rápido.")
                cancel_event.set()

        log_fn("Iniciando varredura das mensagens...")
        result = loop.run_until_complete(
            collect_messages(
                client=client,
                target_chat=target,
                start_dt_brt=start_dt,
                end_dt_brt=end_dt,
                download_media_files=download_media,
                progress_callback=progress_cb,
                cancel_event=cancel_event
            )
        )

        chat_id = result.get("chat_id")
        chat_title = result.get("chat_title", target)
        scanned = result.get("scanned_count", 0)
        saved = result.get("saved_count", 0)
        media_count = result.get("media_count", 0)
        media_folder = result.get("media_folder_name", "")

        log_fn(f"Varredura concluída: {scanned} analisadas, {saved} salvas, {media_count} mídias.")
        if media_folder:
            log_fn(f"Mídias salvas em: {base_dir / 'output' / 'Mídias' / media_folder}")

        # Exporta para planilha Excel
        log_fn("Gerando planilha Excel (.xlsx)...")
        excel_path = export_to_tcc_spreadsheet(
            chat_id=chat_id,
            chat_title=chat_title,
            start_dt=start_dt,
            end_dt=end_dt
        )
        log_fn(f"Planilha gerada com sucesso: {excel_path}")

        return {
            "saved": saved,
            "media_count": media_count,
            "media_folder": media_folder,
            "excel_path": excel_path
        }
    finally:
        try:
            if client.is_connected():
                loop.run_until_complete(client.disconnect())
        except Exception:
            pass
        try:
            if hasattr(client, "session") and hasattr(client.session, "close"):
                client.session.close()
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass

class MiniProgressWindow:
    """Mini card flutuante que posiciona o ícone oficial na Barra de Tarefas do Windows."""
    def __init__(self, target_date_str: str, icon_path: Path, on_ready_callback):
        import customtkinter as ctk

        # Configura o App ID para o Windows exibir o ícone correto na Barra de Tarefas
        try:
            import ctypes
            myappid = "dhferreira13.catalogadortelegram.diario"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Catalogador de Mensagens do Telegram")
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Posiciona no canto inferior direito, logo acima da barra de tarefas
        w, h = 400, 190
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - w - 24
        y = screen_h - h - 68
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # Layout interno do card
        frame = ctk.CTkFrame(self.root, corner_radius=12, fg_color="#1E293B", border_width=1, border_color="#334155")
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Cabeçalho
        lbl_title = ctk.CTkLabel(
            frame,
            text="📱 Coleta Automática em Andamento",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#38BDF8"
        )
        lbl_title.pack(anchor="w", padx=14, pady=(10, 2))

        self.lbl_sub = ctk.CTkLabel(
            frame,
            text=f"📅 Período: {target_date_str}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94A3B8"
        )
        self.lbl_sub.pack(anchor="w", padx=14, pady=(0, 6))

        # Status
        self.lbl_status = ctk.CTkLabel(
            frame,
            text="Iniciando conexão com o Telegram...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#E2E8F0"
        )
        self.lbl_status.pack(anchor="w", padx=14, pady=(0, 6))

        # Barra de progresso indeterminada
        self.prog_bar = ctk.CTkProgressBar(frame, height=6, progress_color="#0284C7")
        self.prog_bar.pack(fill="x", padx=14, pady=(0, 8))
        self.prog_bar.start()

        # Contadores
        self.lbl_counters = ctk.CTkLabel(
            frame,
            text="Mensagens: 0 | Mídias: 0",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#A5F3FC"
        )
        self.lbl_counters.pack(anchor="w", padx=14, pady=(0, 6))

        self.root.after(100, on_ready_callback)

    def update_progress(self, scanned: int, saved: int, media: int, status: str):
        if status:
            # Trunca texto para caber no card
            short_status = status[:48] + "..." if len(status) > 48 else status
            self.lbl_status.configure(text=short_status)
        self.lbl_counters.configure(text=f"Mensagens: {saved} salvas | Mídias: {media} baixadas")

    def show_completed(self, saved: int, media: int, on_close):
        self.prog_bar.stop()
        self.prog_bar.set(1.0)
        self.prog_bar.configure(progress_color="#22C55E")
        self.lbl_status.configure(text="✅ Coleta finalizada com sucesso!", text_color="#4ADE80")
        self.lbl_counters.configure(text=f"Total: {saved} mensagens salvas | {media} mídias baixadas")
        # Fecha automaticamente após 3 segundos
        self.root.after(3000, on_close)

    def show_error(self, err_msg: str, on_close):
        self.prog_bar.stop()
        self.prog_bar.configure(progress_color="#EF4444")
        self.lbl_status.configure(text=f"❌ Erro: {err_msg[:40]}...", text_color="#F87171")
        self.root.after(4000, on_close)

    def run(self):
        self.root.mainloop()

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parent

    if args.base_dir:
        base_dir = Path(args.base_dir).resolve()
    elif (project_root / "dist" / "data" / "telegram_tcc_session.session").exists():
        base_dir = project_root / "dist"
    else:
        base_dir = project_root

    os.environ["APP_BASE_DIR"] = str(base_dir)

    log_file_path = base_dir / "Log_Agendamento.txt"
    def log(msg: str):
        ts = datetime.now(BRT).strftime("%d/%m/%Y %H:%M:%S")
        formatted = f"[{ts}] {msg}"
        print(formatted, flush=True)
        try:
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception:
            pass

    start_dt, end_dt = get_target_interval(args.date, args.start_time, args.end_time)
    date_formatted = start_dt.strftime("%d/%m/%Y")
    interval_formatted = f"{start_dt.strftime('%d/%m/%Y %H:%M')} a {end_dt.strftime('%d/%m/%Y %H:%M')}"

    log("=" * 60)
    log(f"Iniciando Coleta Diária: {interval_formatted}")

    icon_path = project_root / "assets" / "app_icon.ico"

    if args.headless:
        # Modo estritamente linha de comando
        try:
            run_collection_logic(base_dir, args.target, start_dt, end_dt, not args.no_media, limit=args.limit, log_fn=log)
        except Exception as e:
            log(f"ERRO: {e}")
            sys.exit(1)
        return

    # Modo com mini-card e ícone oficial na Barra de Tarefas
    ui = None

    def worker():
        try:
            def on_progress_ui(scanned, saved, media, status):
                if ui:
                    ui.root.after(0, lambda: ui.update_progress(scanned, saved, media, status))

            res = run_collection_logic(
                base_dir=base_dir,
                target=args.target,
                start_dt=start_dt,
                end_dt=end_dt,
                download_media=not args.no_media,
                limit=args.limit,
                update_cb=on_progress_ui,
                log_fn=log
            )
            saved = res.get("saved", 0)
            media = res.get("media_count", 0)
            log("Finalizando processo...")
            if ui:
                ui.root.after(0, lambda: ui.show_completed(saved, media, ui.close))
        except Exception as e:
            log(f"ERRO durante a coleta: {e}")
            if ui:
                ui.root.after(0, lambda: ui.show_error(str(e), ui.close))

    def on_ready():
        threading.Thread(target=worker, daemon=True).start()

    ui = MiniProgressWindow(interval_formatted, icon_path, on_ready)
    ui.run()

if __name__ == "__main__":
    main()
