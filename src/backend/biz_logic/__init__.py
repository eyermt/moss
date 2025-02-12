"""
The backend adhears to a hex architecture. See: https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)
This module contains code for all buisness logic of the application.
The buisness logic of the application is primarily driven by the "Harvest, Bottle, Mix" archetecture outlined by Sam Schwartz.
See this slide deck for more details: https://docs.google.com/presentation/d/1jE0-VBikgAd-E6XSRTEkt_RxI190uVlsWg11fB6YgXw/edit?usp=sharing
In particular, this module uses FastAPI to create RESTful endpoints.
The "unsightly cables behind the desk" which connect routers to various sections of the code are also included in these 
__init__.py files.
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="",
    responses={404: {"description": "Not found"}},
)

from ..biz_logic.harvest.endpoint import router as harvest_router

router.include_router(harvest_router)

