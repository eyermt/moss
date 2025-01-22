from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from .status import Status

class CreateHarvest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[Status] = None
    initial_repositories: list[str] = None
    
class UpdateHarvest(BaseModel):
    name: Optional[str] = None
    status: Optional[Status] = None
    repositories: Optional[list[str]] = None
    