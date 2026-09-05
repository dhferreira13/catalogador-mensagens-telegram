import sys
import asyncio
import customtkinter as ctk
from typing import Optional

from src.utils.logger import setup_logging
from src.collectors.telegram_auth import TelegramAuthManager
from src.gui.screens.credentials_screen import CredentialsScreen
from src.gui.screens.collection_screen import CollectionScreen

class TelegramTCCApp(ctk.CTk):
    """
    Janela Principal do Aplicativo Desktop de Coleta e Catalogação de Mensagens do Telegram.
    """
    def __init__(self):
        setup_logging()
        super().__init__()

        # Configurações Visuais Globais (UX/UI Designer)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Catalogador de Mensagens do Telegram")
        try:
            from src.utils.paths import get_app_icon_path
            icon_file = get_app_icon_path()
            if icon_file.exists():
                self.iconbitmap(str(icon_file))
        except Exception:
            pass

        self.geometry("920x730")
        self.minsize(860, 650)

        # Centraliza a janela na tela
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - 920) // 2
        y = (screen_height - 730) // 2
        self.geometry(f"920x730+{x}+{y}")

        self.auth_manager: Optional[TelegramAuthManager] = None

        # Container para alternância de telas
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.screen_credentials = CredentialsScreen(
            self.container,
            on_success_callback=self.show_collection_screen
        )
        self.screen_collection = CollectionScreen(
            self.container,
            on_back_callback=self.show_credentials_screen
        )

        # Inicia na Tela 1
        self.show_credentials_screen()

        # Intercepta fechamento da janela para desconectar cliente
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def show_credentials_screen(self):
        """Exibe a Tela 1 (Credenciais e Tutorial)."""
        self.screen_collection.pack_forget()
        self.screen_credentials.pack(fill="both", expand=True)

    def show_collection_screen(self, auth_manager: TelegramAuthManager, creds: dict):
        """Exibe a Tela 2 (Coleta, Filtro de Datas, Relógio e Pasta Output)."""
        self.auth_manager = auth_manager
        self.screen_collection.set_auth_manager(auth_manager)
        self.screen_credentials.pack_forget()
        self.screen_collection.pack(fill="both", expand=True)

    def _on_close(self):
        """Finalização segura."""
        if self.auth_manager:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.auth_manager.disconnect())
                loop.close()
            except Exception:
                pass
        self.destroy()

def run_gui():
    """Ponto de entrada para execução da interface gráfica."""
    app = TelegramTCCApp()
    app.mainloop()

if __name__ == "__main__":
    run_gui()
