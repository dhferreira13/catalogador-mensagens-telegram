from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from src.config import DATABASE_URL
from src.db.models import Base

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 30.0} if is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Inicializa todas as tabelas no banco de dados e adiciona colunas se necessário."""
    Base.metadata.create_all(bind=engine)
    if is_sqlite:
        with engine.connect() as conn:
            try:
                res = conn.exec_driver_sql("PRAGMA table_info(messages)").fetchall()
                col_names = [r[1] for r in res]
                if col_names:
                    if "is_bot" not in col_names:
                        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN is_bot BOOLEAN DEFAULT 0")
                    if "is_admin" not in col_names:
                        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN is_admin BOOLEAN DEFAULT 0")
                    if "media_filename" not in col_names:
                        conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN media_filename VARCHAR(255)")
                    conn.commit()
            except Exception:
                pass

def get_db():
    """Gerenciador de contexto para sessões do banco de dados."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
