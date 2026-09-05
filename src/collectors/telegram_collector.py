import os
import re
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    DocumentAttributeAnimated,
    DocumentAttributeVideo
)

from src.utils.paths import get_medias_dir, get_data_dir
from src.utils.session_patch import apply_telethon_sqlite_patch
from src.pipeline.filters import parse_date_to_brt, classify_week
from src.pipeline.cleaner import anonymize_user, extract_urls, clean_text_for_nlp
from src.db.session import SessionLocal, init_db
from src.db.models import Message, ContentAnalysis

apply_telethon_sqlite_patch()

def format_reactions(reactions_obj) -> tuple[int, str, dict]:
    """Extrai total de reações, string formatada e dicionário JSON."""
    if not reactions_obj or not hasattr(reactions_obj, "results") or not reactions_obj.results:
        return 0, "-", {}

    reactions_dict = {}
    formatted_parts = []
    total_count = 0

    for r in reactions_obj.results:
        emoji = getattr(r.reaction, 'emoticon', str(r.reaction))
        count = getattr(r, 'count', 1)
        reactions_dict[emoji] = count
        total_count += count
        formatted_parts.append(f"{emoji} ({count})")

    summary_str = ", ".join(formatted_parts) if formatted_parts else "-"
    return total_count, summary_str, reactions_dict

def get_media_classification(msg) -> tuple[bool, str]:
    """
    Identifica se a mensagem possui mídia e sua classificação
    (Foto, GIF, Imagem, Vídeo, Documento, etc.).
    """
    if not msg.media:
        return False, "Nenhuma"

    if isinstance(msg.media, MessageMediaPhoto) or msg.photo:
        return True, "Foto"

    if msg.gif:
        return True, "GIF"

    if isinstance(msg.media, MessageMediaDocument) and msg.document:
        mime = getattr(msg.document, "mime_type", "").lower()
        if "gif" in mime:
            return True, "GIF"
        if mime.startswith("image/"):
            return True, "Imagem"
        
        # Checa atributos de animação (GIFs do Telegram costumam vir como mp4 animado)
        for attr in getattr(msg.document, "attributes", []):
            if isinstance(attr, DocumentAttributeAnimated):
                return True, "GIF"

        if mime.startswith("video/"):
            return True, "Vídeo"
        return True, "Documento"

    if isinstance(msg.media, MessageMediaWebPage):
        return False, "Nenhuma"

    return True, "Outra Mídia"

