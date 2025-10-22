# app/services.py
from datetime import datetime, timedelta
from typing import Tuple, Optional, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import models


def init_db(engine):
    models.Base.metadata.create_all(bind=engine)


def register_book(
    db: Session, *, title: str, author: str, isbn: str, copies: int = 1
) -> Tuple[Optional[models.Book], Optional[str]]:
    """
    Registra un libro nuevo.
    Devuelve: (Book|None, err|None)
    - Si el ISBN ya existe, retorna (None, "El ISBN ya existe en el catálogo.")
    """
    # Opción 1: verificar duplicado antes (más claro que depender de la excepción)
    existing = db.query(models.Book).filter_by(isbn=isbn, active=True).first()
    if existing:
        return None, "El ISBN ya existe en el catálogo."

    book = models.Book(
        title=title,
        author=author,
        isbn=isbn,
        copies_total=copies,
        copies_available=copies,
        active=True,
    )
    db.add(book)
    try:
        db.commit()
        db.refresh(book)
        return book, None
    except IntegrityError:
        db.rollback()
        return None, "El ISBN ya existe en el catálogo."
    except Exception as e:
        db.rollback()
        return None, f"Error registrando el libro: {e}"


def delete_book(db: Session, *, isbn: str):
    b = db.query(models.Book).filter_by(isbn=isbn, active=True).first()
    if not b:
        return None, "Libro no encontrado"
    if b.copies_available != b.copies_total:
        return None, "No se puede eliminar: hay reservas activas"
    b.active = False
    db.commit()
    return b, None


def reserve_book(db: Session, *, user_email: str, isbn: str):
    b = db.query(models.Book).filter_by(isbn=isbn, active=True).first()
    if not b:
        return None, "Libro no encontrado"
    if b.copies_available < 1:
        return None, "No hay copias disponibles"
    active_res = (
        db.query(models.Reservation)
        .filter_by(user_email=user_email, book_id=b.id, status="active")
        .first()
    )
    if active_res:
        return None, "Ya tienes una reserva activa de este libro"
    res = models.Reservation(
        user_email=user_email,
        book_id=b.id,
        start_date=datetime.utcnow(),
        due_date=datetime.utcnow() + timedelta(days=14),
        status="active",
    )
    b.copies_available -= 1
    db.add(res)
    db.commit()
    db.refresh(res)
    return res, None


def renew_reservation(db: Session, *, user_email: str, isbn: str):
    b = db.query(models.Book).filter_by(isbn=isbn, active=True).first()
    if not b:
        return None, "Libro no encontrado"
    res = (
        db.query(models.Reservation)
        .filter_by(user_email=user_email, book_id=b.id, status="active")
        .first()
    )
    if not res:
        return None, "No tienes una reserva activa de este libro"
    if res.due_date < datetime.utcnow():
        return None, "La reserva ya venció"
    res.due_date = res.due_date + timedelta(days=7)
    db.commit()
    db.refresh(res)
    return res, None


def cancel_reservation(db: Session, *, user_email: str, isbn: str):
    b = db.query(models.Book).filter_by(isbn=isbn, active=True).first()
    if not b:
        return None, "Libro no encontrado"
    res = (
        db.query(models.Reservation)
        .filter_by(user_email=user_email, book_id=b.id, status="active")
        .first()
    )
    if not res:
        return None, "No hay reserva activa para cancelar"
    res.status = "cancelled"
    b.copies_available += 1
    db.commit()
    db.refresh(res)
    return res, None


def list_books(db: Session):
    return db.query(models.Book).filter_by(active=True).all()

