from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes
from db.init_db import SessionLocal
from db.models import User, Engineer, Booking, Setting, EngineerDayOff, Review
from utils.formatting import format_datetime, get_engineer_name, is_slot_free
import io
import datetime
import os
from openpyxl import Workbook

ADMIN_IDS = set(int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if not is_admin(user.id):
        await query.edit_message_text(
            text="У вас нет прав администратора.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]),
        )
        return
    keyboard = [
        [InlineKeyboardButton("👷 Добавить звукорежиссера", callback_data="adm_add_engineer")],
        [InlineKeyboardButton("🛠 Добавить админа", callback_data="adm_add_admin")],
        [InlineKeyboardButton("📋 Список всех записей", callback_data="adm_list_bookings")],
        [InlineKeyboardButton("📊 Статистика за месятц", callback_data="adm_month_stats")],
        [InlineKeyboardButton("📤 Экспорт отчёта", callback_data="adm_export_report")],
        [InlineKeyboardButton("👥 Наша команда", callback_data="adm_team_menu")],
        [InlineKeyboardButton("📞 Контакты студии", callback_data="adm_contacts_menu")],
        [InlineKeyboardButton("💬 Отзывы", callback_data="adm_reviews_menu")],
        [InlineKeyboardButton("🌙 Ночная запись", callback_data="adm_night_booking")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")],
    ]
    await query.edit_message_text(text="Админ‑панель:", reply_markup=InlineKeyboardMarkup(keyboard))

# ----------------- Добавление инженера -----------------
async def adm_add_engineer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Перешлите сообщение от пользователя, которого хотите сделать звукорежиссёром, или пришлите его Telegram‑ID.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")]]),
    )
    context.user_data["awaiting"] = "engineer_id"
    return

# ----------------- Добавление админа -----------------
async def adm_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Перешлите сообщение от пользователя, которого хотите сделать админом, или пришлите его Telegram‑ID.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")]]),
    )
    context.user_data["awaiting"] = "admin_id"
    return

# ----------------- Список всех записей -----------------
async def adm_list_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with SessionLocal() as s:
        bookings = s.query(Booking).order_by(Booking.start_time.desc()).limit(20).all()
    if not bookings:
        text = "Записей пока нет."
    else:
        lines = []
        for b in bookings:
            lines.append(
                f"#{b.id} {b.start_time.strftime('%d.%m %H:%M')}–{b.end_time.strftime('%H:%M')} "
                f"({b.duration_hours} ч) – {b.status} – инж. {b.engineer_id}"
            )
        text = "Последние записи:\n" + "\n".join(lines)
    keyboard = [
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")],
        [InlineKeyboardButton("⚙️ Изменить статус", callback_data="adm_change_status")],
    ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return

# ----------------- Статистика -----------------
async def adm_month_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = datetime.date.today()
    first_day = datetime.date(today.year, today.month, 1)
    if today.month == 12:
        next_first = datetime.date(today.year+1, 1, 1)
    else:
        next_first = datetime.date(today.year, today.month+1, 1)
    with SessionLocal() as s:
        bookings = (
            s.query(Booking)
            .filter(Booking.start_time >= datetime.datetime.combine(first_day, datetime.time.min),
                    Booking.start_time < datetime.datetime.combine(next_first, datetime.time.min))
            .all()
        )
    if not bookings:
        text = "Записей за текущий месяц нет."
    else:
        total_hours = sum(b.duration_hours for b in bookings)
        total_income = sum(b.price or 0 for b in bookings)
        unique_clients = len({b.client_id for b in bookings})
        text = (
            f"📊 Статистика за {today.strftime('%B %Y')}\n"
            f"🗓 Записей: {len(bookings)}\n"
            f"⏱ Общее время: {total_hours} ч\n"
            f"💰 Выручка: {total_income:.0f} руб.\n"
            f"👥 Уникальных клиентов: {unique_clients}"
        )
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return

# ----------------- Экспорт отчёта -----------------
async def adm_export_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    today = datetime.date.today()
    first_day = datetime.date(today.year, today.month, 1)
    if today.month == 12:
        next_first = datetime.date(today.year+1, 1, 1)
    else:
        next_first = datetime.date(today.year, today.month+1, 1)
    with SessionLocal() as s:
        bookings = (
            s.query(Booking)
            .filter(Booking.start_time >= datetime.datetime.combine(first_day, datetime.time.min),
                    Booking.start_time < datetime.datetime.combine(next_first, datetime.time.min))
            .all()
        )
    # Create Excel workbook using openpyxl
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    # Header
    headers = ["ID", "Дата", "Время начала", "Время конца", "Часы", "Клиент ID", "Инженер ID", "Статус", "Цена"]
    ws.append(headers)
    for b in bookings:
        row = [
            b.id,
            b.start_time.strftime("%d.%m.%Y"),
            b.start_time.strftime("%H:%M"),
            b.end_time.strftime("%H:%M"),
            b.duration_hours,
            b.client_id,
            b.engineer_id,
            b.status,
            float(b.price) if b.price is not None else None,
        ]
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    await query.message.reply_document(
        document=InputFile(buffer, filename=f"report_{today:%Y_%m}.xlsx"),
        caption="Отчёт за текущий месяц.",
    )
    await query.edit_message_text(
        text="Отчёт отправлен.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")]]),
    )
    return

