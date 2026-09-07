import os
import sys
import time
import subprocess
import threading
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable

import customtkinter as ctk

from telethon import TelegramClient

from src.utils.paths import get_output_dir, get_medias_dir, get_sheets_dir
from src.utils.session_patch import apply_telethon_sqlite_patch
from src.collectors.telegram_auth import TelegramAuthManager
from src.collectors.telegram_collector import collect_messages
from src.exporter.excel_exporter import export_to_tcc_spreadsheet

apply_telethon_sqlite_patch()

class CollectionScreen(ctk.CTkFrame):
    """
    Tela 2: Configuração do Alvo, Seletores de Data/Hora, Relógio em Tempo Real,
    Monitoramento de Coleta e Acesso à Pasta Output.
    """
    def __init__(self, parent, on_back_callback: Callable[[], None]):
        super().__init__(parent, fg_color="transparent")
        self.on_back_callback = on_back_callback
        self.auth_manager: Optional[TelegramAuthManager] = None
        self.cancel_event: Optional[asyncio.Event] = None
        
        self.is_collecting = False
        self.start_time: Optional[float] = None
        self.timer_after_id: Optional[str] = None

        self._setup_ui()

    def set_auth_manager(self, auth_manager: TelegramAuthManager):
        """Recebe o gerenciador autenticado da Tela 1."""
        self.auth_manager = auth_manager
        self._log("Sessão autenticada e pronta para catalogação.")

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Configurações
        self.grid_rowconfigure(1, weight=1) # Painel de Andamento e Logs

        # =========================================================================
        # CARD SUPERIOR: CONFIGURAÇÕES DA COLETA
        # =========================================================================
        config_card = ctk.CTkFrame(self, corner_radius=12)
        config_card.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")

        # Linha 1: Título e Alvo
        title_lbl = ctk.CTkLabel(
            config_card,
            text="Configurações da Coleta de Mensagens",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        )
        title_lbl.pack(anchor="w", padx=20, pady=(15, 5))

        target_frame = ctk.CTkFrame(config_card, fg_color="transparent")
        target_frame.pack(fill="x", padx=20, pady=(5, 10))

        lbl_target = ctk.CTkLabel(
            target_frame,
            text="ID, Link ou @Username do Grupo/Canal:",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        )
        lbl_target.pack(anchor="w", pady=(0, 3))

        self.entry_target = ctk.CTkEntry(
            target_frame,
            placeholder_text="Ex: @grupo_pesquisa, https://t.me/nomedogrupo ou -100123456789",
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.entry_target.pack(fill="x")

        # Linha 2: Intervalo Temporal (Início e Fim com Horas e Minutos)
        time_frame = ctk.CTkFrame(config_card, fg_color="transparent")
        time_frame.pack(fill="x", padx=20, pady=(0, 10))
        time_frame.grid_columnconfigure(0, weight=1)
        time_frame.grid_columnconfigure(1, weight=1)

        # Início
        start_box = ctk.CTkFrame(time_frame, corner_radius=8)
        start_box.grid(row=0, column=0, padx=(0, 8), sticky="ew")

        lbl_start = ctk.CTkLabel(
            start_box,
            text="📅 Início da Coleta:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        )
        lbl_start.pack(anchor="w", padx=10, pady=(8, 2))

        start_row = ctk.CTkFrame(start_box, fg_color="transparent")
        start_row.pack(fill="x", padx=10, pady=(0, 8))

        self.entry_start_date = ctk.CTkEntry(
            start_row,
            placeholder_text="DD/MM/AAAA",
            width=110,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.entry_start_date.pack(side="left", padx=(0, 5))
        self.entry_start_date.insert(0, "14/09/2026")

        hours_list = [f"{h:02d}" for h in range(24)]
        minutes_list = [f"{m:02d}" for m in range(60)]

        self.opt_start_hour = ctk.CTkOptionMenu(
            start_row,
            values=hours_list,
            width=65,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.opt_start_hour.pack(side="left", padx=2)
        self.opt_start_hour.set("00")

        lbl_colon1 = ctk.CTkLabel(start_row, text=":", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_colon1.pack(side="left", padx=1)

        self.opt_start_min = ctk.CTkOptionMenu(
            start_row,
            values=minutes_list,
            width=65,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.opt_start_min.pack(side="left", padx=2)
        self.opt_start_min.set("00")

        # Fim
        end_box = ctk.CTkFrame(time_frame, corner_radius=8)
        end_box.grid(row=0, column=1, padx=(8, 0), sticky="ew")

        lbl_end = ctk.CTkLabel(
            end_box,
            text="📅 Fim da Coleta:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        )
        lbl_end.pack(anchor="w", padx=10, pady=(8, 2))

        end_row = ctk.CTkFrame(end_box, fg_color="transparent")
        end_row.pack(fill="x", padx=10, pady=(0, 8))

        self.entry_end_date = ctk.CTkEntry(
            end_row,
            placeholder_text="DD/MM/AAAA",
            width=110,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.entry_end_date.pack(side="left", padx=(0, 5))
        self.entry_end_date.insert(0, "27/09/2026")

        self.opt_end_hour = ctk.CTkOptionMenu(
            end_row,
            values=hours_list,
            width=65,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.opt_end_hour.pack(side="left", padx=2)
        self.opt_end_hour.set("23")

        lbl_colon2 = ctk.CTkLabel(end_row, text=":", font=ctk.CTkFont(size=14, weight="bold"))
        lbl_colon2.pack(side="left", padx=1)

        self.opt_end_min = ctk.CTkOptionMenu(
            end_row,
            values=minutes_list,
            width=65,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.opt_end_min.pack(side="left", padx=2)
        self.opt_end_min.set("59")

        # Linha 3: Botões de Ação
        actions_frame = ctk.CTkFrame(config_card, fg_color="transparent")
        actions_frame.pack(fill="x", padx=20, pady=(5, 15))

        self.btn_start = ctk.CTkButton(
            actions_frame,
            text="🚀 Iniciar Coleta",
            height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#16A34A",
            hover_color="#15803D",
            command=self._on_start_stop_clicked
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.btn_open_output = ctk.CTkButton(
            actions_frame,
            text="📂 Abrir Pasta Output",
            height=42,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._open_output_folder
        )
        self.btn_open_output.pack(side="left", fill="x", expand=True, padx=(4, 4))

        self.btn_open_logs = ctk.CTkButton(
            actions_frame,
            text="📄 Abrir Log.txt",
            height=42,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#0D9488",
            hover_color="#0F766E",
            command=self._open_log_file
        )
        self.btn_open_logs.pack(side="left", fill="x", expand=True, padx=(4, 4))

        self.btn_back = ctk.CTkButton(
            actions_frame,
            text="⚙️ Credenciais",
            height=42,
            width=120,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color="#475569",
            hover_color="#334155",
            command=self._on_back_clicked
        )
        self.btn_back.pack(side="right", padx=(8, 0))

        # =========================================================================
        # CARD INFERIOR: PAINEL DE ANDAMENTO, CRONÔMETRO E LOGS
        # =========================================================================
        progress_card = ctk.CTkFrame(self, corner_radius=12)
        progress_card.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")

        # Cabeçalho do Monitoramento + RELÓGIO EM TEMPO REAL
        monitor_header = ctk.CTkFrame(progress_card, fg_color="transparent")
        monitor_header.pack(fill="x", padx=20, pady=(12, 5))

        lbl_mon_title = ctk.CTkLabel(
            monitor_header,
            text="Andamento da Catalogação",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        )
        lbl_mon_title.pack(side="left")

        # RELÓGIO COM CRONÔMETRO
        self.lbl_clock = ctk.CTkLabel(
            monitor_header,
            text="⏱️ Tempo Decorrido: 00:00:00",
            font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
            text_color="#38BDF8"
        )
        self.lbl_clock.pack(side="right")

        # Contadores Rápidos
        counters_frame = ctk.CTkFrame(progress_card, corner_radius=8, fg_color="#1E293B")
        counters_frame.pack(fill="x", padx=20, pady=8)
        counters_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.lbl_cnt_scanned = ctk.CTkLabel(
            counters_frame,
            text="Mensagens Verificadas\n0",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#94A3B8"
        )
        self.lbl_cnt_scanned.grid(row=0, column=0, pady=10)

        self.lbl_cnt_saved = ctk.CTkLabel(
            counters_frame,
            text="Mensagens no Período\n0",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#4ADE80"
        )
        self.lbl_cnt_saved.grid(row=0, column=1, pady=10)

        self.lbl_cnt_media = ctk.CTkLabel(
            counters_frame,
            text="Mídias Baixadas\n0",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#FACC15"
        )
        self.lbl_cnt_media.grid(row=0, column=2, pady=10)

        # Barra de Progresso
        self.prog_bar = ctk.CTkProgressBar(progress_card, mode="indeterminate", height=6)
        self.prog_bar.pack(fill="x", padx=20, pady=(5, 10))
        self.prog_bar.set(0)
        self.prog_bar.stop()

        # Console de Atividade / Logs com rolagem
        self.log_textbox = ctk.CTkTextbox(
            progress_card,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#E2E8F0"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 15))

    def _log(self, message: str):
        """Adiciona mensagem formatada com timestamp ao console e grava no Log.txt."""
        from src.utils.logger import log_event
        log_event(message)
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}\n"
        self.log_textbox.insert("end", entry)
        self.log_textbox.see("end")

    def _open_log_file(self):
        """Abre o arquivo Log.txt no editor de texto padrão."""
        from src.utils.paths import get_log_file_path
        log_file = get_log_file_path()
        try:
            if not log_file.exists():
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write("Log de execução inicializado.\n")
            if sys.platform == "win32":
                os.startfile(log_file)
            else:
                subprocess.Popen(["xdg-open", str(log_file)])
            self._log(f"Arquivo Log.txt aberto com sucesso.")
        except Exception as e:
            self._log(f"Erro ao abrir Log.txt: {e}")

    def _update_clock(self):
        """Atualiza o cronômetro em tempo real a cada 1 segundo."""
        if self.is_collecting and self.start_time:
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            mins = (elapsed % 3600) // 60
            secs = elapsed % 60
            clock_str = f"⏱️ Tempo Decorrido: {hours:02d}:{mins:02d}:{secs:02d}"
            self.lbl_clock.configure(text=clock_str)
            self.timer_after_id = self.after(1000, self._update_clock)

    def _open_output_folder(self):
        """Abre a pasta local 'output' no Windows Explorer."""
        out_dir = get_output_dir()
        try:
            if sys.platform == "win32":
                os.startfile(out_dir)
            else:
                subprocess.Popen(["xdg-open", str(out_dir)])
            self._log(f"Pasta output aberta: {out_dir}")
        except Exception as e:
            self._log(f"Erro ao abrir pasta output: {e}")

    def _parse_dates(self) -> tuple[Optional[datetime], Optional[datetime]]:
        start_date_str = self.entry_start_date.get().strip()
        end_date_str = self.entry_end_date.get().strip()

        start_h = self.opt_start_hour.get()
        start_m = self.opt_start_min.get()

        end_h = self.opt_end_hour.get()
        end_m = self.opt_end_min.get()

        try:
            dt_start_date = datetime.strptime(start_date_str, "%d/%m/%Y")
            dt_start = dt_start_date.replace(hour=int(start_h), minute=int(start_m), second=0)
        except ValueError:
            self._log("⚠️ Data inicial inválida. Use o formato DD/MM/AAAA.")
            return None, None

        try:
            dt_end_date = datetime.strptime(end_date_str, "%d/%m/%Y")
            dt_end = dt_end_date.replace(hour=int(end_h), minute=int(end_m), second=59)
        except ValueError:
            self._log("⚠️ Data final inválida. Use o formato DD/MM/AAAA.")
            return None, None

        if dt_start > dt_end:
            self._log("⚠️ A data inicial não pode ser posterior à data final.")
            return None, None

        return dt_start, dt_end

    def _on_start_stop_clicked(self):
        if self.is_collecting:
            # Solicita cancelamento
            self._log("Solicitando interrupção da coleta...")
            if self.cancel_event:
                self.cancel_event.set()
            self.btn_start.configure(state="disabled")
            return

        target = self.entry_target.get().strip()
        if not target:
            self._log("⚠️ Insira o ID, Link ou @Username do grupo/canal para coletar.")
            return

        dt_start, dt_end = self._parse_dates()
        if not dt_start or not dt_end:
            return

        if not self.auth_manager:
            self._log("⚠️ Nenhuma sessão ativa do Telegram encontrada. Retorne à tela anterior para conectar.")
            return

        # Inicia a coleta
        self.is_collecting = True
        self.start_time = time.time()
        self.cancel_event = asyncio.Event()

        self.btn_start.configure(
            text="⏹ Cancelar Coleta",
            fg_color="#DC2626",
            hover_color="#B91C1C",
            state="normal"
        )
        self.btn_back.configure(state="disabled")
        self.prog_bar.start()
        self._update_clock()

        self._log(f"Iniciando coleta em '{target}' de {dt_start.strftime('%d/%m/%Y %H:%M')} até {dt_end.strftime('%d/%m/%Y %H:%M')}...")

        # Dispara thread de trabalho
        threading.Thread(
            target=self._run_collector_thread,
            args=(target, dt_start, dt_end),
            daemon=True
        ).start()

    def _run_collector_thread(self, target: str, dt_start: datetime, dt_end: datetime):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def on_progress(scanned: int, saved: int, media: int, dt: Optional[datetime], status: str):
            self.after(0, lambda: self._update_progress_ui(scanned, saved, media, dt, status))

        result = None
        client = None
        try:
            session_path = str(self.auth_manager.session_path)
            api_id = self.auth_manager.api_id
            api_hash = self.auth_manager.api_hash

            client = TelegramClient(session_path, api_id, api_hash)
            loop.run_until_complete(client.connect())

            if not loop.run_until_complete(client.is_user_authorized()):
                raise PermissionError("Sessão do Telegram não autorizada. Retorne à tela de credenciais para reconectar.")

            result = loop.run_until_complete(
                collect_messages(
                    client=client,
                    target_chat=target,
                    start_dt_brt=dt_start,
                    end_dt_brt=dt_end,
                    download_media_files=True,
                    progress_callback=on_progress,
                    cancel_event=self.cancel_event
                )
            )

            # Exportação para Excel (.xlsx) estruturado e anonimizado
            self.after(0, lambda: self._log("📊 Gerando planilha Excel estruturada e anonimizada..."))
            chat_id = result.get("chat_id") if result else None
            chat_title = result.get("chat_title") if result else target

            excel_path = export_to_tcc_spreadsheet(
                chat_id=chat_id,
                chat_title=chat_title,
                start_dt=dt_start,
                end_dt=dt_end
            )

            media_folder_name = result.get("media_folder_name", "") if result else ""
            if media_folder_name:
                self.after(0, lambda: self._log(f"📁 Mídias organizadas em: output/Mídias/{media_folder_name}"))
            self.after(0, lambda: self._log(f"✅ Planilha salva com sucesso em:\n{excel_path}"))
            self.after(0, lambda: self._log("🎉 Processo completo! Clique em 'Abrir Pasta Output' para visualizar os arquivos."))

        except Exception as e:
            from src.utils.logger import log_event
            err_msg = str(e)
            log_event(f"Erro durante a coleta: {err_msg}", level="ERRO", exc=e)
            self.after(0, lambda: self._log(f"❌ Erro durante a coleta: {err_msg}"))
        finally:
            if client:
                try:
                    if client.is_connected():
                        loop.run_until_complete(client.disconnect())
                except Exception:
                    pass
                try:
                    if hasattr(client, 'session') and hasattr(client.session, 'close'):
                        client.session.close()
                except Exception:
                    pass
            try:
                loop.close()
            except Exception:
                pass
            self.after(0, self._on_collection_finished)

    def _update_progress_ui(self, scanned: int, saved: int, media: int, dt: Optional[datetime], status: str):
        self.lbl_cnt_scanned.configure(text=f"Mensagens Verificadas\n{scanned}")
        self.lbl_cnt_saved.configure(text=f"Mensagens no Período\n{saved}")
        self.lbl_cnt_media.configure(text=f"Mídias Baixadas\n{media}")
        if status:
            self._log(status)

    def _on_collection_finished(self):
        self.is_collecting = False
        if self.timer_after_id:
            self.after_cancel(self.timer_after_id)
            self.timer_after_id = None

        self.btn_start.configure(
            text="🚀 Iniciar Coleta",
            fg_color="#16A34A",
            hover_color="#15803D",
            state="normal"
        )
        self.btn_back.configure(state="normal")
        self.prog_bar.stop()
        self.prog_bar.set(0)

    def _on_back_clicked(self):
        if self.is_collecting:
            return
        self.on_back_callback()
