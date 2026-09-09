import os
import sys
import json
import time
import subprocess
import threading
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Callable

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from telethon import TelegramClient

from src.utils.paths import get_output_dir, get_medias_dir, get_sheets_dir
from src.utils.session_patch import apply_telethon_sqlite_patch
from src.pipeline.filters import BRT, parse_date_to_brt
from src.collectors.telegram_auth import TelegramAuthManager
from src.collectors.telegram_stream import TelegramStreamCollector
from src.exporter.excel_exporter import export_to_tcc_spreadsheet
from src.db.session import SessionLocal, init_db
from src.db.models import Message

apply_telethon_sqlite_patch()

COLUMNS_CONFIG = [
    ("id", "ID Mensagem", 95, "center"),
    ("date", "Data/Hora (BRT)", 135, "center"),
    ("bot", "Bot?", 50, "center"),
    ("admin", "Admin?", 55, "center"),
    ("forward", "Encam.?", 65, "center"),
    ("forward_from", "Origem Encaminhamento", 140, "w"),
    ("has_media", "Mídia?", 55, "center"),
    ("media_type", "Tipo Mídia", 80, "center"),
    ("media_file", "Arquivo Mídia Salvo", 180, "w"),
    ("views", "Visualizações", 85, "center"),
    ("reactions_count", "Total Reações", 85, "center"),
    ("reactions", "Tipos de Reações", 120, "w"),
    ("text", "Texto da Mensagem", 260, "w"),
    ("sender", "Código Autor (Anônimo)", 130, "center"),
    ("urls", "Links Extraídos", 160, "w"),
]

