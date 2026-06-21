from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db.init_db import SessionLocal
from db.models import Engineer, User, Booking, EngineerDayOff
from utils.formatting import format_datetime, get_engineer_name
import datetime

async def engineer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    with SessionLocal() as s:
        eng = s.query(Engineer).join(User).filter(User.id == user.id).first()
    if not eng:
        await query.edit_message_text(
            text="Вы не зарегистрированы как звукорежиссер. Обратитесь к администратору.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]),
        )
        return
    keyboard = [
        [InlineKeyboardButton("📋 Мои записи", callback_data="eng_my_bookings")],
        [InlineKeyboardButton("🗓 Установить выходные", callback_data="eng_set_dayoff")],
        [InlineKeyboardButton("🔍 Свободные слоты", callback_data="eng_free_slots")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ]
    await query.edit_message_text(
        text="Меню звукорежиссера:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def engineer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = update.effective_user
    with SessionLocal() as s:
        eng = s.query(Engineer).join(User).filter(User.id == user.id).first()
    if not eng:
        await query.edit_message_text(
            text="Ошибка: вы не инженер.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]),
        )
        return

    if data == "eng_my_bookings":
        today = datetime.date.today()
        bookings = (
            s.query(Booking)
            .filter(Booking.engineer_id == eng.id, Booking.start_time >= datetime.datetime.combine(today, datetime.time.min))
            .order_by(Booking.start_time)
            .all()
        )
        if not bookings:
            text = "У вас нет предстоящих записей."
        else:
            lines = []
            for b in bookings[:10]:  # ограничим вывод
                lines.append(
                    f"{b.start_time.strftime('%d.%m %H:%M')} – {b.end_time.strftime('%H:%M')} "
                    f"({b.duration_hours} ч) – {b.status}"
                )
            text = "Ваши записи:\n" + "\n".join(lines)
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="engineer_menu")]]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "eng_set_dayoff":
        # простой выбор даты (календарь на 2 месяца вперёд)
        today = datetime.date.today()
        months = []
        for i in range(3):
            month = today.replace(day=1) + datetime.timedelta(days=32*i)
            months.append(month)
        keyboard = []
        for m in months:
            label = m.strftime("%B %Y")
            keyboard.append([InlineKeyboardButton(label, callback_data=f"eng_dayoff:{m.isoformat()}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="engineer_menu")])
        await query.edit_message_text(
            text="Выберите день, который хотите сделать выходным:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("eng_dayoff:"):
        _, iso = data.split(":")
        off_date = datetime.date.fromisoformat(iso)
        with SessionLocal() as s:
            exists = s.query(EngineerDayOff).filter_by(engineer_id=eng.id, off_date=off_date).first()
            if not exists:
                s.add(EngineerDayOff(engineer_id=eng.id, off_date=off_date))
                s.commit()
            await query.edit_message_text(
                text=f"День {off_date.strftime('%d.%m.%Y')} отмечен как выходной.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="engineer_menu")]]),
            )
        return

    if data == "eng_free_slots":
        # попросим выбрать дату, затем покажем слоты
        today = datetime.date.today()
        months = []
        for i in range(3):
            month = today.replace(day=1) + datetime.timedelta(days=32*i)
            months.append(month)
        keyboard = []
        for m in months:
            label = m.strftime("%B %Y")
            keyboard.append([InlineKeyboardButton(label, callback_data=f"eng_free_date:{m.isoformat()}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="engineer_menu")])
        await query.edit_message_text(
            text="Выберите дату, чтобы увидеть свободные слоты:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data.startswith("eng_free_date:"):
        _, iso = data.split(":")
        date = datetime.date.fromisoformat(iso)
        slots = []
        work_start = datetime.time(11, 0)
        work_end = datetime.time(22, 0)
        cur = datetime.datetime.combine(date, work_start)
        while cur < datetime.datetime.combine(date, work_end):
            slots.append(cur)
            cur += datetime.timedelta(minutes=30)
        free = []
        for st in slots:
            et = st + datetime.timedelta(minutes=30)
            if is_slot_free(eng.id, st, et):
                free.append((st, et))
        if not free:
            text = "На этот день свободных слотов нет."
        else:
            lines = [f"{st.strftime('%H:%M')}–{et.strftime('%H:%M')}" for st, et in free[:15]]
            text = "Свободные слоты (шаг 30 мин):\n" + "\n".join(lines)
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="eng_free_slots")]]
        await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # fallback
    await query.edit_message_text(text="Неизвестная команда.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="engineer_menu")]]))