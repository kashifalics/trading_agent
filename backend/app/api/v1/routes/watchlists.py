from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.database.models import Instrument, User, Watchlist, WatchlistItem
from app.database.session import get_session
from app.market_data.ingestion.service import get_instrument

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


class WatchlistIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ItemIn(BaseModel):
    symbol: str
    note: str | None = Field(default=None, max_length=500)


def _owned(session: Session, wid: int, user: User) -> Watchlist:
    w = session.get(Watchlist, wid)
    if not w or w.user_id != user.id:
        raise NotFoundError("Watchlist not found")
    return w


def _dump(session: Session, w: Watchlist) -> dict:
    items = session.execute(select(WatchlistItem, Instrument.canonical_symbol).join(
        Instrument, WatchlistItem.instrument_id == Instrument.id).where(WatchlistItem.watchlist_id == w.id)).all()
    return {"id": w.id, "name": w.name, "created_at": w.created_at,
            "items": [{"id": i.id, "symbol": s, "note": i.note} for i, s in items]}


@router.get("")
def list_watchlists(session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> list[dict]:
    return [_dump(session, w) for w in session.scalars(select(Watchlist).where(Watchlist.user_id == user.id))]


@router.post("", status_code=201)
def create(body: WatchlistIn, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    w = Watchlist(user_id=user.id, name=body.name.strip())
    session.add(w)
    session.commit()
    return _dump(session, w)


@router.delete("/{wid}", status_code=204)
def delete(wid: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> None:
    w = _owned(session, wid, user)
    for i in session.scalars(select(WatchlistItem).where(WatchlistItem.watchlist_id == w.id)):
        session.delete(i)
    session.delete(w)
    session.commit()


@router.post("/{wid}/items", status_code=201)
def add_item(wid: int, body: ItemIn, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> dict:
    w = _owned(session, wid, user)
    inst = get_instrument(session, body.symbol)
    exists = session.scalar(select(WatchlistItem).where(WatchlistItem.watchlist_id == w.id,
                                                        WatchlistItem.instrument_id == inst.id))
    if not exists:
        session.add(WatchlistItem(watchlist_id=w.id, instrument_id=inst.id, note=body.note))
        session.commit()
    return _dump(session, w)


@router.delete("/{wid}/items/{item_id}", status_code=204)
def remove_item(wid: int, item_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)) -> None:
    w = _owned(session, wid, user)
    item = session.get(WatchlistItem, item_id)
    if not item or item.watchlist_id != w.id:
        raise NotFoundError("Item not found")
    session.delete(item)
    session.commit()
