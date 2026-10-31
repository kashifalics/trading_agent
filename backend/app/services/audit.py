from sqlalchemy.orm import Session

from app.core.jsonutil import to_jsonable
from app.database.models import AuditEvent


def audit(session: Session, user_id: int | None, action: str, entity_type: str | None = None,
          entity_id: int | str | None = None, ip: str | None = None, meta: dict | None = None) -> None:
    session.add(AuditEvent(user_id=user_id, action=action, entity_type=entity_type,
                           entity_id=None if entity_id is None else str(entity_id), ip=ip, meta=to_jsonable(meta or {})))
    session.commit()
