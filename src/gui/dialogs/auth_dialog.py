import customtkinter as ctk
from typing import Optional

class InputModalDialog(ctk.CTkToplevel):
    """
    Diálogo modal moderno para solicitação de código do Telegram ou senha 2FA.
    """
    def __init__(
        self,
        parent,
        title: str,
        prompt: str,
        placeholder: str = "",
        is_password: bool = False,
        help_text: Optional[str] = None
    ):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x260")
        self.resizable(False, False)
        
        # Centraliza o diálogo em relação à janela principal
        self.transient(parent)
        self.grab_set()

        self.result: Optional[str] = None

        # Container principal
        frame = ctk.CTkFrame(self, corner_radius=12)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        title_label = ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        )
        title_label.pack(pady=(10, 5))

        prompt_label = ctk.CTkLabel(
            frame,
            text=prompt,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            wraplength=380,
            justify="center"
        )
        prompt_label.pack(pady=(0, 10))

        self.entry = ctk.CTkEntry(
            frame,
            placeholder_text=placeholder,
            show="*" if is_password else "",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            width=300,
            height=38,
            justify="center"
        )
        self.entry.pack(pady=5)
        self.entry.focus_set()
        self.entry.bind("<Return>", lambda e: self.on_confirm())

        if help_text:
            help_label = ctk.CTkLabel(
                frame,
                text=help_text,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="gray",
                wraplength=380
            )
            help_label.pack(pady=(2, 5))

        # Botões
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(pady=(12, 10))

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancelar",
            fg_color="#64748B",
            hover_color="#475569",
            width=100,
            command=self.on_cancel
        )
        btn_cancel.pack(side="left", padx=10)

        btn_confirm = ctk.CTkButton(
            btn_frame,
            text="Confirmar",
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            width=120,
            command=self.on_confirm
        )
        btn_confirm.pack(side="left", padx=10)

    def on_confirm(self):
        val = self.entry.get().strip()
        if val:
            self.result = val
            self.grab_release()
            self.destroy()

    def on_cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()

def ask_telegram_code(parent, phone: str) -> Optional[str]:
    """Exibe modal para entrada do código enviado pelo Telegram."""
    dialog = InputModalDialog(
        parent=parent,
        title="Código de Confirmação",
        prompt=f"O Telegram enviou um código de verificação para o aplicativo no seu celular associado a {phone}.",
        placeholder="Digite o código recebido (ex: 12345)",
        help_text="O código geralmente chega diretamente no app do Telegram ou por SMS."
    )
    parent.wait_window(dialog)
    return dialog.result

def ask_2fa_password(parent) -> Optional[str]:
    """Exibe modal para entrada de senha de Verificação em Duas Etapas (2FA)."""
    dialog = InputModalDialog(
        parent=parent,
        title="Senha de Verificação (2FA)",
        prompt="Sua conta do Telegram possui Verificação em Duas Etapas ativada.",
        placeholder="Digite sua senha de nuvem do Telegram",
        is_password=True,
        help_text="Esta senha é a mesma que você configurou nas configurações de segurança do Telegram."
    )
    parent.wait_window(dialog)
    return dialog.result
