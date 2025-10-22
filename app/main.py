from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.db import get_db, engine
from app import models
from app.services import list_books, register_book, init_db

app = FastAPI(title="Library by Email", version="0.1.0")

@app.on_event("startup")
def on_startup():
    init_db(engine)

@app.get("/healthz")
def health():
    return {"ok": True}

@app.get("/books")
def api_list_books(db: Session = Depends(get_db)):
    books = list_books(db)
    return [
        {
            "id": b.id, "title": b.title, "author": b.author,
            "isbn": b.isbn, "copies_total": b.copies_total,
            "copies_available": b.copies_available, "active": b.active
        } for b in books
    ]

@app.post("/books/seed")
def seed_books(db: Session = Depends(get_db)):
    if not list_books(db):
        register_book(db, title="Cien Años de Soledad", author="G. G. Márquez", isbn="9780307474728", copies=2)
        register_book(db, title="El Quijote", author="Cervantes", isbn="9788491050299", copies=1)
    return {"seeded": True}
