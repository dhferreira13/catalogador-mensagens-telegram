"""
Coletor Contínuo em Tempo Real (Live Stream) do Telegram para TCC.
Captura mensagens e mídias instantaneamente no momento da postagem,
mantém sincronização contínua com recuperação de lacunas (Gap Recovery),
exibe card com ícone na barra de tarefas e bandeja do sistema (System Tray),
e fecha a planilha Excel (.xlsx) automaticamente na virada do dia (23:59:59 BRT).
"""

import os
import sys
import json
import time
import asyncio
import threading
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Fuso horário de Brasília (BRT UTC-3)
BRT = timezone(timedelta(hours=-3))

def parse_args():
    parser = argparse.ArgumentParser(description="Coletor em Tempo Real do Telegram para TCC")
    parser.add_argument("--target", type=str, default=None, help="ID, link ou username do grupo ou canal alvo")
    parser.add_argument("--no-media", action="store_true", help="Desabilitar download de mídias")
    parser.add_argument("--headless", action="store_true", help="Executar sem janela gráfica")
    parser.add_argument("--base-dir", type=str, default=None, help="Diretório base do app (padrão: dist se existir)")
    return parser.parse_args()

class LiveStreamUI:
    """Card moderno flutuante e integração com a bandeja do sistema (System Tray)."""
    def __init__(self, target_chat: str, icon_path: Path, on_manual_export, on_exit_request):
        import customtkinter as ctk
        from PIL import Image

        self.target_chat = target_chat
        self.icon_path = icon_path
        self.on_manual_export = on_manual_export
        self.on_exit_request = on_exit_request
        self.tray_icon = None

        # Configura o AppUserModelID para o Windows exibir o ícone correto na Barra de Tarefas
        try:
            import ctypes
            myappid = "dhferreira13.catalogadortelegram.stream"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Catalogador Telegram — Tempo Real")
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        # Posiciona no canto inferior direito
        w, h = 440, 290
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - w - 24
        y = screen_h - h - 68
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # Card Frame
        card = ctk.CTkFrame(self.root, corner_radius=14, fg_color="#0F172A", border_width=1, border_color="#334155")
        card.pack(fill="both", expand=True, padx=8, pady=8)

        # Cabeçalho
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=14, pady=(10, 4))

        self.lbl_status_badge = ctk.CTkLabel(
            header_frame,
            text="🟢 AO VIVO",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#22C55E"
        )
        self.lbl_status_badge.pack(side="left")

        self.lbl_title = ctk.CTkLabel(
            header_frame,
            text="Coleta Instantânea Ativa",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#F8FAFC"
        )
        self.lbl_title.pack(side="left", padx=(8, 0))

        # Subtítulo (Canal e Fechamento)
        self.lbl_sub = ctk.CTkLabel(
            card,
            text=f"Grupo: {target_chat} | Fechamento automático às 23:59:59",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#94A3B8"
        )
        self.lbl_sub.pack(anchor="w", padx=14, pady=(0, 6))

        # Contadores Box
        counters_frame = ctk.CTkFrame(card, corner_radius=10, fg_color="#1E293B", border_width=1, border_color="#334155")
        counters_frame.pack(fill="x", padx=14, pady=(0, 8))

        self.lbl_msgs_counter = ctk.CTkLabel(
            counters_frame,
            text="Mensagens Hoje: 0",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#38BDF8"
        )
        self.lbl_msgs_counter.pack(side="left", padx=14, pady=8)

        self.lbl_media_counter = ctk.CTkLabel(
            counters_frame,
            text="Mídias Hoje: 0",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#A855F7"
        )
        self.lbl_media_counter.pack(side="right", padx=14, pady=8)

        # Última mensagem recebida
        self.lbl_latest_label = ctk.CTkLabel(
            card,
            text="Última mensagem recebida:",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#64748B"
        )
        self.lbl_latest_label.pack(anchor="w", padx=14, pady=(0, 2))

        self.lbl_latest_box = ctk.CTkLabel(
            card,
            text="Aguardando primeira postagem no grupo...",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#E2E8F0",
            anchor="w",
            justify="left"
        )
        self.lbl_latest_box.pack(fill="x", padx=14, pady=(0, 10))

        # Botões de Ação
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=14, pady=(0, 8))

        self.btn_export = ctk.CTkButton(
            btn_frame,
            text="📊 Gerar Planilha Agora",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#0284C7",
            hover_color="#0369A1",
            height=28,
            command=self.on_manual_export
        )
        self.btn_export.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_tray = ctk.CTkButton(
            btn_frame,
            text="Minimizar na Bandeja",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#334155",
            hover_color="#475569",
            height=28,
            command=self.minimize_to_tray
        )
        self.btn_tray.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Protocolo de fechar janela
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # Inicia System Tray em thread separada
        self._setup_tray()

    def _setup_tray(self):
        try:
            import pystray
            from PIL import Image

            if self.icon_path.exists():
                img = Image.open(str(self.icon_path))
            else:
                img = Image.new("RGB", (64, 64), color=(34, 197, 94))

            def on_restore(icon, item):
                self.restore_from_tray()

            def on_export(icon, item):
                self.on_manual_export()

            def on_open_medias(icon, item):
                from src.utils.paths import get_medias_dir
                os.startfile(str(get_medias_dir()))

            def on_open_sheets(icon, item):
                from src.utils.paths import get_sheets_dir
                os.startfile(str(get_sheets_dir()))

            def on_quit(icon, item):
                self.on_exit_request()

            menu = pystray.Menu(
                pystray.MenuItem("📊 Abrir Painel de Status", on_restore, default=True),
                pystray.MenuItem("📑 Gerar Planilha do Dia Agora", on_export),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("📁 Abrir Pasta de Mídias", on_open_medias),
                pystray.MenuItem("📁 Abrir Pasta de Planilhas", on_open_sheets),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("❌ Encerrar Coleta", on_quit)
            )

            self.tray_icon = pystray.Icon("TelegramLiveStream", img, "Catalogador Telegram — Ao Vivo", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception:
            self.tray_icon = None

    def minimize_to_tray(self):
        self.root.withdraw()
        if self.tray_icon:
            try:
                self.tray_icon.notify("Coleta continuando em segundo plano.", "Catalogador Telegram")
            except Exception:
                pass

    def restore_from_tray(self):
        self.root.after(0, self._do_restore)

    def _do_restore(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.focus_force()

    def update_message(self, info: dict):
        """Atualiza contadores e caixa de última mensagem na interface gráfica."""
        msgs = info.get("today_messages", 0)
        media = info.get("today_media", 0)
        sender = info.get("sender_anon", "User")
        m_type = info.get("media_type", "")
        preview = info.get("text_preview", "")
        time_str = info.get("date_brt", datetime.now(BRT)).strftime("%H:%M:%S")

        self.lbl_msgs_counter.configure(text=f"Mensagens Hoje: {msgs}")
        self.lbl_media_counter.configure(text=f"Mídias Hoje: {media}")

        m_tag = f"[{m_type}] " if m_type and m_type != "Nenhuma" else ""
        text_disp = f"[{time_str}] {sender}: {m_tag}{preview}"
        if len(text_disp) > 52:
            text_disp = text_disp[:50] + "..."

        self.lbl_latest_box.configure(text=text_disp)

        if self.tray_icon:
            self.tray_icon.title = f"Catalogador Telegram: {msgs} msgs | {media} mídias hoje"

    def show_export_alert(self, excel_path: str):
        file_name = Path(excel_path).name
        self.lbl_latest_box.configure(text=f"✅ Planilha gerada: {file_name[:40]}...")
        if self.tray_icon:
            try:
                self.tray_icon.notify(f"Planilha gerada com sucesso: {file_name}", "Catalogador Telegram")
            except Exception:
                pass

    def close(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()

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

    log_file_path = base_dir / "Log_TempoReal.txt"
    def log(msg: str):
        ts = datetime.now(BRT).strftime("%d/%m/%Y %H:%M:%S")
        formatted = f"[{ts}] {msg}"
        print(formatted, flush=True)
        try:
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception:
            pass

    config_file = base_dir / "data" / "app_config.json"
    session_file = base_dir / "data" / "telegram_tcc_session"

    if not config_file.exists():
        log(f"ERRO: Arquivo de configuração não encontrado: {config_file}")
        sys.exit(1)

    with open(config_file, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    target_chat = args.target
    if not target_chat:
        target_chat = config_data.get("last_target")
    if not target_chat:
        log("ERRO: Alvo de coleta (--target) não informado. Especifique o @username, link ou ID do grupo/canal.")
        sys.exit(1)

    log("=" * 60)
    log(f"Iniciando Coletor em Tempo Real (Live Stream) para o alvo: {target_chat}")

    api_id = int(config_data.get("api_id", 0))
    api_hash = config_data.get("api_hash", "")

    if not api_id or not api_hash:
        log("ERRO: api_id ou api_hash ausentes em app_config.json")
        sys.exit(1)

    from telethon import TelegramClient
    from src.collectors.telegram_stream import TelegramStreamCollector

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(str(session_file), api_id, api_hash)

    collector = None
    ui = None

    def on_new_msg(info: dict):
        if ui:
            ui.root.after(0, lambda: ui.update_message(info))

    def on_export(excel_path: str):
        if ui:
            ui.root.after(0, lambda: ui.show_export_alert(excel_path))

    collector = TelegramStreamCollector(
        client=client,
        target_chat=target_chat,
        on_message_callback=on_new_msg,
        on_export_callback=on_export,
        log_callback=log,
        download_media=not args.no_media
    )

    def manual_export_action():
        if collector:
            res = collector.trigger_manual_export()
            if res and ui:
                ui.root.after(0, lambda: ui.show_export_alert(res))

    def exit_action():
        log("Solicitação de encerramento pelo usuário.")
        if collector:
            collector.stop()
        if ui:
            ui.close()

    def stream_worker():
        try:
            log("Conectando ao Telegram...")
            loop.run_until_complete(client.connect())
            if not loop.run_until_complete(client.is_user_authorized()):
                log("ERRO: Sessão do Telegram não autorizada. Abra o app principal para logar.")
                if ui:
                    ui.close()
                return

            log("Sessão autenticada. Iniciando listener contínuo de eventos...")
            loop.run_until_complete(collector.start())
        except Exception as e:
            log(f"ERRO no stream do Telegram: {e}")
        finally:
            try:
                if client.is_connected():
                    loop.run_until_complete(client.disconnect())
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

    threading.Thread(target=stream_worker, daemon=True).start()

    if args.headless:
        # Modo estritamente linha de comando / sem interface
        try:
            while collector.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            exit_action()
        return

    # Modo interativo com card e system tray
    icon_path = project_root / "assets" / "app_icon.ico"
    ui = LiveStreamUI(target_chat, icon_path, manual_export_action, exit_action)
    ui.run()

if __name__ == "__main__":
    main()
