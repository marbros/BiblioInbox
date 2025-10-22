# app/nlu/intent_router.py
from __future__ import annotations

import json
import os
import re
from typing import Optional, TypedDict, Literal

SYSTEM = """Eres un asistente que traduce correos a una intención de biblioteca.
Devuelve SOLO un JSON válido que siga este schema:
{ "action": "...", "user_email": "...", "title": "...", "isbn": "..." }
Acciones permitidas: reserve, renew, cancel_reservation, register_book, delete_book, list_books.
"""

Action = Literal[
    "reserve",
    "renew",
    "cancel_reservation",
    "register_book",
    "delete_book",
    "list_books",
]
ALLOWED_ACTIONS = {
    "reserve",
    "renew",
    "cancel_reservation",
    "register_book",
    "delete_book",
    "list_books",
}

class Intent(TypedDict, total=False):
    action: Action
    user_email: Optional[str]
    title: Optional[str]
    isbn: Optional[str]

def _strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()

def _normalize_action(a: Optional[str]) -> Action:
    if not a:
        return "list_books"
    a = a.strip()
    aliases = {
        "reservar": "reserve",
        "renovar": "renew",
        "cancelar": "cancel_reservation",
        "registrar": "register_book",
        "eliminar": "delete_book",
        "lista": "list_books",
        "listar": "list_books",
        "list_books": "list_books",
    }
    a2 = aliases.get(a, a)
    return a2 if a2 in ALLOWED_ACTIONS else "list_books"

def _fallback_rules(text: str, sender_email: Optional[str]) -> Intent:
    t = (text or "").lower()
    action: Action = "list_books"
    if "registrar" in t:
        action = "register_book"
    elif "eliminar libro" in t or "eliminar" in t or "borrar libro" in t:
        action = "delete_book"
    elif "reservar" in t:
        action = "reserve"
    elif "renovar" in t:
        action = "renew"
    elif "cancelar" in t or "eliminar reserva" in t:
        action = "cancel_reservation"
    elif "lista" in t or "listar" in t or "catalogo" in t or "catálogo" in t:
        action = "list_books"

    m = re.search(r"(?:isbn[:\s]?)([\d-]{10,17})", t) or re.search(r"\b(\d{10,13})\b", t)
    isbn = m.group(1).replace("-", "") if m else None

    m2 = re.search(r'["\'](.+?)["\']', text or "")
    title = m2.group(1).strip() if m2 else None

    return {"action": action, "user_email": sender_email, "isbn": isbn, "title": title}

def _llm_intent(system_prompt: str, text: str) -> Optional[Intent]:
    """
    Invoca ChatOpenAI SIN templates para evitar conflicto con llaves.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        llm = ChatOpenAI(model=model_name, temperature=0)

        resp = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=text),
        ])
        raw = (resp.content or "").strip()
        cleaned = _strip_code_fences(raw)
        data = json.loads(cleaned)

        data["action"] = _normalize_action(data.get("action"))
        return data  # type: ignore[return-value]
    except Exception as e:
        print(f"[NLU/LLM] Error invocando LLM: {repr(e)}", flush=True)
        return None

def extract_intent(text: str, sender_email: Optional[str]) -> Intent:
    use_llm = os.getenv("USE_LLM", "false").lower() == "true"
    text = (text or "").strip()

    if use_llm:
        data = _llm_intent(SYSTEM, text)
        if isinstance(data, dict) and data.get("action"):
            if sender_email and not data.get("user_email"):
                data["user_email"] = sender_email
            data["action"] = _normalize_action(data.get("action"))
            return data  # type: ignore[return-value]

    return _fallback_rules(text, sender_email)

def humanize_result(action: Action, success: bool, detail: str) -> str:
    prefix = {
        "reserve": "¡Listo! ",
        "renew": "Hecho. ",
        "cancel_reservation": "Perfecto. ",
        "register_book": "Anotado. ",
        "delete_book": "Ok. ",
        "list_books": "Aquí va. ",
    }.get(action, "")
    if success:
        return f"{prefix}{detail}"
    return f"Ups, no pude completarlo: {detail}"
