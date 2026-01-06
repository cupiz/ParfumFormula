"""
SQLAlchemy ORM models matching the ParfumVault database schema.

These models mirror the PHP application's database structure for safe interop.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    TIMESTAMP,
    LargeBinary,
    Index,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Ingredient(Base):
    """
    Main ingredients table.
    
    Maps to: `ingredients` table in ParfumVault.
    """
    __tablename__ = "ingredients"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    INCI: Mapped[Optional[str]] = mapped_column(String(255))
    type: Mapped[Optional[str]] = mapped_column(String(255))
    strength: Mapped[Optional[str]] = mapped_column(String(255))
    category: Mapped[int] = mapped_column(Integer, default=1)
    purity: Mapped[Optional[str]] = mapped_column(String(11))
    cas: Mapped[Optional[str]] = mapped_column(String(255))
    einecs: Mapped[Optional[str]] = mapped_column(String(255))
    reach: Mapped[Optional[str]] = mapped_column(String(255))
    FEMA: Mapped[Optional[str]] = mapped_column(String(255))
    tenacity: Mapped[Optional[str]] = mapped_column(String(255))
    chemical_name: Mapped[Optional[str]] = mapped_column(String(255))
    formula: Mapped[Optional[str]] = mapped_column(String(255))
    flash_point: Mapped[Optional[str]] = mapped_column(String(255))
    appearance: Mapped[Optional[str]] = mapped_column(String(255))
    rdi: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    profile: Mapped[Optional[str]] = mapped_column(String(255))
    solvent: Mapped[Optional[str]] = mapped_column(String(255))
    allergen: Mapped[Optional[int]] = mapped_column(Integer)
    flavor_use: Mapped[Optional[int]] = mapped_column(Integer)
    soluble: Mapped[Optional[str]] = mapped_column(String(255))
    logp: Mapped[Optional[str]] = mapped_column(String(255))
    
    # IFRA Category limits (percentage)
    cat1: Mapped[float] = mapped_column(Float, default=100.0)
    cat2: Mapped[float] = mapped_column(Float, default=100.0)
    cat3: Mapped[float] = mapped_column(Float, default=100.0)
    cat4: Mapped[float] = mapped_column(Float, default=100.0)
    cat5A: Mapped[float] = mapped_column(Float, default=100.0)
    cat5B: Mapped[float] = mapped_column(Float, default=100.0)
    cat5C: Mapped[float] = mapped_column(Float, default=100.0)
    cat5D: Mapped[float] = mapped_column(Float, default=100.0)
    cat6: Mapped[float] = mapped_column(Float, default=100.0)
    cat7A: Mapped[float] = mapped_column(Float, default=100.0)
    cat7B: Mapped[float] = mapped_column(Float, default=100.0)
    cat8: Mapped[float] = mapped_column(Float, default=100.0)
    cat9: Mapped[float] = mapped_column(Float, default=100.0)
    cat10A: Mapped[float] = mapped_column(Float, default=100.0)
    cat10B: Mapped[float] = mapped_column(Float, default=100.0)
    cat11A: Mapped[float] = mapped_column(Float, default=100.0)
    cat11B: Mapped[float] = mapped_column(Float, default=100.0)
    cat12: Mapped[float] = mapped_column(Float, default=100.0)
    
    # Odor impact by note position
    impact_top: Mapped[Optional[str]] = mapped_column(String(10))
    impact_heart: Mapped[Optional[str]] = mapped_column(String(10))
    impact_base: Mapped[Optional[str]] = mapped_column(String(10))
    
    usage_type: Mapped[Optional[str]] = mapped_column(String(255))
    noUsageLimit: Mapped[int] = mapped_column(Integer, default=0)
    byPassIFRA: Mapped[int] = mapped_column(Integer, default=0)
    isPrivate: Mapped[int] = mapped_column(Integer, default=0)
    molecularWeight: Mapped[Optional[str]] = mapped_column(String(255))
    physical_state: Mapped[int] = mapped_column(Integer, default=1)
    cid: Mapped[Optional[int]] = mapped_column(Integer)  # PubChem Compound ID
    shelf_life: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    __table_args__ = (
        Index("ix_ingredients_name", "name"),
        Index("ix_ingredients_owner_id", "owner_id"),
    )


class IFRALibrary(Base):
    """
    IFRA Standards reference library.
    
    Maps to: `IFRALibrary` table in ParfumVault.
    """
    __tablename__ = "IFRALibrary"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ifra_key: Mapped[Optional[str]] = mapped_column(String(255))
    image: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    amendment: Mapped[Optional[str]] = mapped_column(String(255))
    prev_pub: Mapped[Optional[str]] = mapped_column(String(255))
    last_pub: Mapped[Optional[str]] = mapped_column(String(255))
    deadline_existing: Mapped[Optional[str]] = mapped_column(String(255))
    deadline_new: Mapped[Optional[str]] = mapped_column(String(255))
    name: Mapped[Optional[str]] = mapped_column(String(255))
    cas: Mapped[Optional[str]] = mapped_column(String(255))
    cas_comment: Mapped[Optional[str]] = mapped_column(Text)
    synonyms: Mapped[Optional[str]] = mapped_column(Text)
    formula: Mapped[Optional[str]] = mapped_column(String(255))
    flavor_use: Mapped[Optional[str]] = mapped_column(Text)
    prohibited_notes: Mapped[Optional[str]] = mapped_column(Text)
    restricted_photo_notes: Mapped[Optional[str]] = mapped_column(Text)
    restricted_notes: Mapped[Optional[str]] = mapped_column(Text)
    specified_notes: Mapped[Optional[str]] = mapped_column(Text)
    type: Mapped[Optional[str]] = mapped_column(String(255))
    risk: Mapped[Optional[str]] = mapped_column(String(255))
    contrib_others: Mapped[Optional[str]] = mapped_column(Text)
    contrib_others_notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # IFRA Category limits (percentage)
    cat1: Mapped[float] = mapped_column(Float, default=100.0)
    cat2: Mapped[float] = mapped_column(Float, default=100.0)
    cat3: Mapped[float] = mapped_column(Float, default=100.0)
    cat4: Mapped[float] = mapped_column(Float, default=100.0)
    cat5A: Mapped[float] = mapped_column(Float, default=100.0)
    cat5B: Mapped[float] = mapped_column(Float, default=100.0)
    cat5C: Mapped[float] = mapped_column(Float, default=100.0)
    cat5D: Mapped[float] = mapped_column(Float, default=100.0)
    cat6: Mapped[float] = mapped_column(Float, default=100.0)
    cat7A: Mapped[float] = mapped_column(Float, default=100.0)
    cat7B: Mapped[float] = mapped_column(Float, default=100.0)
    cat8: Mapped[float] = mapped_column(Float, default=100.0)
    cat9: Mapped[float] = mapped_column(Float, default=100.0)
    cat10A: Mapped[float] = mapped_column(Float, default=100.0)
    cat10B: Mapped[float] = mapped_column(Float, default=100.0)
    cat11A: Mapped[float] = mapped_column(Float, default=100.0)
    cat11B: Mapped[float] = mapped_column(Float, default=100.0)
    cat12: Mapped[float] = mapped_column(Float, default=100.0)
    
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False)


class IFRACategory(Base):
    """
    IFRA product category definitions.
    
    Maps to: `IFRACategories` table in ParfumVault.
    """
    __tablename__ = "IFRACategories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    type: Mapped[int] = mapped_column(Integer, nullable=False)


class IngCategory(Base):
    """
    Ingredient family/category classification.
    
    Maps to: `ingCategory` table in ParfumVault.
    """
    __tablename__ = "ingCategory"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    image: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False)


class IngProfile(Base):
    """
    Ingredient note position profiles (Top/Heart/Base/Solvent).
    
    Maps to: `ingProfiles` table in ParfumVault.
    """
    __tablename__ = "ingProfiles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class IngStrength(Base):
    """
    Ingredient strength classifications (Low/Medium/High/Extreme).
    
    Maps to: `ingStrength` table in ParfumVault.
    """
    __tablename__ = "ingStrength"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class IngType(Base):
    """
    Ingredient type classifications (AC/EO/Carrier/Solvent/etc).
    
    Maps to: `ingTypes` table in ParfumVault.
    """
    __tablename__ = "ingTypes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Synonym(Base):
    """
    Alternative ingredient names/synonyms.
    
    Maps to: `synonyms` table in ParfumVault.
    """
    __tablename__ = "synonyms"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ing: Mapped[str] = mapped_column(String(255), nullable=False)
    cid: Mapped[Optional[int]] = mapped_column(Integer)
    synonym: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False)