async def collect_messages(
    client: TelegramClient,
    target_chat: str,
    start_dt_brt: datetime,
    end_dt_brt: datetime,
    download_media_files: bool = True,
    progress_callback: Optional[Callable[[int, int, int, Optional[datetime], str], None]] = None,
    cancel_event: Optional[asyncio.Event] = None
) -> dict:
    """
    Coleta mensagens de um grupo/canal do Telegram dentro de um intervalo temporal preciso.
    Salva dados no banco SQLite e mídias em output/Mídias com o padrão:
    {Iddamensagem}_{data}_{horário}.{extensao}
    """
    init_db()
    medias_dir = get_medias_dir()

    def report(scanned: int, saved: int, media: int, dt: Optional[datetime], status: str):
        if progress_callback:
            progress_callback(scanned, saved, media, dt, status)

    report(0, 0, 0, None, f"Localizando grupo/canal: '{target_chat}'...")

    # Limpeza do identificador do chat
    target = target_chat.strip()
    if target.startswith("https://t.me/"):
        target = target.replace("https://t.me/", "")
    elif target.startswith("t.me/"):
        target = target.replace("t.me/", "")

    if target.isdigit() or (target.startswith("-") and target[1:].isdigit()):
        target = int(target)

    entity = None
    try:
        entity = await client.get_entity(target)
    except Exception:
        report(0, 0, 0, None, "Localizando grupo através dos diálogos recentes da sua conta...")
        try:
            dialogs = await client.get_dialogs(limit=300)
            target_str = str(target).replace("-100", "").replace("-", "")
            for d in dialogs:
                d_id_str = str(d.id).replace("-100", "").replace("-", "")
                d_user = getattr(d.entity, 'username', '') or ''
                if d_id_str == target_str or d_user.lower() == str(target).replace("@", "").lower():
                    entity = d.entity
                    break
            if not entity:
                entity = await client.get_entity(target)
        except Exception:
            pass

    if not entity:
        raise ValueError(
            f"Não foi possível localizar o grupo/canal '{target_chat}'. "
            f"Verifique se o seu número do Telegram participa desse grupo ou se o link/@username está correto."
        )

    chat_title = getattr(entity, 'title', str(target))
    chat_id = str(getattr(entity, 'id', target))
    is_broadcast_channel = getattr(entity, 'broadcast', False)

    # Identifica administradores do chat/canal
    admin_ids = set()
    try:
        from telethon.tl.types import ChannelParticipantsAdmins
        async for admin_user in client.iter_participants(entity, filter=ChannelParticipantsAdmins):
            admin_ids.add(admin_user.id)
    except Exception:
        pass

    report(0, 0, 0, None, f"Grupo conectado: '{chat_title}'. Iniciando varredura...")

    db = SessionLocal()
    scanned_count = 0
    saved_count = 0
    media_count = 0

    try:
        # Itera mensagens em ordem decrescente (do mais recente para o mais antigo)
        async for tg_msg in client.iter_messages(entity):
            if cancel_event and cancel_event.is_set():
                report(scanned_count, saved_count, media_count, None, "Coleta interrompida pelo usuário.")
                break

            if not tg_msg.date:
                continue

            scanned_count += 1
            dt_utc = tg_msg.date
            dt_brt = parse_date_to_brt(dt_utc)

            # Se a mensagem for mais recente que o limite superior, pula
            if dt_brt > end_dt_brt:
                if scanned_count % 20 == 0:
                    report(scanned_count, saved_count, media_count, dt_brt, "Buscando início do período selecionado...")
                continue

            # Se a mensagem for anterior ao limite inferior, encerra a busca (mensagens mais antigas)
            if dt_brt < start_dt_brt:
                report(scanned_count, saved_count, media_count, dt_brt, "Alcançado o início do período estipulado.")
                break

            # Mensagem dentro do intervalo!
            has_media, media_type = get_media_classification(tg_msg)
            saved_media_filename = None

            # Download de mídia (fotos, imagens, gifs)
            if download_media_files and has_media and media_type in ["Foto", "GIF", "Imagem", "Vídeo"]:
                date_str = dt_brt.strftime("%Y-%m-%d")
                time_str = dt_brt.strftime("%H-%M-%S")
                # Padrão: {Iddamensagem}_{data}_{horário}
                base_name = f"{tg_msg.id}_{date_str}_{time_str}"
                
                # Verifica se o arquivo já foi baixado anteriormente
                existing_files = list(medias_dir.glob(f"{base_name}.*"))
                if existing_files:
                    saved_media_filename = existing_files[0].name
                else:
                    report(scanned_count, saved_count, media_count, dt_brt, f"Baixando mídia da mensagem #{tg_msg.id} ({media_type})...")
                    try:
                        download_dest = str(medias_dir / base_name)
                        downloaded_path = await client.download_media(tg_msg, file=download_dest)
                        if downloaded_path:
                            saved_media_filename = Path(downloaded_path).name
                            media_count += 1
                    except FloodWaitError as fe:
                        report(scanned_count, saved_count, media_count, dt_brt, f"Pausa temporária solicitada pelo Telegram ({fe.seconds}s)...")
                        await asyncio.sleep(fe.seconds + 1)
                        # Tenta novamente
                        try:
                            downloaded_path = await client.download_media(tg_msg, file=download_dest)
                            if downloaded_path:
                                saved_media_filename = Path(downloaded_path).name
                                media_count += 1
                        except Exception:
                            pass
                    except Exception as me:
                        # Falha pontual de download não deve interromper a coleta
                        pass

            # Anonimização estrita do participante (Ética em Pesquisa)
            sender_id = tg_msg.sender_id
            anon_id, _ = anonymize_user(sender_id)

            # Verifica se o autor é bot
            is_bot = False
            sender_obj = None
            try:
                sender_obj = await tg_msg.get_sender()
                if sender_obj and getattr(sender_obj, 'bot', False):
                    is_bot = True
            except Exception:
                pass

            # Verifica se quem enviou/postou no grupo é administrador
            is_admin = False
            if is_broadcast_channel:
                is_admin = True
            elif tg_msg.sender_id and tg_msg.sender_id in admin_ids:
                is_admin = True
            elif tg_msg.sender_id and tg_msg.sender_id == getattr(entity, 'id', None):
                # Administrador anônimo postando como o próprio grupo
                is_admin = True
            elif getattr(tg_msg, 'post', False) or getattr(tg_msg, 'post_author', None):
                is_admin = True
            elif not admin_ids:
                try:
                    if sender_obj and getattr(sender_obj, 'id', None):
                        perms = await client.get_permissions(entity, sender_obj)
                        if perms and getattr(perms, 'is_admin', False):
                            is_admin = True
                            admin_ids.add(sender_obj.id)
                except Exception:
                    pass

            # Tratamento de encaminhamento
            is_forward = bool(tg_msg.forward)
            forward_from_name = None
            if is_forward and tg_msg.forward:
                # Se for canal público, preserva o nome institucional. Se for usuário comum, preserva sigilo.
                if getattr(tg_msg.forward, 'chat', None):
                    forward_from_name = getattr(tg_msg.forward.chat, 'title', 'Canal de Origem')
                elif getattr(tg_msg.forward, 'from_name', None):
                    forward_from_name = "Origem Externa"
                else:
                    forward_from_name = "Mensagem Encaminhada"

            # Reações
            reactions_count, reactions_summary, reactions_dict = format_reactions(tg_msg.reactions)

            text_raw = tg_msg.message or ""
            urls = extract_urls(text_raw)
            text_clean = clean_text_for_nlp(text_raw)
            week_label = classify_week(dt_brt)

            # Salva ou atualiza no banco de dados SQLite
            existing = db.query(Message).filter_by(telegram_msg_id=tg_msg.id).first()
            if existing:
                existing.views_count = tg_msg.views or existing.views_count
                existing.forwards_count = tg_msg.forwards or existing.forwards_count
                existing.reactions_count = reactions_count
                existing.reactions_json = json.dumps(reactions_dict, ensure_ascii=False) if reactions_dict else None
                existing.is_admin = is_admin
                if saved_media_filename:
                    existing.media_filename = saved_media_filename
            else:
                msg_record = Message(
                    telegram_msg_id=tg_msg.id,
                    chat_id=chat_id,
                    chat_title=chat_title,
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
                    urls_list=json.dumps(urls, ensure_ascii=False) if urls else None
                )
                msg_record.analysis = ContentAnalysis(status_validacao="Pendente")
                db.add(msg_record)
                saved_count += 1

            if scanned_count % 10 == 0:
                db.commit()
                report(scanned_count, saved_count, media_count, dt_brt, f"Coletando mensagens ({saved_count} registradas no intervalo)...")

        db.commit()
    except FloodWaitError as fe:
        report(scanned_count, saved_count, media_count, None, f"Telegram solicitou pausa de {fe.seconds}s. Aguardando...")
        await asyncio.sleep(fe.seconds + 1)
    finally:
        db.close()

    report(scanned_count, saved_count, media_count, None, f"Coleta finalizada com sucesso! {saved_count} mensagens salvas, {media_count} mídias baixadas.")

    return {
        "chat_title": chat_title,
        "chat_id": chat_id,
        "scanned_count": scanned_count,
        "saved_count": saved_count,
        "media_count": media_count
    }
