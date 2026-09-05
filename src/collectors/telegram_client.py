import asyncio
from datetime import datetime, timezone
import json
from typing import Optional
from src.config import (
    TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE,
    TELEGRAM_SESSION_NAME, TELEGRAM_TARGET_CHAT, DATA_DIR
)
from src.pipeline.filters import parse_date_to_brt, classify_week
from src.pipeline.cleaner import anonymize_user, extract_urls, clean_text_for_nlp
from src.db.session import SessionLocal, init_db
from src.db.models import Message, ContentAnalysis

try:
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError
    from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage
    HAS_TELETHON = True
except ImportError:
    HAS_TELETHON = False

async def run_telethon_collector(target_chat: Optional[str] = None, limit: Optional[int] = None) -> int:
    """
    Coleta mensagens diretamente via API MTProto do Telegram usando Telethon.
    Requer credenciais válidas configuradas no arquivo .env.
    """
    if not HAS_TELETHON:
        raise ImportError("A biblioteca 'telethon' não está instalada. Execute: pip install telethon")

    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        raise ValueError("TELEGRAM_API_ID e TELEGRAM_API_HASH são obrigatórios no arquivo .env para coleta direta.")

    target = target_chat or TELEGRAM_TARGET_CHAT
    if not target:
        raise ValueError("Nenhum canal/grupo alvo especificado.")

    init_db()
    session_path = DATA_DIR / TELEGRAM_SESSION_NAME
    client = TelegramClient(str(session_path), int(TELEGRAM_API_ID), TELEGRAM_API_HASH)

    await client.start(phone=TELEGRAM_PHONE)
    print(f"Conectado ao Telegram! Buscando mensagens em: {target}")

    db = SessionLocal()
    inserted_count = 0

    try:
        entity = await client.get_entity(target)
        chat_title = getattr(entity, 'title', str(target))
        chat_id = str(entity.id)

        async for tg_msg in client.iter_messages(entity, limit=limit):
            if not tg_msg.date:
                continue

            dt_utc = tg_msg.date
            dt_brt = parse_date_to_brt(dt_utc)
            week_label = classify_week(dt_brt)

            # Filtra apenas período eleitoral estipulado
            if not week_label:
                continue

            # Checa existência
            existing = db.query(Message).filter_by(telegram_msg_id=tg_msg.id).first()
            if existing:
                continue

            # Mídia
            media_type = "none"
            if tg_msg.media:
                if isinstance(tg_msg.media, MessageMediaPhoto):
                    media_type = "photo"
                elif isinstance(tg_msg.media, MessageMediaDocument):
                    media_type = "document"
                elif isinstance(tg_msg.media, MessageMediaWebPage):
                    media_type = "web_page"
                else:
                    media_type = "other_media"

            # Remetente anonimizado
            sender_id = tg_msg.sender_id
            anon_id, anon_name = anonymize_user(sender_id)

            text_raw = tg_msg.message or ""
            urls = extract_urls(text_raw)
            text_clean = clean_text_for_nlp(text_raw)

            # Reações
            reactions_dict = {}
            if tg_msg.reactions and hasattr(tg_msg.reactions, "results"):
                for r in tg_msg.reactions.results:
                    emoji = getattr(r.reaction, 'emoticon', str(r.reaction))
                    reactions_dict[emoji] = r.count
            
            reactions_count = sum(reactions_dict.values())

            msg = Message(
                telegram_msg_id=tg_msg.id,
                chat_id=chat_id,
                chat_title=chat_title,
                date_utc=dt_utc.replace(tzinfo=None),
                date_brt=dt_brt,
                week_label=week_label,
                sender_id_anon=anon_id,
                sender_name_anon=anon_name,
                sender_type="user",
                text_raw=text_raw,
                text_clean=text_clean,
                media_type=media_type,
                has_media=media_type != "none",
                is_forward=bool(tg_msg.forward),
                forward_from_name=getattr(tg_msg.forward, 'from_name', None) if tg_msg.forward else None,
                views_count=tg_msg.views or 0,
                forwards_count=tg_msg.forwards or 0,
                reactions_count=reactions_count,
                reactions_json=json.dumps(reactions_dict, ensure_ascii=False) if reactions_dict else None,
                urls_list=json.dumps(urls, ensure_ascii=False) if urls else None
            )

            msg.analysis = ContentAnalysis(status_validacao="Pendente")
            db.add(msg)
            inserted_count += 1

        db.commit()
    except FloodWaitError as e:
        print(f"Rate limit atingido. Aguarde {e.seconds} segundos antes de tentar novamente.")
    finally:
        await client.disconnect()
        db.close()

    return inserted_count
