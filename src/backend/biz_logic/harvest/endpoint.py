from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.backend.persistence.db_session import DBSession
from src.backend.biz_logic.harvest.harvest_crud_types import CreateHarvest, UpdateHarvest
from datetime import datetime
from random import random

router = APIRouter(
    prefix="/harvest",
    tags=["harvest"],
    responses={404: {"description": "Not found"}},
)

@router.post(
    "/"
)
async def create_harvest(
    harvest: CreateHarvest,
    db_session: AsyncSession = Depends(DBSession.get_db_session)
):
    # Do buisness processing, if any
    # Add information to database via the db_session which connects with persistance data
    # Return the full harvest (now with a database ID and/or timestamps)
    
    """
    Example:
    processed_harvest = process_for_database_insertion(harvest)
    db_session.add(processed_harvest)
    await db_session.commit()
    await db_session.refresh(db_transaction)
    return db_transaction
    """
    harvest = harvest.model_dump()
    harvest["id"] = int(100*random())
    harvest["created_on"] = datetime.now()
    harvest["last_update"] = datetime.now()
    return harvest


@router.get(
    "/{harvest_id}",
)
async def get_harvest(
    harvest_id: int, session: AsyncSession = Depends(DBSession.get_db_session)
):
    # Get data from database based on the passed ID
    """
    Example:
    stmt = select(DBHarvest).where(DBHarvest.id == harvest_id).distinct()
    try:
        result = await session.scalars(stmt)
        result = result.one()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Harvest '{harvest_id}' not found.\n {e}"
        )
    """
    return f"Harvest {harvest_id} information from the db is returned here."


@router.get(
    "/{harvest_id}/repos",
)
async def get_harvest_repositories(
    harvest_id: int, session: AsyncSession = Depends(DBSession.get_db_session)
):
    # Get data from database based on the passed ID
    
    return ["example/repo1", "otherexample/repo2"]


@router.put(
    "/{harvest_id}"
)
async def update_harvest(
    harvest_id: int,
    harvest: UpdateHarvest,
    session: AsyncSession = Depends(DBSession.get_db_session),
):
    """
    Example:
    
    stmt = select(DBHarvest).filter(DBHarvest.id == harvest_id)
    try:
        result = await session.scalars(stmt)
        db_harvest = result.one()
    except:
        raise HTTPException(
            status_code=404, detail=f"Transaction {harvest_id} not found"
        )

    for key, value in harvest.model_dump(exclude_unset=True).items():
        setattr(db_harvest, key, value)

    await session.commit()
    await session.refresh(db_harvest)
    return db_harvest
    """
    harvest = harvest.model_dump()
    harvest["last_update"] = datetime.now()
    return harvest
