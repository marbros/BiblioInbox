from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/library.db")

# Si es SQLite, aseguramos que el directorio exista
try:
    url = make_url(DATABASE_URL)
    if url.drivername == "sqlite" and url.database:
        db_dir = os.path.dirname(url.database)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
except Exception:
    # Si algo raro pasa al parsear, seguimos sin romper (no es SQLite o URL rara)
    pass

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
