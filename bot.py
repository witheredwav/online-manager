import logging
import os
from datetime import datetime, time, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from dotenv import load_dotenv

# Локальные модули
from db.init_db import init_db, SessionLocal
from db.models import User, Engineer, Booking, Review, Setting, EngineerDayOff
from utils.formatting import (
    format_datetime,
    format_price,
    get_workday_slots,
    is_slot_free,
    get_engineer_name,
)
from utils.notifications import (
    notify_new_booking,
    notify_reminder,
    notify_review_request,
)
from handlers.client import (
    start_client_flow,
    client_date_chosen,
    client_engineer_chosen,
    client_slot_chosen,
    client_duration_chosen,
    client_rules_accepted,
    client_info_received,
    client_confirm_booking,
    client_cancel,
)
from handlers.engineer import engineer_menu, engineer_handler
from handlers.admin import admin_menu, admin_handler

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Conversation states for client booking ---
(
    CHOOSING_DATE,
    CHOOSING_ENGINEER,
    CHOOSING_SLOT,
    CHOOSING_DURATION,
    SHOWING_RULES,
    ENTERING_NAME,
    ENTERING_VISITORS,
    ENTERING_PHONE,
    CONFIRM_BOOKING,
) = range(9)

# --- Helper to get/set settings ---
def get_setting(key: str) -> str:
    with SessionLocal() as s:
        row = s.query(Setting).filter_by(key=key).first()
        return row.value if row else None

def set_setting(key: str, value: str):
    with SessionLocal() as s:
        row = s.query(Setting).filter_by(key=key).first()
        if row:
            row.value = value
        else:
            s.add(Setting(key=key, value=value))
        s.commit()

# --- Main ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with SessionLocal() as s:
        db_user = s.query(User).filter_by(id=user.id).first()
        if not db_user:
            db_user = User(id=user.id, username=user.username, full_name=user.full_name or user.first_name, role="client")
            s.add(db_user)
            s.commit()
    # главное меню
    keyboard = [
        [InlineKeyboardButton("📅 Записаться", callback_data="client_start")],
        [InlineKeyboardButton("👨‍🎧 Я звукорежиссер", callback_data="engineer_menu")],
        [InlineKeyboardButton("🛠 Админ панель", callback_data="admin_menu")],
        [InlineKeyboardButton("📞 Контакты студии", callback_data="show_contacts")],
        [InlineKeyboardButton("👥 Наша команда", callback_data="show_team")],
    ]
    await update.message.reply_text(
        f"Привет, {user.first_name}! Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# --- Generic callbacks ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "client_start":
        return await start_client_flow(update, context)
    if data.startswith("client_date:"):
        return await client_date_chosen(update, context)
    if data.startswith("client_engineer:"):
        return await client_engineer_chosen(update, context)
    if data.startswith("client_slot:"):
        return await client_slot_chosen(update, context)
    if data.startswith("client_duration:"):
        return await client_duration_chosen(update, context)
    if data == "client_rules_yes":
        return await client_rules_accepted(update, context)
    if data == "client_rules_no":
        return await client_cancel(update, context)
    if data == "client_confirm":
        return await client_confirm_booking(update, context)
    if data == "client_cancel":
        return await client_cancel(update, context)

    if data == "engineer_menu":
        return await engineer_menu(update, context)
    if data.startswith("eng_"):
        return await engineer_handler(update, context)

    if data == "admin_menu":
        return await admin_menu(update, context)
    if data.startswith("adm_"):
        return await admin_handler(update, context)

    if data == "show_contacts":
        contacts = get_setting("studio_contacts") or "Контакты не заданы."
        await query.edit_message_text(text=contacts, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]))
    if data == "show_team":
        team = get_setting("team_info") or "Информация о команде не задана."
        await query.edit_message_text(text=team, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]]))
    if data == "main_menu":
        await start(update, context)
        return ConversationHandler.END

    return ConversationHandler.END

def main():
    # инициализация БД
    init_db()
    # приложение
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN не установлен")
    application = Application.builder().token(token).build()

    # обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    # ConversationHandler для клиентского бронирования
    client_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_client_flow, pattern="^client_start$")],
        states={
            CHOOSING_DATE: [CallbackQueryHandler(client_date_chosen, pattern="^client_date:")],
            CHOOSING_ENGINEER: [CallbackQueryHandler(client_engineer_chosen, pattern="^client_engineer:")],
            CHOOSING_SLOT: [CallbackQueryHandler(client_slot_chosen, pattern="^client_slot:")],
            CHOOSING_DURATION: [CallbackQueryHandler(client_duration_chosen, pattern="^client_duration:")],
            SHOWING_RULES: [
                CallbackQueryHandler(client_rules_accepted, pattern="^client_rules_yes$"),
                CallbackQueryHandler(client_cancel, pattern="^client_rules_no$"),
            ],
            ENTERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_info_received)],
            ENTERING_VISITORS: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_info_received)],
            ENTERING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_info_received)],
            CONFIRM_BOOKING: [
                CallbackQueryHandler(client_confirm_booking, pattern="^client_confirm$"),
                CallbackQueryHandler(client_cancel, pattern="^client_cancel$"),
            ],
        },
        fallbacks=[CallbackQueryHandler(client_cancel, pattern="^client_cancel$")],
        allow_reentry=True,
    )
    application.add_handler(client_conv)

    # Запуск
    application.run_polling()

if __name__ == "__main__":
    main()