# ----------------- Меню команды -----------------
async def adm_team_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with SessionLocal() as s:
        engineers = s.query(Engineer).join(User).all()
    if not engineers:
        text = "Команда пуста."
        keyboard = [
            [InlineKeyboardButton("➕ Добавить члена команды", callback_data="adm_team_add")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")],
        ]
    else:
        lines = []
        for eng in engineers:
            name = get_engineer_name(eng)
            info = get_setting(f"team_info_{eng.id}") or "нет описания"
            lines.append(f"👨‍🎧 {name}: {info}")
        text = "Наша команда:\n" + "\n".join(lines)
        keyboard = [
            [InlineKeyboardButton("➕ Добавить/изменить", callback_data="adm_team_add")],
            [InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")],
        ]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return

async def adm_team_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Пришлите Telegram‑ID или username пользователя, которого хотите добавить в команду, либо перешлите его сообщение.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="adm_team_menu")]]),
    )
    context.user_data["awaiting"] = "team_member"
    return

# ----------------- Контакты студии -----------------
async def adm_contacts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    contacts = get_setting("studio_contacts") or "ещё не заданы"
    await query.edit_message_text(
        text=f"Текущие контакты:\n{contacts}\n\nПришлите новый текст, чтобы обновить.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")]]),
    )
    context.user_data["awaiting"] = "studio_contacts"
    return

# ----------------- Отзывы -----------------
async def adm_reviews_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    with SessionLocal() as s:
        reviews = s.query(Review).order_by(Review.created_at.desc()).limit(10).all()
    if not reviews:
        text = "Отзывов пока нет."
    else:
        lines = []
        for r in reviews:
            stars = "⭐" * r.rating
            comment = f" – {r.comment}" if r.comment else ""
            lines.append(f"{r.id}. {stars}{comment} (клиент {r.client_id})")
        text = "Последние отзывы:\n" + "\n".join(lines)
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return

# ----------------- Ночная запись -----------------
async def adm_night_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="Для ночной записи укажите Telegram‑ID клиента, дату (ГГГГ‑ММ‑ДД), время начало (ЧЧ:ММ) и длительность в часах через пробел.\nПример: 123456789 2026-07-15 23:00 3",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_menu")]]),
    )
    context.user_data["awaiting"] = "night_booking"
    return

