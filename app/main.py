from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import check_admin_credentials, generate_access_code, get_current_participant, require_admin
from app.database import get_db, init_db
from app.models import AdminAction, Bid, Item, ItemStatus, Participant, ParticipantStatus, Round, RoundStatus
from app.services import auction
from app.services.csv_io import csv_response, read_csv_rows
from app.services.uploads import save_image
from app.settings import BASE_DIR, settings
from app.websocket_manager import manager


app = FastAPI(title=settings.event_name)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="leilao_session", https_only=False)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["money"] = auction.money


@app.on_event("startup")
def startup() -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()


def redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)


def admin_context(request: Request, db: Session) -> dict:
    state = auction.current_state(db, admin=True)
    return {
        "request": request,
        "event_name": settings.event_name,
        "state": state,
        "items": db.scalars(select(Item).order_by(Item.display_order, Item.id)).all(),
        "participants_available": db.scalar(select(func.count(Participant.id)).where(Participant.status == ParticipantStatus.AVAILABLE)) or 0,
    }


async def broadcast_state(db: Session, event: str, extra: dict | None = None) -> None:
    payload = {"event": event, **(extra or {})}
    await manager.broadcast_all(payload)


@app.get("/", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    if request.session.get("participant_id"):
        return redirect("/participant")
    return templates.TemplateResponse("login.html", {"request": request, "event_name": settings.event_name, "error": None})


@app.post("/login")
def participant_login(request: Request, code: str = Form(...), db: Session = Depends(get_db)):
    participant = db.scalar(select(Participant).where(Participant.access_code == code.strip()))
    if not participant:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "event_name": settings.event_name, "error": "Codigo invalido. Confira os 5 numeros."},
            status_code=400,
        )
    request.session.clear()
    request.session["participant_id"] = participant.id
    return redirect("/participant")


@app.post("/logout")
def participant_logout(request: Request):
    request.session.clear()
    return redirect("/")


@app.get("/participant", response_class=HTMLResponse)
def participant_page(request: Request, participant: Participant = Depends(get_current_participant)):
    return templates.TemplateResponse(
        "participant.html",
        {"request": request, "event_name": settings.event_name, "participant": participant},
    )


@app.get("/api/current-state")
def api_current_state(participant: Participant = Depends(get_current_participant), db: Session = Depends(get_db)):
    return auction.current_state(db, participant=participant)


@app.post("/api/bid")
async def api_bid(participant: Participant = Depends(get_current_participant), db: Session = Depends(get_db)):
    bid = auction.place_bid(db, participant)
    await broadcast_state(db, "bid_changed", {"bid_id": bid.id})
    return {"ok": True, "bid": auction.serialize_bid(bid)}


@app.delete("/api/bid")
async def api_cancel_bid(participant: Participant = Depends(get_current_participant), db: Session = Depends(get_db)):
    auction.cancel_bid(db, participant)
    await broadcast_state(db, "bid_changed")
    return {"ok": True}


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    if request.session.get("admin"):
        return redirect("/admin")
    return templates.TemplateResponse("admin_login.html", {"request": request, "event_name": settings.event_name, "error": None})


@app.post("/admin/login")
def admin_login(request: Request, username: str = Form(...), password: str = Form(...)):
    if not check_admin_credentials(username, password):
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "event_name": settings.event_name, "error": "Usuario ou senha invalidos."},
            status_code=400,
        )
    request.session.clear()
    request.session["admin"] = True
    return redirect("/admin")


