from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    ...


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    author: Mapped[str] = mapped_column(String(255), index=True)
    isbn: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    copies_total: Mapped[int] = mapped_column(Integer, default=1)
    copies_available: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    reservations: Mapped[List["Reservation"]] = relationship(back_populates="book")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_email: Mapped[str] = mapped_column(String(320), index=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"),
        index=True,
    )
    start_date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    due_date: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active|cancelled|expired|returned

    book: Mapped["Book"] = relationship(back_populates="reservations")
