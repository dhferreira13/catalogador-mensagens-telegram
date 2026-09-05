import asyncio
import re
from typing import Optional, Callable, Awaitable
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PasswordHashInvalidError,
    FloodWaitError
)
from src.config import DATA_DIR, TELEGRAM_SESSION_NAME
from src.utils.session_patch import apply_telethon_sqlite_patch

apply_telethon_sqlite_patch()

class TelegramAuthManager:
    """
    Gerenciador de autenticação assíncrona com a MTProto API do Telegram.
    Suporta verificação por código (SMS/Telegram) e senha de 2FA.
    """

    def __init__(self, api_id: int, api_hash: str, phone: str, session_name: Optional[str] = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = re.sub(r'[\s\-\(\)]', '', phone.strip())
        self.session_path = DATA_DIR / (session_name or TELEGRAM_SESSION_NAME)
        self.client = TelegramClient(str(self.session_path), self.api_id, self.api_hash)
        self.phone_code_hash: Optional[str] = None

    async def connect(self) -> bool:
        """Conecta ao servidor do Telegram."""
        if not self.client.is_connected():
            await self.client.connect()
        return await self.client.is_user_authorized()

    async def request_code(self) -> str:
        """
        Envia solicitação de código de login para o número de telefone.
        Retorna o phone_code_hash.
        """
        if not self.client.is_connected():
            await self.client.connect()

        if await self.client.is_user_authorized():
            return "ALREADY_AUTHORIZED"

        sent_code = await self.client.send_code_request(self.phone)
        self.phone_code_hash = sent_code.phone_code_hash
        return self.phone_code_hash

    async def sign_in_with_code(self, code: str) -> str:
        """
        Tenta autenticar com o código recebido via Telegram ou SMS.
        Retorna:
          - 'SUCCESS' se logado com sucesso.
          - '2FA_REQUIRED' se for necessária senha de verificação em duas etapas.
        """
        clean_code = code.strip().replace("-", "").replace(" ", "")
        try:
            await self.client.sign_in(
                phone=self.phone,
                code=clean_code,
                phone_code_hash=self.phone_code_hash
            )
            return "SUCCESS"
        except SessionPasswordNeededError:
            return "2FA_REQUIRED"

    async def sign_in_with_password(self, password: str) -> str:
        """Tenta autenticar com a senha de 2FA."""
        await self.client.sign_in(password=password)
        return "SUCCESS"

    async def is_authorized(self) -> bool:
        """Verifica se a sessão atual está autenticada."""
        if not self.client.is_connected():
            await self.client.connect()
        return await self.client.is_user_authorized()

    async def disconnect(self):
        """Desconecta o cliente de forma segura e libera o arquivo de sessão SQLite."""
        if self.client:
            try:
                if self.client.is_connected():
                    await self.client.disconnect()
            except Exception:
                pass
            try:
                if hasattr(self.client, 'session') and hasattr(self.client.session, 'close'):
                    self.client.session.close()
            except Exception:
                pass
