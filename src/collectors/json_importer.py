import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from src.pipeline.filters import parse_date_to_brt, classify_week
from src.pipeline.cleaner import anonymize_user, extract_urls, clean_text_for_nlp
from src.db.session import SessionLocal, init_db
from src.db.models import Message, ContentAnalysis

def parse_json_export(file_path: Path) -> int:
    """
    Faz o parsing do arquivo 'result.json' exportado pelo Telegram Desktop
    e insere as mensagens filtradas no banco de dados SQLite.
    """
    init_db()
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chat_title = data.get("name", "Chat Desconhecido")
    chat_id = str(data.get("id", ""))
    raw_messages = data.get("messages", [])

    db = SessionLocal()
    inserted_count = 0

    try:
        for item in raw_messages:
            if item.get("type") != "message":
                continue

            # Parsing da data
            date_str = item.get("date")
            if not date_str:
                continue
            
            # Formato padrão da exportação do Telegram Desktop: 'YYYY-MM-DDTHH:MM:SS'
            try:
                dt_utc = datetime.fromisoformat(date_str)
            except Exception:
                continue

            dt_brt = parse_date_to_brt(dt_utc)
            week_label = classify_week(dt_brt)

            # Filtra apenas mensagens das duas semanas de interesse
            if not week_label:
                continue

            telegram_msg_id = item.get("id")
            
            # Verifica se já existe no banco
            existing = db.query(Message).filter_by(telegram_msg_id=telegram_msg_id).first()
            if existing:
                continue

            # Processamento de texto (pode vir como lista de blocos no JSON do Telegram)
            raw_text_obj = item.get("text", "")
            if isinstance(raw_text_obj, list):
                text_parts = []
                for part in raw_text_obj:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict):
                        text_parts.append(part.get("text", ""))
                text_raw = "".join(text_parts)
            else:
                text_raw = str(raw_text_obj)

            # Informações do remetente
            sender_id = item.get("from_id")
            sender_name = item.get("from")
            anon_id, anon_name = anonymize_user(sender_id, sender_name)

            # Mídia
            media_type = item.get("media_type", "none")
            if "photo" in item:
                media_type = "photo"
            elif "file" in item:
                media_type = item.get("mime_type", "document")
            has_media = media_type != "none"

            # Encaminhamento
            is_forward = "forwarded_from" in item
            forward_from_name = item.get("forwarded_from")

            # URLs e limpeza
            urls = extract_urls(text_raw)
            text_clean = clean_text_for_nlp(text_raw)

            # Reações (quando disponíveis na exportação)
            reactions = item.get("reactions", [])
            reactions_count = sum(r.get("count", 0) for r in reactions) if isinstance(reactions, list) else 0

            msg = Message(
                telegram_msg_id=telegram_msg_id,
                chat_id=chat_id,
                chat_title=chat_title,
                date_utc=dt_utc,
                date_brt=dt_brt,
                week_label=week_label,
                sender_id_anon=anon_id,
                sender_name_anon=anon_name,
                sender_type="user" if not item.get("author") else "channel",
                text_raw=text_raw,
                text_clean=text_clean,
                media_type=media_type,
                has_media=has_media,
                is_forward=is_forward,
                forward_from_name=forward_from_name,
                views_count=item.get("views", 0) or 0,
                forwards_count=item.get("forwards", 0) or 0,
                reactions_count=reactions_count,
                reactions_json=json.dumps(reactions, ensure_ascii=False) if reactions else None,
                urls_list=json.dumps(urls, ensure_ascii=False) if urls else None
            )

            # Cria registro vinculado para catalogação qualitativa
            msg.analysis = ContentAnalysis(
                status_validacao="Pendente"
            )

            db.add(msg)
            inserted_count += 1

        db.commit()
    finally:
        db.close()

    return inserted_count