class CollectionScreen(ctk.CTkFrame):
    """
    Tela Principal de Coleta: Coleta Automática Quase Instantânea (Live Stream)
    com Visor de Planilha ao Vivo (com as 15 colunas oficiais do TCC) e
    fechamento diário automatizado às 23:59:59 (BRT).
    """

    def __init__(self, parent, on_back_callback: Callable[[], None]):
        super().__init__(parent, fg_color="transparent")
        self.on_back_callback = on_back_callback
        self.auth_manager: Optional[TelegramAuthManager] = None
        self.collector: Optional[TelegramStreamCollector] = None
        self.stream_thread: Optional[threading.Thread] = None

        self.is_streaming = False
        self.today_date = datetime.now(BRT).date()
        self.today_messages_count = 0
        self.today_media_count = 0

        self._setup_ui()

    def set_auth_manager(self, auth_manager: TelegramAuthManager):
        """Recebe o gerenciador autenticado da Tela de Login."""
        self.auth_manager = auth_manager
        self._load_today_cached_messages()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Configurações e Controles
        self.grid_rowconfigure(1, weight=1) # Visor de Planilha ao Vivo

        # =========================================================================
        # 1. CARD SUPERIOR: CONFIGURAÇÕES E CONTROLES SIMPLIFICADOS
        # =========================================================================
        config_card = ctk.CTkFrame(self, corner_radius=12, fg_color="#0F172A", border_width=1, border_color="#334155")
        config_card.grid(row=0, column=0, padx=12, pady=(10, 8), sticky="ew")

        # Cabeçalho do Card
        top_row = ctk.CTkFrame(config_card, fg_color="transparent")
        top_row.pack(fill="x", padx=16, pady=(12, 6))

        title_lbl = ctk.CTkLabel(
            top_row,
            text="📡 Coleta Automática Instantânea (Live Stream)",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(side="left")

        self.lbl_status_badge = ctk.CTkLabel(
            top_row,
            text="⚪ COLETOR PARADO",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#94A3B8"
        )
        self.lbl_status_badge.pack(side="right")

        # Linha de Parâmetros: Alvo, Data, Horário Limite e Mídias
        params_row = ctk.CTkFrame(config_card, fg_color="transparent")
        params_row.pack(fill="x", padx=16, pady=(0, 10))

        # Alvo
        lbl_target = ctk.CTkLabel(params_row, text="Grupo/Canal:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#E2E8F0")
        lbl_target.pack(side="left", padx=(0, 4))

        self.entry_target = ctk.CTkEntry(
            params_row,
            placeholder_text="Ex: @nomedogrupo, link ou ID",
            width=240,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.entry_target.pack(side="left", padx=(0, 14))

        # Data de Referência
        lbl_date = ctk.CTkLabel(params_row, text="📅 Data de Coleta:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#E2E8F0")
        lbl_date.pack(side="left", padx=(0, 4))

        self.entry_date = ctk.CTkEntry(
            params_row,
            placeholder_text="DD/MM/AAAA",
            width=110,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.entry_date.pack(side="left", padx=(0, 14))
        self.entry_date.insert(0, datetime.now(BRT).strftime("%d/%m/%Y"))
        self.entry_date.bind("<FocusOut>", lambda e: self._refresh_cached_messages())
        self.entry_date.bind("<Return>", lambda e: self._refresh_cached_messages())

        # Horário Limite Diário
        lbl_cutoff = ctk.CTkLabel(params_row, text="⏰ Horário Limite Diário:", font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color="#E2E8F0")
        lbl_cutoff.pack(side="left", padx=(0, 4))

        self.entry_cutoff = ctk.CTkEntry(
            params_row,
            placeholder_text="HH:MM:SS",
            width=90,
            height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.entry_cutoff.pack(side="left", padx=(0, 14))
        self.entry_cutoff.insert(0, "23:59:59")

        # Download de Mídias
        self.chk_media = ctk.CTkCheckBox(
            params_row,
            text="Baixar Arquivos e Mídias",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#E2E8F0"
        )
        self.chk_media.pack(side="left", padx=(4, 0))
        self.chk_media.select()

        # Barra de Ações e Métricas
        actions_bar = ctk.CTkFrame(config_card, fg_color="#1E293B", corner_radius=8)
        actions_bar.pack(fill="x", padx=16, pady=(0, 12))

        # Botão Iniciar / Parar Coleta
        self.btn_toggle = ctk.CTkButton(
            actions_bar,
            text="🚀 Iniciar Coleta Instantânea",
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#16A34A",
            hover_color="#15803D",
            command=self._on_toggle_streaming
        )
        self.btn_toggle.pack(side="left", padx=8, pady=8)

        # Botão Gerar Planilha do Dia Agora
        self.btn_export = ctk.CTkButton(
            actions_bar,
            text="📊 Gerar Planilha Agora",
            height=36,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#0284C7",
            hover_color="#0369A1",
            command=self._on_manual_export_clicked
        )
        self.btn_export.pack(side="left", padx=(0, 8), pady=8)

        # Botões de Utilidades
        self.btn_output = ctk.CTkButton(
            actions_bar,
            text="📂 Pasta Output",
            height=36,
            width=110,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#334155",
            hover_color="#475569",
            command=self._open_output_folder
        )
        self.btn_output.pack(side="left", padx=(0, 6), pady=8)

        self.btn_logs = ctk.CTkButton(
            actions_bar,
            text="📄 Log.txt",
            height=36,
            width=90,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="#334155",
            hover_color="#475569",
            command=self._open_log_file
        )
        self.btn_logs.pack(side="left", padx=(0, 8), pady=8)

        # Indicador de Métricas ao Vivo
        self.lbl_metrics = ctk.CTkLabel(
            actions_bar,
            text="Mensagens Hoje: 0  |  Mídias Hoje: 0  |  Próximo Fechamento: 23:59:59",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#38BDF8"
        )
        self.lbl_metrics.pack(side="right", padx=14, pady=8)

        # =========================================================================
        # 2. CARD INFERIOR: VISOR DE PLANILHA EM TEMPO REAL (TREEVIEW GRID)
        # =========================================================================
        grid_card = ctk.CTkFrame(self, corner_radius=12, fg_color="#0F172A", border_width=1, border_color="#334155")
        grid_card.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="nsew")
        grid_card.grid_columnconfigure(0, weight=1)
        grid_card.grid_rowconfigure(1, weight=1)

        # Cabeçalho da Planilha
        grid_header = ctk.CTkFrame(grid_card, fg_color="transparent")
        grid_header.grid(row=0, column=0, padx=16, pady=(10, 6), sticky="ew")

        lbl_grid_title = ctk.CTkLabel(
            grid_header,
            text="📋 Visor de Planilha em Tempo Real (Espelho da Planilha Oficial .xlsx)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#F8FAFC"
        )
        lbl_grid_title.pack(side="left")

        lbl_hint = ctk.CTkLabel(
            grid_header,
            text="Dica: Dê dois cliques em qualquer linha para inspecionar os detalhes da mensagem.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#64748B"
        )
        lbl_hint.pack(side="right")

        # Container do Treeview com Scrollbars
        table_frame = tk.Frame(grid_card, bg="#0F172A")
        table_frame.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        # Estilização ttk para modo escuro moderno
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "LiveGrid.Treeview",
            background="#0F172A",
            foreground="#F8FAFC",
            fieldbackground="#0F172A",
            rowheight=26,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        style.configure(
            "LiveGrid.Treeview.Heading",
            background="#1E3A8A", # Azul Marinho / Navy Oficial
            foreground="#FFFFFF",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            borderwidth=1
        )
        style.map(
            "LiveGrid.Treeview",
            background=[("selected", "#0284C7")],
            foreground=[("selected", "#FFFFFF")]
        )
        style.map(
            "LiveGrid.Treeview.Heading",
            background=[("active", "#1D4ED8")]
        )

        col_ids = [c[0] for c in COLUMNS_CONFIG]
        self.tree = ttk.Treeview(
            table_frame,
            columns=col_ids,
            show="headings",
            style="LiveGrid.Treeview",
            selectmode="browse"
        )

        for cid, header, width, align in COLUMNS_CONFIG:
            self.tree.heading(cid, text=header, anchor=align)
            self.tree.column(cid, width=width, minwidth=40, anchor=align)

        # Scrollbars
        v_scroll = ctk.CTkScrollbar(table_frame, orientation="vertical", command=self.tree.yview)
        h_scroll = ctk.CTkScrollbar(table_frame, orientation="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        # Tags para zebrado elegante
        self.tree.tag_configure("even", background="#0F172A")
        self.tree.tag_configure("odd", background="#1E293B")
        self.tree.tag_configure("new", background="#064E3B", foreground="#A7F3D0") # Destaque suave em verde para mensagem instantânea

        # Evento de duplo clique
        self.tree.bind("<Double-1>", self._on_row_double_click)

    def _refresh_cached_messages(self):
        """Limpa e recarrega os dados do visor ao trocar a data de coleta."""
        if hasattr(self, "tree"):
            for item in self.tree.get_children():
                self.tree.delete(item)
            self._load_today_cached_messages()

    def _load_today_cached_messages(self):
        """Carrega mensagens já coletadas do dia de referência do banco de dados SQLite para o visor."""
        init_db()
        db = SessionLocal()
        try:
            target_date = datetime.now(BRT).date()
            if hasattr(self, "entry_date"):
                try:
                    d_str = self.entry_date.get().strip()
                    if d_str:
                        target_date = datetime.strptime(d_str, "%d/%m/%Y").date()
                except Exception:
                    pass
            start_today = datetime.combine(target_date, datetime.min.time())
            end_today = datetime.combine(target_date, datetime.max.time().replace(microsecond=0))
            messages = db.query(Message).filter(Message.date_brt >= start_today, Message.date_brt <= end_today).order_by(Message.date_brt.desc()).limit(150).all()

            for i, m in enumerate(messages):
                reacts_display = "-"
                if m.reactions_json:
                    try:
                        r_dict = json.loads(m.reactions_json)
                        if r_dict:
                            reacts_display = ", ".join([f"{k} ({v})" for k, v in r_dict.items()])
                    except Exception:
                        pass

                tag = "even" if i % 2 == 0 else "odd"
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        m.telegram_msg_id,
                        m.date_brt.strftime("%d/%m/%Y %H:%M:%S"),
                        "Sim" if m.is_bot else "Não",
                        "Sim" if getattr(m, 'is_admin', False) else "Não",
                        "Sim" if m.is_forward else "Não",
                        m.forward_from_name or "-",
                        "Sim" if m.has_media else "Não",
                        m.media_type or "Nenhuma",
                        m.media_filename or "-",
                        m.views_count or 0,
                        m.reactions_count or 0,
                        reacts_display,
                        (m.text_raw or "").replace("\n", " ")[:60],
                        m.sender_id_anon or "-",
                        m.urls_list or "-"
                    ),
                    tags=(tag,)
                )
            self.today_messages_count = len(messages)
            self._update_metrics_label()
        except Exception:
            pass
        finally:
            db.close()

    def _update_metrics_label(self):
        cutoff = self.entry_cutoff.get().strip() or "23:59:59" if hasattr(self, "entry_cutoff") else "23:59:59"
        d_str = self.entry_date.get().strip() if hasattr(self, "entry_date") else datetime.now(BRT).strftime("%d/%m/%Y")
        self.lbl_metrics.configure(
            text=f"Mensagens ({d_str}): {self.today_messages_count}  |  Mídias ({d_str}): {self.today_media_count}  |  Próximo Fechamento: {cutoff}"
        )

    def _on_toggle_streaming(self):
        """Inicia ou pausa a coleta contínua em tempo real."""
        if not self.is_streaming:
            self._start_streaming()
        else:
            self._stop_streaming()

    def _start_streaming(self):
        if not self.auth_manager or not self.auth_manager.client:
            self._show_alert("Erro de Conexão", "Sessão do Telegram não autenticada. Volte à tela de Credenciais.")
        target = self.entry_target.get().strip()
        if not target:
            self._show_alert("Alvo Não Informado", "Por favor, digite o @username, link ou ID do grupo ou canal do Telegram que deseja monitorar.")
            return

        date_str = self.entry_date.get().strip()
        try:
            target_date = datetime.strptime(date_str, "%d/%m/%Y").date()
        except Exception:
            target_date = datetime.now(BRT).date()
            self.entry_date.delete(0, "end")
            self.entry_date.insert(0, target_date.strftime("%d/%m/%Y"))

        cutoff_str = self.entry_cutoff.get().strip() or "23:59:59"
        download_media = bool(self.chk_media.get())

        self.is_streaming = True
        self.btn_toggle.configure(
            text="⏹️ Parar Coleta",
            fg_color="#DC2626",
            hover_color="#B91C1C"
        )
        self.lbl_status_badge.configure(text=f"🟢 AO VIVO - {target_date.strftime('%d/%m/%Y')}", text_color="#22C55E")

        def on_msg_received(info: dict):
            self.after(0, lambda: self._add_message_to_grid(info))

        def on_export_done(excel_path: str):
            self.after(0, lambda: self._on_daily_exported(excel_path))

        self.collector = TelegramStreamCollector(
            client=self.auth_manager.client,
            target_chat=target,
            target_date=target_date,
            cutoff_time_str=cutoff_str,
            on_message_callback=on_msg_received,
            on_export_callback=on_export_done,
            log_callback=print,
            download_media=download_media
        )

        def runner():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.collector.start())
            except Exception as e:
                print(f"Erro no streaming: {e}")
            finally:
                self.after(0, self._on_streaming_stopped)

        self.stream_thread = threading.Thread(target=runner, daemon=True)
        self.stream_thread.start()

    def _stop_streaming(self):
        if self.collector:
            self.collector.stop()
        self._on_streaming_stopped()

    def _on_streaming_stopped(self):
        self.is_streaming = False
        self.btn_toggle.configure(
            text="🚀 Iniciar Coleta Instantânea",
            fg_color="#16A34A",
            hover_color="#15803D"
        )
        self.lbl_status_badge.configure(text="⚪ COLETOR PARADO", text_color="#94A3B8")

    def _add_message_to_grid(self, info: dict):
        """Insere a mensagem instantaneamente no topo do visor da planilha."""
        self.today_messages_count = info.get("today_messages", self.today_messages_count + 1)
        self.today_media_count = info.get("today_media", self.today_media_count)

        text_preview = (info.get("text", "") or "").replace("\n", " ")
        if len(text_preview) > 60:
            text_preview = text_preview[:58] + "..."

        row_values = (
            info.get("msg_id"),
            info.get("date_brt_str", datetime.now(BRT).strftime("%d/%m/%Y %H:%M:%S")),
            info.get("is_bot", "Não"),
            info.get("is_admin", "Não"),
            info.get("is_forward", "Não"),
            info.get("forward_from", "-"),
            info.get("has_media", "Não"),
            info.get("media_type", "Nenhuma"),
            info.get("media_file", "-"),
            info.get("views", 0),
            info.get("reactions_count", 0),
            info.get("reactions", "-"),
            text_preview,
            info.get("sender_anon", "Participante_Anon"),
            info.get("urls", "-")
        )

        # Insere no topo com tag de destaque instantâneo
        item_id = self.tree.insert("", 0, values=row_values, tags=("new",))
        # Remove tag de destaque após 4 segundos para retornar ao tema escuro padrão
        self.after(4000, lambda: self.tree.item(item_id, tags=("even",)))

        self._update_metrics_label()

    def _on_daily_exported(self, excel_path: str):
        file_name = Path(excel_path).name
        self._show_alert("Fechamento Diário Concluído", f"A planilha oficial do dia foi gerada com sucesso:\n\n{file_name}\n\nSalva em: output/Planilhas de Catalogação/")

    def _on_manual_export_clicked(self):
        """Gera a planilha acumulada do dia de referência sob demanda."""
        date_str = self.entry_date.get().strip() if hasattr(self, "entry_date") else None
        try:
            target_date = datetime.strptime(date_str, "%d/%m/%Y").date() if date_str else datetime.now(BRT).date()
        except Exception:
            target_date = datetime.now(BRT).date()

        if self.collector:
            path = self.collector.trigger_manual_export()
            if path:
                self._show_alert("Planilha Exportada", f"Planilha do dia {target_date.strftime('%d/%m/%Y')} gerada com sucesso:\n\n{Path(path).name}")
            else:
                self._show_alert("Aviso", "Não foi possível gerar a planilha no momento.")
        else:
            # Exporta diretamente pelo banco de dados para a data informada
            start_dt = datetime.combine(target_date, datetime.min.time())
            now_brt = datetime.now(BRT)
            if target_date == now_brt.date():
                end_dt = now_brt
            else:
                end_dt = datetime.combine(target_date, datetime.max.time().replace(microsecond=0))
            target = self.entry_target.get().strip() or None
            try:
                excel_path = export_to_tcc_spreadsheet(chat_id=target, start_dt=start_dt, end_dt=end_dt)
                self._show_alert("Planilha Exportada", f"Planilha do dia {target_date.strftime('%d/%m/%Y')} gerada com sucesso:\n\n{Path(excel_path).name}")
            except Exception as e:
                self._show_alert("Erro", f"Falha ao exportar planilha: {e}")

    def _on_row_double_click(self, event):
        """Abre modal com os detalhes completos da mensagem selecionada."""
        selected_item = self.tree.focus()
        if not selected_item:
            return

        values = self.tree.item(selected_item, "values")
        if not values:
            return

        msg_id = values[0]
        # Busca texto completo no banco
        db = SessionLocal()
        full_text = values[12]
        try:
            m = db.query(Message).filter_by(telegram_msg_id=int(msg_id)).first()
            if m:
                full_text = m.text_raw or ""
        except Exception:
            pass
        finally:
            db.close()

        # Modal flutuante
        modal = ctk.CTkToplevel(self)
        modal.title(f"Detalhes da Mensagem #{msg_id}")
        modal.geometry("640x520")
        modal.attributes("-topmost", True)

        m_frame = ctk.CTkFrame(modal, corner_radius=12, fg_color="#0F172A")
        m_frame.pack(fill="both", expand=True, padx=14, pady=14)

        lbl_head = ctk.CTkLabel(
            m_frame,
            text=f"Mensagem #{msg_id} — {values[1]} (BRT)",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color="#38BDF8"
        )
        lbl_head.pack(anchor="w", padx=14, pady=(12, 4))

        meta_txt = (
            f"👤 Autor Anônimo: {values[13]}  |  🤖 Bot: {values[2]}  |  👑 Admin: {values[3]}\n"
            f"📎 Mídia: {values[7]} ({values[8]})\n"
            f"👀 Visualizações: {values[9]}  |  ❤️ Reações: {values[11]} (Total: {values[10]})\n"
            f"🔗 Encaminhada: {values[4]} ({values[5]})"
        )
        lbl_meta = ctk.CTkLabel(m_frame, text=meta_txt, font=ctk.CTkFont(family="Segoe UI", size=11), text_color="#94A3B8", justify="left")
        lbl_meta.pack(anchor="w", padx=14, pady=(0, 8))

        lbl_body = ctk.CTkLabel(m_frame, text="Texto Completo da Postagem:", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color="#E2E8F0")
        lbl_body.pack(anchor="w", padx=14, pady=(0, 2))

        txt_box = ctk.CTkTextbox(m_frame, height=220, font=ctk.CTkFont(family="Segoe UI", size=11))
        txt_box.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        txt_box.insert("1.0", full_text)
        txt_box.configure(state="disabled")

        btn_close = ctk.CTkButton(m_frame, text="Fechar", width=100, height=32, command=modal.destroy)
        btn_close.pack(anchor="e", padx=14, pady=(0, 10))

    def _open_output_folder(self):
        """Abre a pasta local 'output' no Windows Explorer."""
        out_dir = get_output_dir()
        try:
            if sys.platform == "win32":
                os.startfile(out_dir)
            else:
                subprocess.Popen(["xdg-open", str(out_dir)])
        except Exception as e:
            self._show_alert("Erro", f"Não foi possível abrir a pasta output: {e}")

    def _open_log_file(self):
        """Abre o arquivo de Log."""
        from src.utils.paths import get_base_dir
        log_file = get_base_dir() / "Log.txt"
        try:
            if not log_file.exists():
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write("Log inicializado.\n")
            if sys.platform == "win32":
                os.startfile(log_file)
            else:
                subprocess.Popen(["xdg-open", str(log_file)])
        except Exception as e:
            self._show_alert("Erro", f"Não foi possível abrir Log.txt: {e}")

    def _show_alert(self, title: str, message: str):
        """Exibe uma caixa de diálogo elegante e informativa."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("440x220")
        dialog.attributes("-topmost", True)

        f = ctk.CTkFrame(dialog, fg_color="#0F172A", corner_radius=10)
        f.pack(fill="both", expand=True, padx=10, pady=10)

        lbl = ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color="#38BDF8")
        lbl.pack(padx=14, pady=(14, 6))

        msg_lbl = ctk.CTkLabel(f, text=message, font=ctk.CTkFont(size=11), text_color="#E2E8F0", wraplength=400)
        msg_lbl.pack(padx=14, pady=(0, 14), fill="both", expand=True)

        btn = ctk.CTkButton(f, text="OK", width=90, height=32, command=dialog.destroy)
        btn.pack(pady=(0, 12))
