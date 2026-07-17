from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Bid, Item, ItemStatus, Participant, ParticipantStatus, Round, RoundStatus


def money(value: int | None) -> str:
    if value is None:
        return "-"
    return f"T$ {value:,.0f}".replace(",", ".")


def active_round(db: Session) -> Round | None:
    return db.scalar(
        select(Round)
        .options(joinedload(Round.item), joinedload(Round.bids).joinedload(Bid.participant))
        .where(Round.status == RoundStatus.ACTIVE)
        .order_by(Round.started_at.desc())
    )


def item_position(db: Session, item: Item | None) -> str | None:
    if not item:
        return None
    total = db.scalar(select(func.count(Item.id)).where(Item.status != ItemStatus.CANCELED)) or 0
    before = (
        db.scalar(
            select(func.count(Item.id)).where(
                Item.status != ItemStatus.CANCELED,
                Item.display_order <= item.display_order,
            )
        )
        or 1
    )
    return f"Item {before} de {total}"


def current_state(db: Session, participant: Participant | None = None, admin: bool = False) -> dict:
    round_ = active_round(db)
    available_count = db.scalar(select(func.count(Participant.id)).where(Participant.status == ParticipantStatus.AVAILABLE)) or 0
    if not round_:
        return {
            "round": None,
            "item": None,
            "participant": serialize_participant(participant) if participant else None,
            "available_count": available_count,
            "message": "Aguardando o proximo item.",
        }

    bids = [bid for bid in round_.bids if bid.active]
    my_bid = None
    if participant:
        my_bid = next((bid for bid in bids if bid.participant_id == participant.id), None)
    payload = {
        "round": {"id": round_.id, "status": round_.status, "started_at": iso(round_.started_at)},
        "item": serialize_item(db, round_.item),
        "participant": serialize_participant(participant) if participant else None,
        "my_bid": serialize_bid(my_bid) if my_bid else None,
        "interested_count": len(bids),
        "available_count": available_count,
    }
    if admin:
        ordered = sorted(bids, key=lambda bid: (-bid.bid_value, bid.created_at, bid.id))
        payload["bids"] = [serialize_admin_bid(bid) for bid in ordered]
        payload["highest_value"] = max([bid.bid_value for bid in bids], default=None)
    return payload


def serialize_participant(participant: Participant | None) -> dict | None:
    if not participant:
        return None
    return {
        "id": participant.id,
        "name": participant.name,
        "fixed_value": participant.fixed_value,
        "fixed_value_label": money(participant.fixed_value),
        "status": participant.status,
        "won_item_id": participant.won_item_id,
    }


def serialize_item(db: Session, item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description or "",
        "image_path": item.image_path or "/static/uploads/logo2026.png",
        "display_order": item.display_order,
        "position": item_position(db, item),
        "status": item.status,
        "winner_id": item.winner_id,
        "winning_value": item.winning_value,
        "winning_value_label": money(item.winning_value),
        "closed_at": iso(item.closed_at),
    }


def serialize_bid(bid: Bid) -> dict:
    return {"id": bid.id, "value": bid.bid_value, "value_label": money(bid.bid_value), "created_at": iso(bid.created_at)}


