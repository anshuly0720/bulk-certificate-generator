from pydantic import ValidationError

from app.schemas import RecipientIn


def font_can_draw(name: str) -> bool:
    """The built-in PDF font draws black boxes for anything outside cp1252,
    and raises nothing, so the row is rejected up front instead."""
    try:
        name.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _clip(value) -> str | None:
    return None if value is None else str(value)[:200]


def check_recipients(rows: list[dict]) -> list[dict]:
    """One result per row, in order. error=None means the row is valid."""
    results = []
    seen = set()
    for index, raw in enumerate(rows):
        error = None
        recipient = None
        try:
            recipient = RecipientIn.model_validate(raw)
        except ValidationError as exc:
            error = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
            )
        if recipient is not None:
            if not font_can_draw(recipient.name):
                error = "name uses characters the certificate font cannot draw"
            elif recipient.email.lower() in seen:
                error = "duplicate email in this request"
            else:
                seen.add(recipient.email.lower())
        results.append({
            "index": index,
            "name": recipient.name if recipient else _clip(raw.get("name")),
            "email": recipient.email if recipient else _clip(raw.get("email")),
            "error": error[:500] if error else None,
        })
    return results