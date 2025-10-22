import os
import time
import re
from email.header import decode_header, make_header

from sqlalchemy.exc import IntegrityError

from app.email.mail_utils import connect_imap, fetch_unseen, mark_seen, send_mail, html_to_text
from app.nlu.intent_router import extract_intent, humanize_result
from app.db import SessionLocal
from app.services import (
    register_book, delete_book, reserve_book, renew_reservation, cancel_reservation, list_books
)

POLL_SECONDS = int(os.getenv("POLL_SECONDS", "15"))

# --- Filtros desde .env (sencillos) ---
ALLOWED_SENDERS = {s.strip().lower() for s in os.getenv("ALLOWED_SENDERS", "").split(",") if s.strip()}
SUBJECT_ACTIONS = [s.strip().lower() for s in os.getenv(
    "SUBJECT_ACTIONS",
    "reservar,renovar,cancelar,registrar,eliminar,lista,listar"
).split(",") if s.strip()]


def _sender_from(msg):
    from_ = str(make_header(decode_header(msg.get("From", ""))))
    m = re.search(r"<(.+?)>", from_)
    return (m.group(1) if m else from_).strip().lower()


def _subject_from(msg):
    return str(make_header(decode_header(msg.get("Subject", "")))).strip()


def _body_from(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                return part.get_payload(decode=True).decode(errors="ignore")
            if ctype == "text/html":
                html = part.get_payload(decode=True).decode(errors="ignore")
                return html_to_text(html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(errors="ignore")
    return ""


def _format_reply(req: dict, natural: str) -> str:
    action = req.get("action")
    title_or_isbn = req.get("title") or req.get("isbn") or "(sin título/ISBN)"
    return (
        f"Tu solicitud: {action} sobre {title_or_isbn}.\n"
        f"{natural}\n\n"
        "¿Te ayudo con algo más? Puedes escribir: reservar, renovar, cancelar, registrar, eliminar, lista."
    )


def process_email(msg):
    sender = _sender_from(msg)
    subject = _subject_from(msg)

    # --- Filtros mínimos y claros ---
    if ALLOWED_SENDERS and sender not in ALLOWED_SENDERS:
        raise RuntimeError(f"Skip: sender no permitido -> {sender}")

    subj_low = subject.lower()
    if SUBJECT_ACTIONS and not any(kw in subj_low for kw in SUBJECT_ACTIONS):
        raise RuntimeError(f"Skip: asunto sin acción válida -> {subject}")

    # NLU con asunto + cuerpo (robusto si el cuerpo está vacío)
    body = _body_from(msg)
    text_for_nlu = f"{subject}\n{body}".strip()

    req = extract_intent(text_for_nlu, sender)
    action = req.get("action")
    isbn = (req.get("isbn") or "").strip()
    title = (req.get("title") or "").strip()

    db = SessionLocal()
    try:
        if action == "register_book":
            if not isbn or not title:
                natural = humanize_result(action, False, 'Incluye ISBN y el título entre comillas ("Título").')
            else:
                try:
                    # Soporta ambas firmas de services.register_book:
                    # 1) (book, err)
                    # 2) book (solo objeto)
                    result = register_book(db, title=title, author="Desconocido", isbn=isbn, copies=1)
                    if isinstance(result, tuple) and len(result) == 2:
                        b, err = result
                        natural = humanize_result(
                            action,
                            not bool(err),
                            f"Registré '{b.title}' con ISBN {b.isbn}. Ya está disponible." if not err else err
                        )
                    else:
                        b = result  # type: ignore[assignment]
                        natural = humanize_result(action, True, f"Registré '{b.title}' con ISBN {b.isbn}. Ya está disponible.")
                except IntegrityError:
                    natural = humanize_result(action, False, "El ISBN ya existe en el catálogo.")
                except Exception as e:
                    natural = humanize_result(action, False, f"No pude registrar el libro: {e}")

        elif action == "delete_book":
            if not isbn:
                natural = humanize_result(action, False, "Para eliminar un libro, indica el ISBN (ej: isbn:978...).")
            else:
                _, err = delete_book(db, isbn=isbn)
                natural = humanize_result(action, not bool(err), "Libro eliminado." if not err else err)

        elif action == "reserve":
            _, err = reserve_book(db, user_email=sender, isbn=isbn)
            natural = humanize_result(
                action, not bool(err),
                "Reserva realizada exitosamente. ¡Disfrútalo! (tu correo quedó asociado a la reserva)." if not err else err
            )

        elif action == "renew":
            _, err = renew_reservation(db, user_email=sender, isbn=isbn)
            natural = humanize_result(
                action, not bool(err),
                "Renovación exitosa por 7 días adicionales." if not err else err
            )

        elif action == "cancel_reservation":
            _, err = cancel_reservation(db, user_email=sender, isbn=isbn)
            natural = humanize_result(
                action, not bool(err),
                "Reserva cancelada. El libro se considera devuelto; si lo necesitas de nuevo, vuelve a reservar." if not err else err
            )

        else:  # list_books
            books = list_books(db)
            listado = "\n".join(
                [f"- {b.title} (ISBN {b.isbn}) | disp: {b.copies_available}/{b.copies_total}" for b in books]
            ) or "(sin libros)"
            natural = humanize_result(action, True, f"Catálogo:\n{listado}")

        # ⬇️ AHORA devolvemos 3 valores (para que run() no falle)
        return sender, _format_reply(req, natural), req

    finally:
        db.close()


def run():
    client = connect_imap()
    print("[WORKER] Iniciado. Esperando correos...", flush=True)

    while True:
        try:
            for uid, msg in fetch_unseen(client):
                try:
                    # logs básicos del correo
                    subject = str(make_header(decode_header(msg.get("Subject", ""))))
                    sender_header = str(make_header(decode_header(msg.get("From", ""))))
                    print(f"[MAIL] UID={uid} FROM={sender_header} SUBJECT={subject}", flush=True)

                    # procesa NLU (NO marcar leído si hay Skip/ERROR)
                    try:
                        to_addr, text, req = process_email(msg)
                    except RuntimeError as skip_reason:
                        print(f"[SKIP] UID={uid} {skip_reason}", flush=True)
                        continue
                    except Exception as e:
                        print(f"[ERROR] UID={uid} fallo en process_email: {repr(e)}", flush=True)
                        continue

                    # log de intención
                    action = (req or {}).get("action")
                    isbn = (req or {}).get("isbn")
                    title = (req or {}).get("title")
                    print(f"[NLU]  UID={uid} action={action} isbn={isbn} title={title}", flush=True)

                    # enviar por SMTP
                    print(f"[SMTP] UID={uid} -> enviando a {to_addr}", flush=True)
                    res = send_mail(to_addr, "Biblioteca — Respuesta", text)
                    print(f"[SMTP] UID={uid} sendmail result: {res}", flush=True)

                    # SOLO si send_mail fue OK (dict vacío) marcamos como leído
                    if not res:
                        mark_seen(client, uid)
                        print(f"[SEEN] UID={uid} marcado como leído", flush=True)
                    else:
                        print(f"[WARN] UID={uid} no marcado leído; fallos: {res}", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[ERROR] UID={uid} excepción no controlada: {repr(e)}", flush=True)
                    traceback.print_exc()

        except Exception as loop_error:
            print(f"[LOOP] Error en ciclo principal: {repr(loop_error)}", flush=True)
            try:
                client.noop()
            except Exception:
                time.sleep(3)
                client = connect_imap()

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
