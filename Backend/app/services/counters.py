from __future__ import annotations

from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.order import SequenceCounter


def next_value(db: Session, company_id: UUID, scope: str) -> int:
    """Siguiente número del ámbito, atómico y sin huecos (se libera con el commit o el rollback)."""
    stmt = (
        insert(SequenceCounter)
        .values(company_id=company_id, scope=scope, value=1)
        .on_conflict_do_update(
            index_elements=[SequenceCounter.company_id, SequenceCounter.scope],
            set_={"value": SequenceCounter.value + 1},
        )
        .returning(SequenceCounter.value)
    )
    return int(db.execute(stmt).scalar_one())
