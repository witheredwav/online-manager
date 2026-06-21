from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from db.init_db import SessionLocal
from db.models import Booking, User
import asyncio

async def notify_new_booking(application, booking_id: int, engineer_tg_id: int | None = None):
    with SessionLocal() as s:
        booking = s.get(Booking, booking_id)
        if not booking:
            return
        client = s.get(User, booking.client_id)
        engineer = s.get(User, booking.engineer.user_id) if booking.engineer else None
    text_client = f"✅ Ваша бронь на {booking.start_time.strftime('%d.%m %H:%M')}–{booking.end_time.strftime('%H:%M')} создана. Статус: {booking.status}."
    text_eng = f"🔔 Новая бронь: клиент {client.full_name if client else 'неизвестен'} на {booking.start_time.strftime('%d.%m %H:%M')}–{booking.end_time.strftime('%H:%M')} ({booking.duration_hours} ч). Статус: {booking.status}."
    try:
        await application.bot.send_message(chat_id=client.id, text=text_client)
    except Exception:
        pass
    if engineer:
        try:
            await application.bot.send_message(chat_id=engineer.id, text=text_eng)
        except Exception:
            pass
    # также уведомляем всех админов из settings
    admin_ids_str = s.query(Setting).filter_by(key="admin_ids").first()
    if admin_ids_str and admin_ids_str.value:
        for aid in map(int, admin_ids_str.value.split(",")):
            if aid != client.id and aid != (engineer.id if engineer else None):
                try:
                    await application.bot.send_message(chat_id=aid, text=text_eng)
                except Exception:
                    pass

async def notify_reminder(application, booking_id: int, when: datetime.datetime):
    # вызывается из scheduler в client.py
    await asyncio.sleep((when - datetime.datetime.now()).total_seconds())
    with SessionLocal() as s:
        booking = s.get(Booking, booking_id)
        if not booking or booking.status not in ("подтверждено", "ожидает подтверждения"):
            return
        client = s.get(User, booking.client_id)
        engineer = s.get(User, booking.engineer.user_id) if booking.engineer else None
    text = f"⏰ Напоминание: ваша запись через 2 часа ({booking.start_time.strftime('%H:%M')})."
    if client:
        try:
            await application.bot.send_message(chat_id=client.id, text=text)
        except Exception:
            pass
    if engineer:
        try:
            await application.bot.send_message(chat_id=engineer.id, text=text)
        except Exception:
            pass

async def notify_review_request(application, booking_id: int):
    with SessionLocal() as s:
        booking = s.get(Booking, booking_id)
        if not booking or booking.status != "завершено":
            return
        client = s.get(User, booking.client_id)
    text = "Спасибо, что воспользовались нашей студией! Пожалуйста, оцените сессию от 1 до 5 и, если хотите, оставьте комментарий."
    keyboard = [
        [
            InlineKeyboardButton("1⭐", callback_data=f"review:{booking_id}:1"),
            InlineKeyboardButton("2⭐", callback_data=f"review:{booking_id}:2"),
            InlineKeyboardButton("3⭐", callback_data=f"review:{booking_id}:3"),
            InlineKeyboardButton("4⭐", callback_data=f"review:{booking_id}:4"),
            InlineKeyboardButton("5⭐", callback_data=f"review:{booking_id}:5"),
        ]
    ]
    try:
        await application.bot.send_message(chat_id=client.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        pass