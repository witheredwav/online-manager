from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db.models import Base, Setting
import os
import datetime

def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return create_engine(db_url)
    # fallback to SQLite for local testing
    return create_engine("sqlite:///soundstudio.db")

def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    # заполним базовые настройки, если их нет
    Session = sessionmaker(bind=engine)
    with Session() as s:
        defaults = {
            "work_start": "11:00",
            "work_end": "22:00",
            "slot_step": "30",
            "price_per_hour": "1500",
            "timezone": "Europe/Moscow",
            "studio_rules": "Правила посещения студии:\n1. Не приносить еду и напитки без разрешения.\n2. Бережно относиться к оборудованию.\n3. Приходить вовремя.",
            "studio_contacts": "Телефон: +7 (XXX) XXX-XX-XX\nАдрес: ул. Примерная, д. 1\nГрафик работы: 11:00–22:00",
            "night_booking_allowed": "false",
        }
        for k, v in defaults.items():
            if not s.query(Setting).filter_by(key=k).first():
                s.add(Setting(key=k, value=v))
        s.commit()

def SessionLocal():
    engine = get_engine()
    return sessionmaker(bind=engine)()