# ----------------- Общий обработчик ввода -----------------
async def admin_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting"):
        return
    awaiting = context.user_data.pop("awaiting")
    text = update.message.text.strip()
    user = update.effective_user
    with SessionLocal() as s:
        if awaiting == "engineer_id":
            # ожидаем пересланное сообщение или ID
            if update.message.forward_from:
                target_id = update.message.forward_from.id
            else:
                try:
                    target_id = int(text)
                except ValueError:
                    await update.message.reply_text("Нужно прислать Telegram‑ID или переслать сообщение.")
                    context.user_data["awaiting"] = "engineer_id"
                    return
            eng = s.query(Engineer).join(User).filter(User.id == target_id).first()
            if eng:
                await update.message.reply_text("Этот пользователь уже звукорежиссер.")
            else:
                # создаём запись инженера (если пользователь существует)
                u = s.get(User, target_id)
                if not u:
                    # создаём минимального пользователя
                    u = User(id=target_id, username=update.message.forward_from.username if update.message.forward_from else None,
                             full_name=update.message.forward_from.full_name if update.message.forward_from else "Неизвестно")
                    s.add(u)
                s.add(Engineer(user_id=target_id, specialization="", hourly_rate=float(get_setting("price_per_hour") or "1000")))
                s.commit()
                await update.message.reply_text("Пользователь добавлен как звукорежиссер.")
        elif awaiting == "admin_id":
            if update.message.forward_from:
                target_id = update.message.forward_from.id
            else:
                try:
                    target_id = int(text)
                except ValueError:
                    await update.message.reply_text("Нужно прислать Telegram‑ID или переслать сообщение.")
                    context.user_data["awaiting"] = "admin_id"
                    return
            # просто добавляем в список ADMIN_IDS (в .env не меняем, но сохраняем в settings)
            current = get_setting("admin_ids") or ""
            ids = set(int(x) for x in current.split(",") if x.strip().isdigit())
            ids.add(target_id)
            set_setting("admin_ids", ",".join(str(i) for i in ids))
            await update.message.reply_text("Пользователь добавлен как админ (запомнено в настройках).")
        elif awaiting == "team_member":
            # аналогично инженер, но сохраняем описание и фото позже
            if update.message.forward_from:
                target_id = update.message.forward_from.id
            else:
                try:
                    target_id = int(text)
                except ValueError:
                    await update.message.reply_text("Нужно прислать Telegram‑ID или переслать сообщение.")
                    context.user_data["awaiting"] = "team_member"
                    return
            # спросим описание
            context.user_data["team_member_id"] = target_id
            await update.message.reply_text("Введите описание для этого члена команды (можно оставить пустым):")
            context.user_data["awaiting"] = "team_desc"
            return
        elif awaiting == "team_desc":
            member_id = context.user_data.pop("team_member_id")
            desc = text
            set_setting(f"team_info_{member_id}", desc)
            await update.message.reply_text("Описание сохранено. Теперь пришлите фото для профиля (или отправьте любое сообщение, чтобы пропустить).")
            context.user_data["awaiting"] = "team_photo"
            return
        elif awaiting == "team_photo":
            member_id = context.user_data.pop("team_member_id", None)
            if member_id and update.message.photo:
                file_id = update.message.photo[-1].file_id
                set_setting(f"team_photo_{member_id}", file_id)
                await update.message.reply_text("Фото сохранено.")
            else:
                await update.message.reply_text("Фото не получено – пропущено.")
            context.user_data.clear()
            return
        elif awaiting == "studio_contacts":
            set_setting("studio_contacts", text)
            await update.message.reply_text("Контакты студии обновлены.")
            context.user_data.clear()
            return
        elif awaiting == "night_booking":
            # формат: client_id YYYY-MM-DD HH:MM hours
            parts = text.split()
            if len(parts) != 4:
                await update.message.reply_text("Неверный формат. Пример: 123456789 2026-07-15 23:00 3")
                context.user_data["awaiting"] = "night_booking"
                return
            try:
                client_id = int(parts[0])
                date = datetime.date.fromisoformat(parts[1])
                start_time = datetime.datetime.strptime(parts[2], "%H:%M")
                duration = int(parts[3])
                if duration < 1:
                    raise ValueError
            except Exception:
                await update.message.reply_text("Ошибка в данных.")
                context.user_data["awaiting"] = "night_booking"
                return
            start_dt = datetime.datetime.combine(date, start_time)
            end_dt = start_dt + datetime.timedelta(hours=duration)
            # проверяем доступность (просто проверяем, что нет конфликтов с уже существующими бронями у любого инженера?)
            # Для простоты берём первого доступного инженера (можно уточнить)
            with SessionLocal() as s2:
                engs = s2.query(Engineer).all()
                chosen_eng = None
                for e in engs:
                    if is_slot_free(e.id, start_dt, end_dt):
                        chosen_eng = e
                        break
                if not chosen_eng:
                    await update.message.reply_text("Нет доступного инженера на выбранное время.")
                    context.user_data.clear()
                    return
                price_per_hour = float(get_setting("price_per_hour") or "1000")
                price = price_per_hour * duration
                booking = Booking(
                    client_id=client_id,
                    engineer_id=chosen_eng.id,
                    start_time=start_dt,
                    end_time=end_dt,
                    duration_hours=duration,
                    status="ожидает подтверждения",  # ночная запись требует подтверждения
                    price=price,
                )
                s2.add(booking)
                s2.commit()
                await update.message.reply_text(
                    f"Ночная запись создана!\n"
                    f"Клиент ID: {client_id}\n"
                    f"Инженер: {chosen_eng.id}\n"
                    f"Время: {start_dt.strftime('%d.%m %H:%M')}–{end_dt.strftime('%H:%M')} ({duration} ч)\n"
                    f"Статус: ожидает подтверждения (нужно подтвердить админом или инженером)."
                )
            context.user_data.clear()
            return
        else:
            await update.message.reply_text("Неизвестное ожидание.")
            context.user_data.clear()
    # после обработки покажем меню админа снова
    await admin_menu(update, context)