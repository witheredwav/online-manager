from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Numeric, Text, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)  # Telegram‑ID
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(String(20), nullable=False)  # client, engineer, admin
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Engineer(Base):
    __tablename__ = "engineers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    specialization = Column(String(255), nullable=True)
    hourly_rate = Column(Numeric(10, 2), nullable=False, default=1000)
    user = relationship("User")

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    engineer_id = Column(Integer, ForeignKey("engineers.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    duration_hours = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False)  # ожидает подтверждения, подтверждено, отменено, завершено
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    confirmed_at = Column(DateTime, nullable=True)
    __table_args__ = (
        CheckConstraint("status IN ('ожидает подтверждения','подтверждено','отменено','завершено')", name="chk_status"),
    )

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=True)

class EngineerDayOff(Base):
    __tablename__ = "engineer_days_off"
    engineer_id = Column(Integer, ForeignKey("engineers.id", ondelete="CASCADE"), primary_key=True)
    off_date = Column(Date, primary_key=True)
    engineer = relationship("Engineer")

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1‑5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="chk_rating"),
    )