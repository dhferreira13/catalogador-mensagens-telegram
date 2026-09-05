import asyncio
import threading
import webbrowser
import customtkinter as ctk
from typing import Callable, Optional

from src.config import load_saved_credentials, save_user_credentials
from src.collectors.telegram_auth import TelegramAuthManager
from src.gui.dialogs.auth_dialog import ask_telegram_code, ask_2fa_password

class CredentialsScreen(ctk.CTkFrame):
    """
    Tela 1: Configuração de Credenciais de API do Telegram com Tutorial Passo a Passo.
    """
    def __init__(self, parent, on_success_callback: Callable[[TelegramAuthManager, dict], None]):
        super().__init__(parent, fg_color="transparent")
        self.on_success_callback = on_success_callback
        self.auth_manager: Optional[TelegramAuthManager] = None

        self._setup_ui()
        self._load_existing_creds()

    def _setup_ui(self):
        # Grid com duas colunas: Esquerda = Formulário de Credenciais, Direita = Tutorial Integrado
        self.grid_columnconfigure(0, weight=5)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(0, weight=1)

        # ----------------- PAINEL ESQUERDO: FORMULÁRIO -----------------
        form_card = ctk.CTkFrame(self, corner_radius=14)
        form_card.grid(row=0, column=0, padx=(15, 10), pady=15, sticky="nsew")

        # Cabeçalho
        title = ctk.CTkLabel(
            form_card,
            text="Autenticação Telegram API",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold")
        )
        title.pack(anchor="w", padx=25, pady=(20, 5))

        subtitle = ctk.CTkLabel(
            form_card,
            text="Insira suas chaves de desenvolvedor do Telegram para habilitar a extração acadêmica de dados.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#94A3B8",
            wraplength=340,
            justify="left"
        )
        subtitle.pack(anchor="w", padx=25, pady=(0, 20))

        # Campo: API ID
        lbl_api_id = ctk.CTkLabel(
            form_card,
            text="API ID (número):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        )
        lbl_api_id.pack(anchor="w", padx=25, pady=(5, 2))

        self.entry_api_id = ctk.CTkEntry(
            form_card,
            placeholder_text="Ex: 12345678",
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.entry_api_id.pack(fill="x", padx=25, pady=(0, 10))

        # Campo: API Hash
        lbl_api_hash = ctk.CTkLabel(
            form_card,
            text="API Hash (código alfanumérico):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        )
        lbl_api_hash.pack(anchor="w", padx=25, pady=(5, 2))

        self.entry_api_hash = ctk.CTkEntry(
            form_card,
            placeholder_text="Ex: 0123456789abcdef0123456789abcdef",
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.entry_api_hash.pack(fill="x", padx=25, pady=(0, 10))

        # Campo: Telefone
        lbl_phone = ctk.CTkLabel(
            form_card,
            text="Número de Telefone (com DDI e DDD):",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        )
        lbl_phone.pack(anchor="w", padx=25, pady=(5, 2))

        self.entry_phone = ctk.CTkEntry(
            form_card,
            placeholder_text="Ex: +5511999999999",
            height=38,
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.entry_phone.pack(fill="x", padx=25, pady=(0, 15))

        # Checkbox salvar credenciais
        self.chk_save_var = ctk.BooleanVar(value=True)
        self.chk_save = ctk.CTkCheckBox(
            form_card,
            text="Salvar credenciais neste computador",
            variable=self.chk_save_var,
            font=ctk.CTkFont(family="Segoe UI", size=12)
        )
        self.chk_save.pack(anchor="w", padx=25, pady=(0, 15))

        # Feedback de Status
        self.lbl_status = ctk.CTkLabel(
            form_card,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#38BDF8",
            wraplength=340,
            justify="center"
        )
        self.lbl_status.pack(fill="x", padx=25, pady=(0, 10))

        # Barra de progresso para conexão
        self.prog_bar = ctk.CTkProgressBar(form_card, mode="indeterminate", height=6)
        self.prog_bar.pack(fill="x", padx=25, pady=(0, 15))
        self.prog_bar.set(0)
        self.prog_bar.stop()

        # Botão Conectar
        self.btn_connect = ctk.CTkButton(
            form_card,
            text="Conectar e Prosseguir ➔",
            height=44,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._on_connect_clicked
        )
        self.btn_connect.pack(fill="x", padx=25, pady=(0, 20))

        # ----------------- PAINEL DIREITO: TUTORIAL INTEGRADO -----------------
        tutorial_card = ctk.CTkFrame(self, corner_radius=14)
        tutorial_card.grid(row=0, column=1, padx=(10, 15), pady=15, sticky="nsew")

        tut_header = ctk.CTkLabel(
            tutorial_card,
            text="📖 Como Obter suas Chaves de API",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold")
        )
        tut_header.pack(anchor="w", padx=20, pady=(20, 10))

        tut_scroll = ctk.CTkScrollableFrame(tutorial_card, corner_radius=10, fg_color="transparent")
        tut_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        tutorial_text = (
            "Para que o aplicativo possa se comunicar com o Telegram de forma segura e oficial, "
            "você precisa de credenciais de desenvolvedor gratuitas fornecidas pelo próprio Telegram.\n\n"
            "Siga o passo a passo abaixo:\n\n"
            "1️⃣  Clique no botão 'Abrir my.telegram.org' abaixo ou acesse https://my.telegram.org no navegador.\n\n"
            "2️⃣  Digite o número do seu celular cadastrado no Telegram (com o DDI +55 e DDD) e clique em 'Next'.\n\n"
            "3️⃣  Você receberá uma mensagem no aplicativo do Telegram com um código alfanumérico. Digite-o na página web para entrar.\n\n"
            "4️⃣  Na tela inicial do portal, clique na opção 'API development tools'.\n\n"
            "5️⃣  Preencha o pequeno formulário com qualquer nome:\n"
            "      • App title: Catalogador TCC\n"
            "      • Short name: catalogador_tcc\n"
            "      (Os outros campos podem ser deixados em branco).\n\n"
            "6️⃣  Clique em 'Create application'.\n\n"
            "7️⃣  Pronto! Serão gerados dois valores:\n"
            "      • api_id: um número (copie e cole no campo API ID).\n"
            "      • api_hash: um código de letras e números (copie e cole no campo API Hash).\n\n"
            "💡 Dica Ética: Seus dados de acesso ficam salvos apenas localmente na sua máquina e nunca são compartilhados externamente."
        )

        tut_content = ctk.CTkLabel(
            tut_scroll,
            text=tutorial_text,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#CBD5E1",
            justify="left",
            wraplength=340
        )
        tut_content.pack(anchor="w", padx=5, pady=5)

        btn_open_portal = ctk.CTkButton(
            tutorial_card,
            text="🌐 Abrir my.telegram.org no Navegador",
            height=38,
            fg_color="#0D9488",
            hover_color="#0F766E",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=lambda: webbrowser.open("https://my.telegram.org")
        )
        btn_open_portal.pack(fill="x", padx=20, pady=(0, 20))

    def _load_existing_creds(self):
        """Carrega credenciais salvas previamente se existirem."""
        creds = load_saved_credentials()
        if creds.get("api_id"):
            self.entry_api_id.insert(0, creds["api_id"])
        if creds.get("api_hash"):
            self.entry_api_hash.insert(0, creds["api_hash"])
        if creds.get("phone"):
            self.entry_phone.insert(0, creds["phone"])

    def _set_ui_busy(self, is_busy: bool, status_msg: str = ""):
        self.lbl_status.configure(text=status_msg)
        if is_busy:
            self.btn_connect.configure(state="disabled")
            self.prog_bar.start()
        else:
            self.btn_connect.configure(state="normal")
            self.prog_bar.stop()
            self.prog_bar.set(0)

    def _on_connect_clicked(self):
        api_id_raw = self.entry_api_id.get().strip()
        api_hash = self.entry_api_hash.get().strip()
        phone = self.entry_phone.get().strip()

        if not api_id_raw or not api_id_raw.isdigit():
            self.lbl_status.configure(text="⚠️ O campo 'API ID' deve ser um número válido.")
            return

        if not api_hash:
            self.lbl_status.configure(text="⚠️ O campo 'API Hash' é obrigatório.")
            return

        if not phone:
            self.lbl_status.configure(text="⚠️ O campo 'Número de Telefone' é obrigatório.")
            return

        api_id = int(api_id_raw)

        if self.chk_save_var.get():
            save_user_credentials(str(api_id), api_hash, phone)

        self._set_ui_busy(True, "Iniciando conexão com os servidores do Telegram...")

        # Executa a autenticação em thread separada para não travar a interface
        threading.Thread(
            target=self._run_auth_thread,
            args=(api_id, api_hash, phone),
            daemon=True
        ).start()

    def _run_auth_thread(self, api_id: int, api_hash: str, phone: str):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            self.auth_manager = TelegramAuthManager(api_id, api_hash, phone)
            
            # Conecta e verifica autorização
            is_authorized = loop.run_until_complete(self.auth_manager.connect())

            if is_authorized:
                loop.run_until_complete(self.auth_manager.disconnect())
                loop.close()
                self.after(0, lambda: self._on_auth_complete(api_id, api_hash, phone))
                return

            # Se não estiver autorizado, solicita código
            self.after(0, lambda: self.lbl_status.configure(text="Solicitando código de login ao Telegram..."))
            loop.run_until_complete(self.auth_manager.request_code())

            # Exibe modal de código na thread principal do Tkinter
            code_event = threading.Event()
            user_code = [None]

            def prompt_code():
                code = ask_telegram_code(self.winfo_toplevel(), phone)
                user_code[0] = code
                code_event.set()

            self.after(0, prompt_code)
            code_event.wait()

            if not user_code[0]:
                self.after(0, lambda: self._set_ui_busy(False, "Autenticação cancelada pelo usuário."))
                return

            self.after(0, lambda: self.lbl_status.configure(text="Validando código..."))
            result = loop.run_until_complete(self.auth_manager.sign_in_with_code(user_code[0]))

            if result == "2FA_REQUIRED":
                # Solicita senha de nuvem (2FA)
                pwd_event = threading.Event()
                user_pwd = [None]

                def prompt_pwd():
                    pwd = ask_2fa_password(self.winfo_toplevel())
                    user_pwd[0] = pwd
                    pwd_event.set()

                self.after(0, prompt_pwd)
                pwd_event.wait()

                if not user_pwd[0]:
                    self.after(0, lambda: self._set_ui_busy(False, "Autenticação cancelada."))
                    return

                self.after(0, lambda: self.lbl_status.configure(text="Validando senha 2FA..."))
                loop.run_until_complete(self.auth_manager.sign_in_with_password(user_pwd[0]))

            # Desconecta o cliente desta thread para liberar o arquivo de sessão
            loop.run_until_complete(self.auth_manager.disconnect())
            loop.close()

            # Sucesso!
            from src.utils.logger import log_event
            log_event("Autenticação com o Telegram realizada com sucesso.", level="SUCESSO")
            self.after(0, lambda: self._on_auth_complete(api_id, api_hash, phone))

        except Exception as e:
            from src.utils.logger import log_event
            err_msg = str(e)
            log_event(f"Erro na conexão com Telegram: {err_msg}", level="ERRO", exc=e)
            self.after(0, lambda: self._set_ui_busy(False, f"Erro na conexão: {err_msg}"))
            try:
                loop.run_until_complete(self.auth_manager.disconnect())
                loop.close()
            except Exception:
                pass

    def _on_auth_complete(self, api_id: int, api_hash: str, phone: str):
        from src.utils.logger import log_event
        log_event(f"Avançando para Tela de Coleta (Telefone: {phone[:6]}***)", level="INFO")
        self._set_ui_busy(False, "Conexão estabelecida com sucesso!")
        creds = {"api_id": api_id, "api_hash": api_hash, "phone": phone}
        self.on_success_callback(self.auth_manager, creds)
