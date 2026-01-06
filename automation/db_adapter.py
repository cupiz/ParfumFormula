"""
Database adapter for safe MySQL operations.

Provides connection handling and CRUD operations that don't disrupt
the existing PHP application's database state.
"""

import logging
from contextlib import contextmanager
from typing import Any, Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config import get_config, get_logger
from models import Base, Ingredient, IFRALibrary, Synonym, IngCategory


class DatabaseAdapter:
    """
    Safe database connection handler for ParfumVault.
    
    Features:
    - Connection pooling for efficiency
    - Context manager for automatic cleanup
    - Safe upsert that preserves user customizations
    """
    
    def __init__(self) -> None:
        self.config = get_config()
        self.logger = get_logger()
        
        self.engine = create_engine(
            self.config.db.connection_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
            echo=self.config.log_level == "DEBUG",
        )
        
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )
        
        self.logger.info(f"Database adapter initialized for {self.config.db.host}")
    
    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        
        Usage:
            with db.session() as session:
                result = session.query(Ingredient).all()
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    def test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            with self.session() as session:
                session.execute(text("SELECT 1"))
            self.logger.info("Database connection successful")
            return True
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return False
    
    # -------------------------------------------------------------------------
    # Ingredient Operations
    # -------------------------------------------------------------------------
    
    def get_ingredient_by_name(
        self, 
        name: str, 
        owner_id: Optional[str] = None
    ) -> Optional[Ingredient]:
        """
        Case-insensitive ingredient lookup by name.
        
        Args:
            name: Ingredient name to search for
            owner_id: Optional owner filter (uses default if not provided)
        
        Returns:
            Ingredient instance or None if not found
        """
        owner = owner_id or self.config.owner_id
        
        with self.session() as session:
            result = session.query(Ingredient).filter(
                Ingredient.name.ilike(name),
                Ingredient.owner_id == owner
            ).first()
            
            if result:
                session.expunge(result)
            return result
    
    def get_ingredient_by_cas(
        self, 
        cas: str, 
        owner_id: Optional[str] = None
    ) -> Optional[Ingredient]:
        """
        Lookup ingredient by CAS number.
        
        Args:
            cas: CAS registry number (e.g., "8007-75-8")
            owner_id: Optional owner filter
        
        Returns:
            Ingredient instance or None if not found
        """
        owner = owner_id or self.config.owner_id
        
        with self.session() as session:
            result = session.query(Ingredient).filter(
                Ingredient.cas == cas,
                Ingredient.owner_id == owner
            ).first()
            
            if result:
                session.expunge(result)
            return result
    
    def get_all_ingredients(
        self, 
        owner_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list[Ingredient]:
        """
        Get all ingredients for an owner.
        
        Args:
            owner_id: Owner filter (uses default if not provided)
            limit: Maximum number of results
        
        Returns:
            List of Ingredient instances
        """
        owner = owner_id or self.config.owner_id
        
        with self.session() as session:
            query = session.query(Ingredient).filter(
                Ingredient.owner_id == owner
            )
            if limit:
                query = query.limit(limit)
            
            results = query.all()
            for r in results:
                session.expunge(r)
            return results
    
    def upsert_ingredient(
        self,
        ingredient_data: dict[str, Any],
        fill_missing_only: bool = True,
        owner_id: Optional[str] = None
    ) -> tuple[Ingredient, bool]:
        """
        Insert or update an ingredient with safety checks.
        
        Args:
            ingredient_data: Dictionary of ingredient fields
            fill_missing_only: If True, only populate NULL/empty fields
                             (preserves user customizations)
            owner_id: Owner ID for the ingredient
        
        Returns:
            Tuple of (Ingredient, was_created)
        """
        owner = owner_id or self.config.owner_id
        name = ingredient_data.get("name", "").strip()
        
        if not name:
            raise ValueError("Ingredient name is required")
        
        with self.session() as session:
            # Try to find existing ingredient
            existing = session.query(Ingredient).filter(
                Ingredient.name.ilike(name),
                Ingredient.owner_id == owner
            ).first()
            
            if existing:
                # Update existing ingredient
                updated_fields = []
                
                for key, value in ingredient_data.items():
                    if key in ("id", "name", "owner_id", "created_at"):
                        continue  # Skip protected fields
                    
                    if not hasattr(existing, key):
                        continue  # Skip unknown fields
                    
                    current_value = getattr(existing, key)
                    
                    if fill_missing_only:
                        # Only update if current value is None or empty
                        is_empty = (
                            current_value is None or 
                            current_value == "" or
                            (isinstance(current_value, float) and current_value == 100.0)
                        )
                        if is_empty and value is not None:
                            setattr(existing, key, value)
                            updated_fields.append(key)
                    else:
                        # Always update
                        if value is not None:
                            setattr(existing, key, value)
                            updated_fields.append(key)
                
                if updated_fields:
                    self.logger.info(
                        f"Updated ingredient '{name}': {', '.join(updated_fields)}"
                    )
                else:
                    self.logger.debug(f"No updates needed for '{name}'")
                
                session.expunge(existing)
                return existing, False
            
            else:
                # Create new ingredient
                ingredient_data["owner_id"] = owner
                new_ingredient = Ingredient(**ingredient_data)
                session.add(new_ingredient)
                session.flush()
                
                self.logger.info(f"Created new ingredient: {name}")
                session.expunge(new_ingredient)
                return new_ingredient, True
    
    # -------------------------------------------------------------------------
    # IFRA Library Operations
    # -------------------------------------------------------------------------
    
    def get_ifra_entry_by_cas(
        self, 
        cas: str, 
        owner_id: Optional[str] = None
    ) -> Optional[IFRALibrary]:
        """Lookup IFRA entry by CAS number."""
        owner = owner_id or self.config.owner_id
        
        with self.session() as session:
            result = session.query(IFRALibrary).filter(
                IFRALibrary.cas == cas,
                IFRALibrary.owner_id == owner
            ).first()
            
            if result:
                session.expunge(result)
            return result
    
    def get_ifra_entry_by_name(
        self, 
        name: str, 
        owner_id: Optional[str] = None
    ) -> Optional[IFRALibrary]:
        """Lookup IFRA entry by name."""
        owner = owner_id or self.config.owner_id
        
        with self.session() as session:
            result = session.query(IFRALibrary).filter(
                IFRALibrary.name.ilike(name),
                IFRALibrary.owner_id == owner
            ).first()
            
            if result:
                session.expunge(result)
            return result
    
    def upsert_ifra_entry(
        self,
        ifra_data: dict[str, Any],
        fill_missing_only: bool = True,
        owner_id: Optional[str] = None
    ) -> tuple[IFRALibrary, bool]:
        """
        Insert or update IFRA library entry.
        
        Args:
            ifra_data: Dictionary of IFRA fields
            fill_missing_only: If True, only populate NULL fields
            owner_id: Owner ID for the entry
        
        Returns:
            Tuple of (IFRALibrary, was_created)
        """
        owner = owner_id or self.config.owner_id
        cas = ifra_data.get("cas", "").strip()
        name = ifra_data.get("name", "").strip()
        
        if not cas and not name:
            raise ValueError("Either CAS or name is required for IFRA entry")
        
        with self.session() as session:
            # Try to find existing entry by CAS first, then by name
            existing = None
            if cas:
                existing = session.query(IFRALibrary).filter(
                    IFRALibrary.cas == cas,
                    IFRALibrary.owner_id == owner
                ).first()
            
            if not existing and name:
                existing = session.query(IFRALibrary).filter(
                    IFRALibrary.name.ilike(name),
                    IFRALibrary.owner_id == owner
                ).first()
            
            if existing:
                # Update existing entry
                updated_fields = []
                
                for key, value in ifra_data.items():
                    if key in ("id", "owner_id"):
                        continue
                    
                    if not hasattr(existing, key):
                        continue
                    
                    current_value = getattr(existing, key)
                    
                    if fill_missing_only:
                        is_empty = (
                            current_value is None or 
                            current_value == "" or
                            (isinstance(current_value, float) and current_value == 100.0)
                        )
                        if is_empty and value is not None:
                            setattr(existing, key, value)
                            updated_fields.append(key)
                    else:
                        if value is not None:
                            setattr(existing, key, value)
                            updated_fields.append(key)
                
                if updated_fields:
                    self.logger.info(
                        f"Updated IFRA entry '{name or cas}': {', '.join(updated_fields)}"
                    )
                
                session.expunge(existing)
                return existing, False
            
            else:
                # Create new entry
                ifra_data["owner_id"] = owner
                new_entry = IFRALibrary(**ifra_data)
                session.add(new_entry)
                session.flush()
                
                self.logger.info(f"Created new IFRA entry: {name or cas}")
                session.expunge(new_entry)
                return new_entry, True
    
    # -------------------------------------------------------------------------
    # Synonym Operations
    # -------------------------------------------------------------------------
    
    def add_synonym(
        self,
        ingredient_name: str,
        synonym: str,
        source: Optional[str] = None,
        cid: Optional[int] = None,
        owner_id: Optional[str] = None
    ) -> Synonym:
        """Add a synonym for an ingredient."""
        owner = owner_id or self.config.owner_id
        
        with self.session() as session:
            # Check if synonym already exists
            existing = session.query(Synonym).filter(
                Synonym.ing == ingredient_name,
                Synonym.synonym == synonym,
                Synonym.owner_id == owner
            ).first()
            
            if existing:
                session.expunge(existing)
                return existing
            
            new_synonym = Synonym(
                ing=ingredient_name,
                synonym=synonym,
                source=source,
                cid=cid,
                owner_id=owner
            )
            session.add(new_synonym)
            session.flush()
            
            self.logger.debug(f"Added synonym '{synonym}' for '{ingredient_name}'")
            session.expunge(new_synonym)
            return new_synonym
    
    # -------------------------------------------------------------------------
    # Category Operations
    # -------------------------------------------------------------------------
    
    def get_or_create_category(
        self,
        name: str,
        notes: Optional[str] = None,
        owner_id: Optional[str] = None
    ) -> tuple[IngCategory, bool]:
        """Get or create an ingredient category."""
        owner = owner_id or self.config.owner_id
        
        with self.session() as session:
            existing = session.query(IngCategory).filter(
                IngCategory.name.ilike(name),
                IngCategory.owner_id == owner
            ).first()
            
            if existing:
                session.expunge(existing)
                return existing, False
            
            new_category = IngCategory(
                name=name,
                notes=notes,
                owner_id=owner
            )
            session.add(new_category)
            session.flush()
            
            self.logger.info(f"Created new category: {name}")
            session.expunge(new_category)
            return new_category, True


# Singleton instance
_db_adapter: Optional[DatabaseAdapter] = None


def get_db() -> DatabaseAdapter:
    """Get or create the global database adapter instance."""
    global _db_adapter
    if _db_adapter is None:
        _db_adapter = DatabaseAdapter()
    return _db_adapter