def serialize_admin_bid(bid: Bid) -> dict:
    return {
        **serialize_bid(bid),
        "participant_id": bid.participant_id,
        "participant_name": bid.participant.name,
    }


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def start_round(db: Session, item_id: int) -> Round:
    if db.scalar(select(Round.id).where(Round.status == RoundStatus.ACTIVE)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ja existe uma rodada ativa")
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item nao encontrado")
    if item.status == ItemStatus.CANCELED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Item cancelado nao pode iniciar rodada")

    for active_item in db.scalars(select(Item).where(Item.status == ItemStatus.ACTIVE)).all():
        active_item.status = ItemStatus.WAITING
    item.status = ItemStatus.ACTIVE
    item.winner_id = None
    item.winning_value = None
    item.closed_at = None
    round_ = Round(item=item, status=RoundStatus.ACTIVE)
    db.add(round_)
    db.commit()
    db.refresh(round_)
    return round_


def place_bid(db: Session, participant: Participant) -> Bid:
    if participant.status != ParticipantStatus.AVAILABLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Participante nao pode participar")
    round_ = db.scalar(select(Round).where(Round.status == RoundStatus.ACTIVE))
    if not round_:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nao ha rodada aberta")
    existing = db.scalar(
        select(Bid).where(Bid.round_id == round_.id, Bid.participant_id == participant.id, Bid.active.is_(True))
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Participacao ja registrada")
    bid = Bid(round_id=round_.id, participant_id=participant.id, bid_value=participant.fixed_value, active=True)
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return bid


def cancel_bid(db: Session, participant: Participant) -> None:
    round_ = db.scalar(select(Round).where(Round.status == RoundStatus.ACTIVE))
    if not round_:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nao ha rodada aberta")
    bid = db.scalar(
        select(Bid).where(Bid.round_id == round_.id, Bid.participant_id == participant.id, Bid.active.is_(True))
    )
    if not bid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participacao nao encontrada")
    bid.active = False
    bid.canceled_at = datetime.now(timezone.utc)
    db.commit()


def close_round(db: Session) -> dict:
    round_ = db.scalar(select(Round).where(Round.status == RoundStatus.ACTIVE))
    if not round_:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nao ha rodada aberta")
    item = db.get(Item, round_.item_id)
    now = datetime.now(timezone.utc)
    bids = db.scalars(
        select(Bid)
        .options(joinedload(Bid.participant))
        .where(Bid.round_id == round_.id, Bid.active.is_(True))
        .order_by(Bid.bid_value.desc(), Bid.created_at.asc(), Bid.id.asc())
    ).all()

    winner_bid = bids[0] if bids else None
    round_.status = RoundStatus.CLOSED
    round_.closed_at = now
    item.status = ItemStatus.CLOSED
    item.closed_at = now
    if winner_bid:
        winner = winner_bid.participant
        round_.winner_id = winner.id
        item.winner_id = winner.id
        item.winning_value = winner_bid.bid_value
        winner.status = ParticipantStatus.WINNER
        winner.won_item_id = item.id
    db.commit()
    return {
        "winner": serialize_participant(winner_bid.participant) if winner_bid else None,
        "winning_bid": serialize_bid(winner_bid) if winner_bid else None,
        "item": serialize_item(db, item),
    }


def reopen_round(db: Session, item_id: int | None = None) -> Round:
    if db.scalar(select(Round.id).where(Round.status == RoundStatus.ACTIVE)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ja existe uma rodada ativa")
    item = db.get(Item, item_id) if item_id else db.scalar(select(Item).where(Item.status == ItemStatus.CLOSED).order_by(Item.closed_at.desc()))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item nao encontrado")
    if item.winner_id:
        winner = db.get(Participant, item.winner_id)
        if winner and winner.won_item_id == item.id:
            winner.status = ParticipantStatus.AVAILABLE
            winner.won_item_id = None
    item.status = ItemStatus.ACTIVE
    item.winner_id = None
    item.winning_value = None
    item.closed_at = None
    round_ = Round(item_id=item.id, status=RoundStatus.ACTIVE)
    db.add(round_)
    db.commit()
    db.refresh(round_)
    return round_


def cancel_round(db: Session) -> None:
    round_ = db.scalar(select(Round).where(Round.status == RoundStatus.ACTIVE))
    if not round_:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Nao ha rodada aberta")
    item = db.get(Item, round_.item_id)
    round_.status = RoundStatus.CANCELED
    round_.closed_at = datetime.now(timezone.utc)
    item.status = ItemStatus.CANCELED
    item.closed_at = round_.closed_at
    db.commit()
