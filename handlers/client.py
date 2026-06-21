from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from db.init_db import SessionLocal, get_setting
from db.models import User, Engineer, Booking, Setting
from utils.formatting import (
    get_workday_slots,
    is_slot_free,
    format_datetime,
    get_engineer_name,
)
from utils.notifications import notify_new_booking, notify_reminder
import datetime