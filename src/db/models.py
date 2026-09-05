from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_msg_id = Column(Integer, unique=True, nullable=False, index=True)
    chat_id = Column(String(100), nullable=True)
    chat_title = Column(String(255), nullable=True)
    
    date_utc = Column(DateTime, nullable=False)
    date_brt = Column(DateTime, nullable=False, index=True)
    week_label = Column(String(100), nullable=True, index=True)
    
    sender_id_anon = Column(String(100), nullable=True)
    sender_type = Column(String(50), default="user")
    is_bot = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    
    text_raw = Column(Text, nullable=True)
    text_clean = Column(Text, nullable=True)
    
    media_type = Column(String(50), default="none")
    has_media = Column(Boolean, default=False)
    media_filename = Column(String(255), nullable=True)
    
    is_forward = Column(Boolean, default=False)
    forward_from_name = Column(String(255), nullable=True)
    
    views_count = Column(Integer, default=0)
    forwards_count = Column(Integer, default=0)
    reactions_count = Column(Integer, default=0)
    reactions_json = Column(Text, nullable=True)
    urls_list = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relação 1:1 com a análise qualitativa de conteúdo
    analysis = relationship("ContentAnalysis", back_populates="message", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_chat_date", "chat_id", "date_brt"),
    )

    def __repr__(self):
        return f"<Message id={self.id} tg_id={self.telegram_msg_id} date={self.date_brt}>"


class ContentAnalysis(Base):
    __tablename__ = "content_analysis"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), unique=True, nullable=False)
    
    tema_predominante = Column(String(100), nullable=True)
    enquadramento_noticioso = Column(String(100), nullable=True)
    valencia_politica = Column(String(50), nullable=True)
    apelo_credibilidade = Column(String(100), nullable=True)
    
    status_validacao = Column(String(50), default="Pendente")
    observacoes_netnograficas = Column(Text, nullable=True)
    
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    message = relationship("Message", back_populates="analysis")

    def __repr__(self):
        return f"<ContentAnalysis id={self.id} msg_id={self.message_id} status={self.status_validacao}>"
