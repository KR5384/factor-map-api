from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/items", tags=["items"])


class ItemCreate(BaseModel):
    name: str


class Item(BaseModel):
    id: int
    name: str


# DB を繋ぐまではメモリ上で保持（サーバー再起動で消える）
_items: list[Item] = [
    Item(id=1, name="sample-1"),
    Item(id=2, name="sample-2"),
]


@router.get("", response_model=list[Item])
def list_items():
    return _items


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int):
    for item in _items:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@router.post("", response_model=Item, status_code=201)
def create_item(payload: ItemCreate):
    new_id = max((item.id for item in _items), default=0) + 1
    item = Item(id=new_id, name=payload.name)
    _items.append(item)
    return item
