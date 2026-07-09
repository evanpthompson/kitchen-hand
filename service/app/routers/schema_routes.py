from fastapi import APIRouter

from .. import core

router = APIRouter(tags=["schema"])


@router.get("/schema")
def get_schema():
    return core.load_schema()