@app.post("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return redirect("/admin/login")


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    return templates.TemplateResponse("admin_dashboard.html", admin_context(request, db))


@app.get("/admin/live", response_class=HTMLResponse)
def admin_live(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    return templates.TemplateResponse("admin_live.html", admin_context(request, db))


@app.get("/admin/api/current-state")
def admin_api_current_state(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    return auction.current_state(db, admin=True)


@app.get("/admin/participants", response_class=HTMLResponse)
def admin_participants(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    participants = db.scalars(select(Participant).order_by(Participant.name)).all()
    return templates.TemplateResponse(
        "admin_participants.html",
        {"request": request, "event_name": settings.event_name, "participants": participants, "error": None},
    )


@app.post("/admin/participants")
async def create_participant(
    request: Request,
    name: str = Form(...),
    access_code: str = Form(""),
    fixed_value: str = Form(...),
    status_value: str = Form(ParticipantStatus.AVAILABLE),
    db: Session = Depends(get_db),
):
    require_admin(request)
    code = access_code.strip() or generate_access_code(db)
    participant = Participant(name=name.strip(), access_code=code, fixed_value=auction.parse_money_value(fixed_value), status=status_value)
    db.add(participant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Codigo duplicado")
    await broadcast_state(db, "participants_changed")
    return redirect("/admin/participants")


@app.post("/admin/participants/{participant_id}/edit")
async def edit_participant(
    request: Request,
    participant_id: int,
    name: str = Form(...),
    access_code: str = Form(...),
    fixed_value: str = Form(...),
    status_value: str = Form(...),
    db: Session = Depends(get_db),
):
    require_admin(request)
    participant = db.get(Participant, participant_id)
    if not participant:
        raise HTTPException(404, "Participante nao encontrado")
    participant.name = name.strip()
    participant.access_code = access_code.strip()
    participant.fixed_value = auction.parse_money_value(fixed_value)
    participant.status = status_value
    db.commit()
    await broadcast_state(db, "participants_changed")
    return redirect("/admin/participants")


@app.post("/admin/participants/{participant_id}/delete")
async def delete_participant(request: Request, participant_id: int, db: Session = Depends(get_db)):
    require_admin(request)
    participant = db.get(Participant, participant_id)
    if participant:
        db.delete(participant)
        db.commit()
    await broadcast_state(db, "participants_changed")
    return redirect("/admin/participants")


@app.post("/admin/participants/import")
def import_participants(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_admin(request)
    rows = read_csv_rows(file.file.read())
    for row in rows:
        code = (row.get("codigo") or "").strip() or generate_access_code(db)
        db.add(Participant(name=(row.get("nome") or "").strip(), access_code=code, fixed_value=auction.parse_money_value(row.get("valor") or 0)))
    db.commit()
    return redirect("/admin/participants")


@app.get("/admin/export/participants")
def export_participants(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    rows = [
        {"nome": p.name, "codigo": p.access_code, "valor": p.fixed_value, "status": p.status, "item_ganho": p.won_item_id or ""}
        for p in db.scalars(select(Participant).order_by(Participant.name)).all()
    ]
    return Response(csv_response(rows, ["nome", "codigo", "valor", "status", "item_ganho"]), media_type="text/csv")


@app.get("/admin/items", response_class=HTMLResponse)
def admin_items(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    items = db.scalars(select(Item).order_by(Item.display_order, Item.id)).all()
    return templates.TemplateResponse("admin_items.html", {"request": request, "event_name": settings.event_name, "items": items})


@app.post("/admin/items")
async def create_item(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    display_order: int = Form(0),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    require_admin(request)
    image_path = await save_image(image)
    db.add(Item(name=name.strip(), description=description.strip() or None, display_order=display_order, image_path=image_path))
    db.commit()
    await broadcast_state(db, "items_changed")
    return redirect("/admin/items")


@app.post("/admin/items/{item_id}/edit")
async def edit_item(
    request: Request,
    item_id: int,
    name: str = Form(...),
    description: str = Form(""),
    display_order: int = Form(0),
    status_value: str = Form(ItemStatus.WAITING),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    require_admin(request)
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(404, "Item nao encontrado")
    image_path = await save_image(image)
    item.name = name.strip()
    item.description = description.strip() or None
    item.display_order = display_order
    item.status = status_value
    if image_path:
        item.image_path = image_path
    db.commit()
    await broadcast_state(db, "items_changed")
    return redirect("/admin/items")


@app.post("/admin/items/{item_id}/delete")
async def delete_item(request: Request, item_id: int, db: Session = Depends(get_db)):
    require_admin(request)
    item = db.get(Item, item_id)
    if item:
        db.delete(item)
        db.commit()
    await broadcast_state(db, "items_changed")
    return redirect("/admin/items")


@app.post("/admin/items/import")
def import_items(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    require_admin(request)
    rows = read_csv_rows(file.file.read())
    for idx, row in enumerate(rows, start=1):
        db.add(
            Item(
                name=(row.get("nome") or "").strip(),
                description=(row.get("descricao") or "").strip() or None,
                display_order=int(row.get("ordem") or idx),
            )
        )
    db.commit()
    return redirect("/admin/items")


@app.get("/admin/export/items")
def export_items(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    rows = [
        {"nome": i.name, "descricao": i.description or "", "ordem": i.display_order, "status": i.status}
        for i in db.scalars(select(Item).order_by(Item.display_order)).all()
    ]
    return Response(csv_response(rows, ["nome", "descricao", "ordem", "status"]), media_type="text/csv")


@app.post("/admin/round/start/{item_id}")
async def admin_start_round(request: Request, item_id: int, next_url: str = Form("/admin/live"), db: Session = Depends(get_db)):
    require_admin(request)
    auction.start_round(db, item_id)
    await broadcast_state(db, "round_started")
    return redirect(next_url)


@app.post("/admin/round/close")
async def admin_close_round(request: Request, next_url: str = Form("/admin/live"), db: Session = Depends(get_db)):
    require_admin(request)
    result = auction.close_round(db)
    await broadcast_state(db, "round_closed", result)
    return redirect(next_url)


@app.post("/admin/round/reopen")
async def admin_reopen_round(request: Request, item_id: int | None = Form(None), next_url: str = Form("/admin/live"), db: Session = Depends(get_db)):
    require_admin(request)
    auction.reopen_round(db, item_id)
    await broadcast_state(db, "round_reopened")
    return redirect(next_url)


@app.post("/admin/round/cancel")
async def admin_cancel_round(request: Request, next_url: str = Form("/admin/live"), db: Session = Depends(get_db)):
    require_admin(request)
    auction.cancel_round(db)
    await broadcast_state(db, "round_canceled")
    return redirect(next_url)


@app.post("/admin/bids/{bid_id}/remove")
async def admin_remove_bid(request: Request, bid_id: int, next_url: str = Form("/admin/live"), db: Session = Depends(get_db)):
    require_admin(request)
    bid = db.get(Bid, bid_id)
    if bid and bid.round.status == RoundStatus.ACTIVE:
        bid.active = False
        db.commit()
    await broadcast_state(db, "bid_changed")
    return redirect(next_url)


@app.get("/admin/history", response_class=HTMLResponse)
def admin_history(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    items = db.scalars(select(Item).order_by(Item.display_order, Item.id)).all()
    counts = dict(db.execute(select(Round.item_id, func.count(Bid.id)).join(Bid, Bid.round_id == Round.id, isouter=True).group_by(Round.item_id)).all())
    return templates.TemplateResponse(
        "admin_history.html",
        {"request": request, "event_name": settings.event_name, "items": items, "counts": counts},
    )


@app.get("/admin/export/results")
def export_results(request: Request, db: Session = Depends(get_db)):
    require_admin(request)
    rows = []
    for item in db.scalars(select(Item).order_by(Item.display_order)).all():
        rows.append(
            {
                "item": item.name,
                "status": item.status,
                "vencedor": item.winner.name if item.winner else "",
                "valor": item.winning_value or "",
                "encerrado_em": item.closed_at or "",
            }
        )
    return Response(csv_response(rows, ["item", "status", "vencedor", "valor", "encerrado_em"]), media_type="text/csv")


@app.websocket("/ws/participant")
async def ws_participant(websocket: WebSocket):
    await manager.connect_participant(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/admin")
async def ws_admin(websocket: WebSocket):
    await manager.connect_admin(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
