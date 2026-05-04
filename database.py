from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./manufacturing.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL;"))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    Base.metadata.create_all(bind=engine)
    from models import Inventory
    db = SessionLocal()
    try:
        if db.query(Inventory).count() == 0:
            db.add(Inventory(product_name="Widget", quantity=10))
            db.add(Inventory(product_name="Gadget", quantity=100))
            db.add(Inventory(product_name="SLOW", quantity=999))
            db.add(Inventory(product_name="NETFAIL", quantity=999))
            db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
