from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SearchProfile
from ..schemas import SearchProfileCreate, SearchProfileUpdate, SearchProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[SearchProfileOut])
def list_profiles(db: Session = Depends(get_db)):
    return db.query(SearchProfile).order_by(SearchProfile.name).all()


@router.post("", response_model=SearchProfileOut, status_code=201)
def create_profile(payload: SearchProfileCreate, db: Session = Depends(get_db)):
    profile = SearchProfile(
        name=payload.name,
        enabled=payload.enabled,
        config=payload.config.model_dump(),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=SearchProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(SearchProfile).filter(SearchProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile


@router.patch("/{profile_id}", response_model=SearchProfileOut)
def update_profile(profile_id: int, payload: SearchProfileUpdate, db: Session = Depends(get_db)):
    profile = db.query(SearchProfile).filter(SearchProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")

    if payload.name is not None:
        profile.name = payload.name
    if payload.enabled is not None:
        profile.enabled = payload.enabled
    if payload.config is not None:
        profile.config = payload.config.model_dump()

    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(SearchProfile).filter(SearchProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(404, "Profile not found")
    db.delete(profile)
    db.commit()
