import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Participant
from app.settings import settings


def generate_access_code(db: Session) -> str:
    for _ in range(200):
        code = f"{secrets.randbelow(100000):05d}"
        exists = db.scalar(select(Participant.id).where(Participant.access_code == code))
        if not exists:
            return code
    raise RuntimeError("Nao foi possivel gerar codigo unico")


def get_current_participant(request: Request, db: Annotated[Session, Depends(get_db)]) -> Participant:
    participant_id = request.session.get("participant_id")
    if not participant_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nao autenticado")
    participant = db.get(Participant, int(participant_id))
    if not participant:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessao invalida")
    return participant


def require_admin(request: Request) -> None:
    if not request.session.get("admin"):
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/admin/login"})


def check_admin_credentials(username: str, password: str) -> bool:
    return secrets.compare_digest(username, settings.admin_username) and secrets.compare_digest(
        password, settings.admin_password
    )
