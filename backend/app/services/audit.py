from sqlalchemy.orm import Session

from app.models import AuditLog


def record(db: Session, actor: str, action: str, target_type: str, target_id: int | None, **details) -> None:
    """Append one audit entry. The database refuses any later UPDATE or DELETE of it."""
    db.add(AuditLog(actor=actor, action=action, target_type=target_type, target_id=target_id, details=details))
