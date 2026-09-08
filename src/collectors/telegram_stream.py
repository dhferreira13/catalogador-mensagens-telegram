import os
import sys
import json
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Callable

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from sqlalchemy import func

from src.utils.paths import get_medias_dir, get_media_subfolder, get_media_subfolder_name, get_base_dir
from src.utils.session_patch import apply_telethon_sqlite_patch
from src.pipeline.filters import parse_date_to_brt, classify_week, BRT
from src.pipeline.cleaner import anonymize_user, extract_urls, clean_text_for_nlp
from src.collectors.telegram_collector import get_media_classification, format_reactions
from src.db.session import SessionLocal, init_db
from src.db.models import Message, ContentAnalysis
from src.exporter.excel_exporter import export_to_tcc_spreadsheet

apply_telethon_sqlite_patch()

class TelegramStreamCollector:
    """
    Gerenciador de Coleta Contínua em Tempo Real do Telegram.
    Captura mensagens no momento em que são enviadas, baixa mídias imediatamente
    em subpastas diárias e consolida a planilha Excel às 23:59:59 (BRT).
    """

    def __init__(
        self,
        client: TelegramClient,
        target_chat: str,
        on_message_callback: Optional[Callable[[dict], None]] = None,
        on_export_callback: Optional[Callable[[str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        download_media: bool = True
    ):
        self.client = client
        self.target_chat = target_chat
        self.on_message_cb = on_message_callback
        self.on_export_cb = on_export_callback
        self.log_cb = log_callback or print
        self.download_media = download_media

        self.is_running = False
        self.entity = None
        self.chat_id_str = None
        self.chat_title = None
        self.admin_ids = set()
        self.is_broadcast = False
        self._rollover_task = None

        # Estatísticas diárias
        self.today_date = datetime.now(BRT).date()
        self.today_messages_count = 0
        self.today_media_count = 0

    def log(self, msg: str):
        self.log_cb(f"[{datetime.now(BRT).strftime('%d/%m/%Y %H:%M:%S')}] {msg}")

    async def initialize_entity(self):
        """Identifica e valida o canal/grupo alvo."""
        self.log(f"Localizando grupo/canal: '{self.target_chat}'...")
        try:
            target_int = int(self.target_chat)
            self.entity = await self.client.get_entity(target_int)
        except (ValueError, TypeError):
            self.entity = await self.client.get_entity(self.target_chat)

        self.chat_id_str = str(self.entity.id)
        self.chat_title = getattr(self.entity, 'title', None) or getattr(self.entity, 'username', None) or str(self.entity.id)
        self.is_broadcast = getattr(self.entity, 'broadcast', False)

        # Mapeia administradores conhecidos
        try:
            from telethon.tl.types import ChannelParticipantsAdmins
            admins = await self.client.get_participants(self.entity, filter=ChannelParticipantsAdmins())
            self.admin_ids = {a.id for a in admins}
            self.log(f"Administradores identificados: {len(self.admin_ids)}")
        except Exception:
            self.admin_ids = set()

        self.log(f"Canal/Grupo pronto para escuta: '{self.chat_title}' (ID: {self.chat_id_str})")

    async def process_single_message(self, tg_msg) -> Optional[dict]:
        """
        Processa, higieniza, baixa mídias e persiste uma mensagem individual no SQLite.
        """
        if not tg_msg:
            return None

        dt_utc = tg_msg.date
        dt_brt = parse_date_to_brt(dt_utc)

        # Atualiza contadores diários se mudou de dia
        current_date = dt_brt.date()
        if current_date != self.today_date:
            self.today_date = current_date
            self.today_messages_count = 0
            self.today_media_count = 0

        # Subpasta de mídias diária: Mídias DD-MM
        day_start = datetime.combine(current_date, datetime.min.time())
        day_end = datetime.combine(current_date, datetime.max.time().replace(microsecond=0))
        target_media_dir = get_media_subfolder(day_start, day_end)
        media_subfolder_name = target_media_dir.name
        medias_root_dir = get_medias_dir()

        has_media, media_type = get_media_classification(tg_msg)
        saved_media_filename = None
        downloaded_media = False

        # Download de arquivos/mídias sem limitações de MB ou tempo
        if self.download_media and has_media and media_type != "Nenhuma":
            date_str = dt_brt.strftime("%Y-%m-%d")
            time_str = dt_brt.strftime("%H-%M-%S")
            base_name = f"{tg_msg.id}_{date_str}_{time_str}"

            # Verifica se já existe
            existing = list(target_media_dir.glob(f"{base_name}.*"))
            if existing:
                saved_media_filename = f"{media_subfolder_name}/{existing[0].name}"
            else:
                legacy = list(medias_root_dir.glob(f"{base_name}.*"))
                if legacy:
                    saved_media_filename = legacy[0].name
                else:
                    self.log(f"Baixando mídia instantânea #{tg_msg.id} ({media_type}) em '{media_subfolder_name}'...")
                    download_dest = str(target_media_dir / base_name)
                    try:
                        downloaded_path = await self.client.download_media(tg_msg, file=download_dest)
                        if downloaded_path:
                            saved_media_filename = f"{media_subfolder_name}/{Path(downloaded_path).name}"
                            self.today_media_count += 1
                            downloaded_media = True
                    except FloodWaitError as fe:
                        self.log(f"Pausa temporária do Telegram ({fe.seconds}s)...")
                        await asyncio.sleep(fe.seconds + 1)
                        try:
                            downloaded_path = await self.client.download_media(tg_msg, file=download_dest)
                            if downloaded_path:
                                saved_media_filename = f"{media_subfolder_name}/{Path(downloaded_path).name}"
                                self.today_media_count += 1
                                downloaded_media = True
                        except Exception:
                            pass
                    except Exception as e:
                        self.log(f"Aviso ao baixar mídia #{tg_msg.id}: {e}")

        # Anonimização estrita do participante (LGPD e CNS 510/2016)
        sender_id = tg_msg.sender_id
        anon_id, _ = anonymize_user(sender_id)

        is_bot = False
        sender_obj = None
        try:
            sender_obj = await tg_msg.get_sender()
            if sender_obj and getattr(sender_obj, 'bot', False):
                is_bot = True
        except Exception:
            pass

        is_admin = False
        if self.is_broadcast:
            is_admin = True
        elif tg_msg.sender_id and tg_msg.sender_id in self.admin_ids:
            is_admin = True
        elif tg_msg.sender_id and tg_msg.sender_id == getattr(self.entity, 'id', None):
            is_admin = True
        elif getattr(tg_msg, 'post', False) or getattr(tg_msg, 'post_author', None):
            is_admin = True

        # Encaminhamentos
        is_forward = bool(tg_msg.forward)
        forward_from_name = None
        if is_forward and tg_msg.forward:
            if getattr(tg_msg.forward, 'chat', None):
                forward_from_name = getattr(tg_msg.forward.chat, 'title', 'Canal de Origem')
            elif getattr(tg_msg.forward, 'from_name', None):
                forward_from_name = "Origem Externa"
            else:
                forward_from_name = "Mensagem Encaminhada"

        reactions_count, reactions_summary, reactions_dict = format_reactions(tg_msg.reactions)
        text_raw = tg_msg.message or ""
        urls = extract_urls(text_raw)
        text_clean = clean_text_for_nlp(text_raw)
        week_label = classify_week(dt_brt)

        # Gravação imediata no SQLite
        db = SessionLocal()
        try:
            existing_db = db.query(Message).filter_by(telegram_msg_id=tg_msg.id).first()
            if existing_db:
                existing_db.views_count = tg_msg.views or existing_db.views_count
                existing_db.forwards_count = tg_msg.forwards or existing_db.forwards_count
                existing_db.reactions_count = reactions_count
                existing_db.reactions_json = json.dumps(reactions_dict, ensure_ascii=False) if reactions_dict else None
                existing_db.is_admin = is_admin
                if saved_media_filename:
                    existing_db.media_filename = saved_media_filename
                db.commit()
            else:
                msg_record = Message(
                    telegram_msg_id=tg_msg.id,
                    chat_id=self.chat_id_str,
                    chat_title=self.chat_title,
                    date_utc=dt_utc.replace(tzinfo=None),
                    date_brt=dt_brt,
                    week_label=week_label or "Período Personalizado",
                    sender_id_anon=anon_id,
                    sender_type="bot" if is_bot else "user",
                    is_bot=is_bot,
                    is_admin=is_admin,
                    text_raw=text_raw,
                    text_clean=text_clean,
                    media_type=media_type,
                    has_media=has_media,
                    media_filename=saved_media_filename,
                    is_forward=is_forward,
                    forward_from_name=forward_from_name,
                    views_count=tg_msg.views or 0,
                    forwards_count=tg_msg.forwards or 0,
                    reactions_count=reactions_count,
                    reactions_json=json.dumps(reactions_dict, ensure_ascii=False) if reactions_dict else None,
                    urls_list=json.dumps(urls, ensure_ascii=False) if urls else None,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                msg_record.analysis = ContentAnalysis(
                    status_validacao="Pendente",
                    updated_at=datetime.now(timezone.utc).replace(tzinfo=None)
                )
                db.add(msg_record)
                db.commit()
                self.today_messages_count += 1
        except Exception as dbe:
            db.rollback()
            self.log(f"Erro ao salvar mensagem #{tg_msg.id} no banco: {dbe}")
        finally:
            db.close()

        info = {
            "msg_id": tg_msg.id,
            "date_brt_str": dt_brt.strftime("%d/%m/%Y %H:%M:%S"),
            "date_brt": dt_brt,
            "is_bot": "Sim" if is_bot else "Não",
            "is_admin": "Sim" if is_admin else "Não",
            "is_forward": "Sim" if is_forward else "Não",
            "forward_from": forward_from_name or "-",
            "has_media": "Sim" if has_media else "Não",
            "media_type": media_type if has_media else "Nenhuma",
            "media_file": saved_media_filename or "-",
            "views": tg_msg.views or 0,
            "reactions_count": reactions_count,
            "reactions": reactions_summary or "-",
            "text": text_raw or "",
            "text_preview": text_raw[:60].replace("\n", " "),
            "sender_anon": anon_id or "Participante_Anon",
            "urls": ", ".join(urls) if urls else "-",
            "today_messages": self.today_messages_count,
            "today_media": self.today_media_count
        }

        if self.on_message_cb:
            try:
                self.on_message_cb(info)
            except Exception:
                pass

        return info

    async def sync_gap_messages(self):
        """
        Verifica a última mensagem registrada no banco e recupera qualquer mensagem
        postada enquanto o aplicativo esteve desligado ou desconectado.
        """
        init_db()
        db = SessionLocal()
        max_id = None
        try:
            res = db.query(func.max(Message.telegram_msg_id)).filter_by(chat_id=self.chat_id_str).scalar()
            max_id = res
        finally:
            db.close()

        if not max_id:
            self.log("Nenhum histórico prévio encontrado para sincronização de lacuna. Modo tempo real ativado.")
            return

        self.log(f"Verificando mensagens recebidas durante período offline (último ID registrado: #{max_id})...")
        gap_count = 0
        try:
            # Pede mensagens mais recentes que max_id
            async for tg_msg in self.client.iter_messages(self.entity, min_id=max_id, reverse=True):
                await self.process_single_message(tg_msg)
                gap_count += 1
            if gap_count > 0:
                self.log(f"Sincronização de lacuna concluída: {gap_count} mensagens recuperadas!")
            else:
                self.log("Banco de dados 100% atualizado. Nenhuma mensagem pendente no período offline.")
        except Exception as e:
            self.log(f"Aviso durante sincronização de lacuna: {e}")

    async def _daily_rollover_loop(self):
        """
        Monitora a virada do dia (23:59:59 BRT) e consolida a planilha Excel do dia anterior.
        """
        while self.is_running:
            now_brt = datetime.now(BRT)
            # Próximo fechamento às 23:59:59
            target_time = now_brt.replace(hour=23, minute=59, second=59, microsecond=0)
            if now_brt >= target_time:
                # Se já passou das 23:59:59, mira nas 23:59:59 do dia seguinte
                target_time += timedelta(days=1)

            seconds_to_wait = (target_time - now_brt).total_seconds()
            self.log(f"Próximo fechamento diário programado para {target_time.strftime('%d/%m/%Y às %H:%M:%S')} (em {int(seconds_to_wait // 3600)}h {int((seconds_to_wait % 3600) // 60)}m).")

            # Aguarda até o fechamento (em fatias de até 30s para permitir cancelamento limpo)
            while self.is_running and datetime.now(BRT) < target_time:
                await asyncio.sleep(min(30, (target_time - datetime.now(BRT)).total_seconds()))

            if not self.is_running:
                break

            # Executa fechamento diário
            closed_day = (datetime.now(BRT) - timedelta(seconds=10)).date()
            start_dt = datetime.combine(closed_day, datetime.min.time())
            end_dt = datetime.combine(closed_day, datetime.max.time().replace(microsecond=0))

            self.log(f"⏰ [VIRADA DE DIA 23:59:59] Consolidando planilha Excel de {closed_day.strftime('%d/%m/%Y')}...")
            try:
                excel_path = export_to_tcc_spreadsheet(
                    chat_id=self.chat_id_str,
                    chat_title=self.chat_title,
                    start_dt=start_dt,
                    end_dt=end_dt
                )
                self.log(f"✅ Planilha do dia gerada com sucesso: {excel_path}")
                if self.on_export_cb:
                    self.on_export_cb(excel_path)
            except Exception as exp_err:
                self.log(f"❌ Erro ao gerar planilha do dia: {exp_err}")

            # Pequena pausa para garantir passagem de segundo
            await asyncio.sleep(5)

    def trigger_manual_export(self) -> Optional[str]:
        """Permite exportar a planilha do dia atual sob demanda (ex: via menu da bandeja)."""
        today = datetime.now(BRT).date()
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.now(BRT)
        self.log(f"Exportando planilha parcial do dia ({today.strftime('%d/%m/%Y')})...")
        try:
            excel_path = export_to_tcc_spreadsheet(
                chat_id=self.chat_id_str,
                chat_title=self.chat_title,
                start_dt=start_dt,
                end_dt=end_dt
            )
            self.log(f"Planilha parcial gerada com sucesso: {excel_path}")
            return excel_path
        except Exception as e:
            self.log(f"Erro ao exportar planilha parcial: {e}")
            return None

    async def start(self):
        """Inicia a escuta de eventos em tempo real."""
        init_db()
        await self.initialize_entity()
        self.is_running = True

        # Sincroniza lacuna prévia
        await self.sync_gap_messages()

        # Registra manipulador de novos eventos
        @self.client.on(events.NewMessage(chats=self.entity))
        async def new_message_handler(event):
            try:
                res = await self.process_single_message(event.message)
                if res:
                    m_label = f"[{res['media_type']}]" if res['has_media'] else ""
                    self.log(f"📥 [Nova Mensagem #{res['msg_id']}] {res['sender_anon']} {m_label}: {res['text_preview']}")
            except Exception as err:
                self.log(f"Erro no processamento da mensagem em tempo real: {err}")

        self.log("🟢 COLETOR EM TEMPO REAL ATIVO! Aguardando postagens no grupo...")

        # Inicia o loop de fechamento diário
        self._rollover_task = asyncio.create_task(self._daily_rollover_loop())

        # Mantém vivo enquanto is_running for True
        while self.is_running:
            await asyncio.sleep(1)

    def stop(self):
        """Encerra a coleta contínua de forma graciosa."""
        self.log("Encerrando coletor em tempo real...")
        self.is_running = False
        if self._rollover_task:
            self._rollover_task.cancel()
