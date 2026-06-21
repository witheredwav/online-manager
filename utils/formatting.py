import datetime
from db.init_db import SessionLocal
from db.models import Booking, Engineer

def format_datetime(dt: datetime.datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")

def format_price(price: float) -> str:
    return f"{price:,.0f}".replace(",", " ")

def get_workday_slots(day: datetime.date):
    """Возвращает список datetime начала слотов (шаг 30 мин) для рабочего дня."""
    start_h = int(os.getenv("WORK_START", "11").split(":")[0]) if ":" in os.getenv("WORK_START", "11") else 11
    start_m = int(os.getenv("WORK_START", "11").split(":")[1]) if ":" in os.getenv("WORK_START", "11") else 0
    end_h = int(os.getenv("WORK_END", "22").split(":")[0]) if ":" in os.getenv("WORK_END", "22") else 22
    end_m = int(os.getenv("WORK_END", "22").split(":")[1]) if ":" in os.getenv("WORK_END", "22") else 0
    tz = datetime.timezone(datetime.timedelta(hours=int(os.getenv("TZ_OFFSET", "3"))))  # упрощённо
    start = datetime.datetime.combine(day, datetime.time(start_h, start_m), tzinfo=tz)
    end = datetime.datetime.combine(day, datetime.time(end_h, end_m), tzinfo=tz)
    step = int(os.getenv("SLOT_STEP", "30"))
    slots = []
    cur = start
    while cur < end:
        slots.append(cur)
        cur += datetime.timedelta(minutes=step)
    return slots

def is_slot_free(engineer_id: int, start: datetime.datetime, end: datetime.datetime) -> bool:
    with SessionLocal() as s:
        overlapping = (
            s.query(Booking)
            .filter(
                Booking.engineer_id == engineer_id,
                Booking.start_time < end,
                Booking.end_time > start,
                Booking.status.in_(["ожидает подтверждения", "подтверждено"]),
            )
            .first()
        )
        return overlapping is None

def get_engineer_name(eng):
    if eng.user.full_name:
        return eng.user.full_name
    return eng.user.username or f"Инженер {eng.id}"