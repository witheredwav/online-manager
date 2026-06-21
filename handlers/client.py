from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db.init_db import SessionLocal
from db.models import User, Engineer, Booking, Setting
from utils.formatting import (
    get_workday_slots,
    is_slot_free,
    format_datetime,
    get_engineer_name,
)
from utils.notifications import notify_new_booking, notify_reminder
import datetime

# --- Вход в бронь ---
async def start_client_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # очистим данные предыдущей брони
    context.user_data.clear()
    # покажем календарь (простой выбор месяцев на 2 вперёд)
    today = datetime.date.today()
    months = []
    for i in range(3):  # текущий + следующие 2
        month = today.replace(day=1) + datetime.timedelta(days=32*i)
        months.append(month)
    keyboard = []
    for m in months:
        label = m.strftime("%B %Y")
        keyboard.append([InlineKeyboardButton(label, callback_data=f"client_date:{m.isoformat()}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
    await query.edit_message_text(
        text="Выберите месяц бронирования:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_DATE

# ---- Дата ----
async def client_date_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, iso = query.data.split(":")
    chosen = datetime.date.fromisoformat(iso)
    context.user_data["date"] = chosen
    # получим список инженеров, у которых нет выходных в этот день
    with SessionLocal() as s:
        engineers = (
            s.query(Engineer)
            .join(User)
            .outerjoin(EngineerDayOff, (Engineer.id == EngineerDayOff.engineer_id) & (EngineerDayOff.off_date == chosen))
            .filter(EngineerDayOff.id.is_(None))  # нет выходного
            .all()
        )
    if not engineers:
        await query.edit_message_text(
            text="На этот день нет доступных звукорежиссёров. Выберите другую дату.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="client_start")]]),
        )
        return CHOOSING_DATE
    keyboard = []
    for eng in engineers:
        name = get_engineer_name(eng)
        keyboard.append([InlineKeyboardButton(name, callback_data=f"client_engineer:{eng.id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="client_start")])
    await query.edit_message_text(
        text="Выберите звукорежиссёра:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_ENGINEER

# ---- Инженер ----
async def client_engineer_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, eng_id = query.data.split(":")
    context.user_data["engineer_id"] = int(eng_id)
    date: datetime.date = context.user_data["date"]
    eng_id = int(eng_id)
    with SessionLocal() as s:
        eng = s.get(Engineer, eng_id)
        # сформировать слоты
        slots = get_workday_slots(date)  # список datetime с шагом 30 мин
        free = []
        for st in slots:
            et = st + datetime.timedelta(minutes=30)
            if is_slot_free(eng_id, st, et):
                free.append((st, et))
    if not free:
        await query.edit_message_text(
            text="На выбранный день у этого инженера нет свободных слотов. Попробуйте другую дату или инженера.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="client_engineer_chosen")]]),
        )
        return CHOOSING_ENGINEER
    # сгруппируем по часам для удобства (покажем только начало слота)
    keyboard = []
    for st, et in free:
        label = st.strftime("%H:%M")
        keyboard.append([InlineKeyboardButton(label, callback_data=f"client_slot:{st.isoformat()}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=f"client_date:{date.isoformat()}")])
    await query.edit_message_text(
        text="Выберите время начала записи (шаг 30 мин):",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_SLOT

# ---- Слот ----
async def client_slot_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, iso = query.data.split(":")
    start_time = datetime.datetime.fromisoformat(iso)
    context.user_data["start_time"] = start_time
    # выбор длительности
    keyboard = [
        [InlineKeyboardButton("1 ч", callback_data="client_duration:1")],
        [InlineKeyboardButton("2 ч", callback_data="client_duration:2")],
        [InlineKeyboardButton("3 ч", callback_data="client_duration:3")],
        [InlineKeyboardButton("4 ч", callback_data="client_duration:4")],
        [InlineKeyboardButton("◀️ Назад", callback_data=f"client_engineer:{context.user_data['engineer_id']}")],
    ]
    await query.edit_message_text(
        text="Выберите длительность записи:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSING_DURATION

# ---- Длительность ----
async def client_duration_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, dur = query.data.split(":")
    context.user_data["duration"] = int(dur)
    # показать правила
    rules = get_setting("studio_rules") or "Правила посещения студии:\n1. Не приносить еду и напитки без разрешения.\n2. Бережно относиться к оборудованию.\n3. Приходить вовремя."
    keyboard = [
        [InlineKeyboardButton("✅ Я согласен с правилами", callback_data="client_rules_yes")],
        [InlineKeyboardButton("❌ Не согласен", callback_data="client_rules_no")],
    ]
    await query.edit_message_text(
        text=rules,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return SHOWING_RULES

# ---- Правила приняты ----
async def client_rules_accepted(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="Введите ваше имя:")
    return ENTERING_NAME

# ---- Ввод имени ----
async def client_info_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    step = context.user_data.get("info_step")
    if step is None:
        # имя
        context.user_data["client_name"] = text
        context.user_data["info_step"] = "visitors"
        await update.message.reply_text("Сколько человек будет посещать студию? (целое число ≥1)")
        return ENTERING_VISITORS
    elif step == "visitors":
        if not text.isdigit() or int(text) < 1:
            await update.message.reply_text("Пожалуйста, введите целое число ≥1.")
            return ENTERING_VISITORS
        context.user_data["visitors"] = int(text)
        context.user_data["info_step"] = "phone"
        await update.message.reply_text("Введите ваш телефон (для связи):")
        return ENTERING_PHONE
    elif step == "phone":
        context.user_data["phone"] = text
        # переходим к подтверждению
        await show_confirmation(update, context)
        return CONFIRM_BOOKING
    return ENTERING_NAME  # fallback

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    date: datetime.date = context.user_data["date"]
    start: datetime.datetime = context.user_data["start_time"]
    dur: int = context.user_data["duration"]
    end = start + datetime.timedelta(hours=dur)
    eng_id: int = context.user_data["engineer_id"]
    with SessionLocal() as s:
        eng = s.get(Engineer, eng_id)
        eng_name = get_engineer_name(eng)
        price_per_hour = float(get_setting("price_per_hour") or "1000")
        price = price_per_hour * dur
    text = (
        f"📅 *Дата:* {date.strftime('%d.%m.%Y')}\n"
        f"⏰ *Время:* {start.strftime('%H:%M')} – {end.strftime('%H:%M')} ({dur} ч)\n"
        f"👨‍🎧 *Звукорежиссер:* {eng_name}\n"
        f"👤 *Имя:* {context.user_data['client_name']}\n"
        f"👥 *Посетителей:* {context.user_data['visitors']}\n"
        f"📞 *Телефон:* {context.user_data['phone']}\n"
        f"💰 *Стоимость:* {format_price(price)} руб.\n\n"
        f"Все верно?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить бронь", callback_data="client_confirm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="client_cancel")],
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

# ---- Подтверждение брони ----
async def client_confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    date: datetime.date = context.user_data["date"]
    start: datetime.datetime = context.user_data["start_time"]
    dur: int = context.user_data["duration"]
    end = start + datetime.timedelta(hours=dur)
    eng_id: int = context.user_data["engineer_id"]
    visitors = context.user_data["visitors"]
    phone = context.user_data["phone"]
    name = context.user_data["client_name"]
    # проверяем доступность ещё раз
    with SessionLocal() as s:
        if not is_slot_free(eng_id, start, end):
            await query.edit_message_text(
                text="К сожалению, этот slot уже занят. Выберите другое время.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=f"client_engineer:{eng_id}")]]),
            )
            return CHOOSING_SLOT
        price_per_hour = float(get_setting("price_per_hour") or "1000")
        price = price_per_hour * dur
        # определяем статус
        status = "подтверждено" if dur < 3 else "ожидает подтверждения"
        booking = Booking(
            client_id=user.id,
            engineer_id=eng_id,
            start_time=start,
            end_time=end,
            duration_hours=dur,
            status=status,
            price=price,
        )
        s.add(booking)
        s.commit()
        booking_id = booking.id
        engineer = s.get(Engineer, eng_id)
        engineer_user = s.get(User, engineer.user_id)
    # уведомления
    await notify_new_booking(context.application, booking_id, engineer_user.id if engineer_user else None)
    # напоминание за 2 часа
    context.application.create_task(
        schedule_reminder(context.application, booking_id, start - datetime.timedelta(hours=2))
    )
    # выводим результат
    engineer_name = get_engineer_name(engineer)
    eng_phone = get_setting(f"engineer_{engineer_user.id}_phone") or "не указан"
    eng_tg = f"@{engineer_user.username}" if engineer_user.username else "не указан"
    text = (
        f"✅ Бронь создана!\n\n"
        f"📅 {date.strftime('%d.%m.%Y')} {start.strftime('%H:%M')}–{end.strftime('%H:%M')}\n"
        f"👨‍🎧 Звукорежиссер: {engineer_name}\n"
        f"📞 Контакт инженера: {eng_phone} / {eng_tg}\n"
        f"💰 Стоимость: {format_price(price)} руб.\n"
        f"📋 Статус: {status}\n\n"
        f"Свяжитесь со звукорежиссёром для уточнения деталей."
    )
    keyboard = [
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")],
    ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    # очистка
    context.user_data.clear()
    return ConversationHandler.END

# ---- Отмена на любом этапе ----
async def client_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Бронирование отменено.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]]),
    )
    context.user_data.clear()
    return ConversationHandler.END

# ---- Фоновая задача напоминания ----
import asyncio
async def schedule_reminder(app: Application, booking_id: int, when: datetime.datetime):
    now = datetime.datetime.now()
    delay = (when - now).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
    # получаем запись и отправляем напоминание
    from db.init_db import SessionLocal
    from db.models import Booking, User
    with SessionLocal() as s:
        booking = s.get(Booking, booking_id)
        if not booking or booking.status not in ("подтверждено", "ожидает подтверждения"):
            return
        client = s.get(User, booking.client_id)
        engineer = s.get(User, booking.engineer.user_id) if booking.engineer else None
    if client:
        await app.bot.send_message(
            chat_id=client.id,
            text=f"⏰ Напоминание: ваша запись через 2 часа ({booking.start_time.strftime('%H:%M')}).",
        )
    if engineer:
        await app.bot.send_message(
            chat_id=engineer.id,
            text=f"⏰ Напоминание: у вас запись через 2 часа ({booking.start_time.strftime('%H:%M')}).",
        )