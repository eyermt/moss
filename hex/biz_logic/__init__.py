from fastapi import APIRouter

router = APIRouter(
    prefix="",
    responses={404: {"description": "Not found"}},
)

from ..biz_logic.harvest.endpoint import router as harvest_router

router.include_router(harvest_router)

