"""
IFRA Standards synchronization module.

Parses IFRA standards from CSV files or online sources and
populates the IFRALibrary table in ParfumVault.
"""

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import requests

from config import get_config, get_logger
from db_adapter import get_db, DatabaseAdapter


@dataclass
class IFRAEntry:
    """Parsed IFRA standard entry."""
    name: str
    cas: Optional[str] = None
    amendment: Optional[str] = None
    type: Optional[str] = None  # Prohibition, Restriction, Specification
    risk: Optional[str] = None  # Sensitization, Phototoxicity, etc.
    synonyms: Optional[str] = None
    formula: Optional[str] = None
    
    # Category limits (percentage)
    cat1: float = 100.0
    cat2: float = 100.0
    cat3: float = 100.0
    cat4: float = 100.0
    cat5A: float = 100.0
    cat5B: float = 100.0
    cat5C: float = 100.0
    cat5D: float = 100.0
    cat6: float = 100.0
    cat7A: float = 100.0
    cat7B: float = 100.0
    cat8: float = 100.0
    cat9: float = 100.0
    cat10A: float = 100.0
    cat10B: float = 100.0
    cat11A: float = 100.0
    cat11B: float = 100.0
    cat12: float = 100.0
    
    # Additional metadata
    prohibited_notes: Optional[str] = None
    restricted_notes: Optional[str] = None
    specified_notes: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database upsert."""
        return {
            "name": self.name,
            "cas": self.cas,
            "amendment": self.amendment,
            "type": self.type,
            "risk": self.risk,
            "synonyms": self.synonyms,
            "formula": self.formula,
            "cat1": self.cat1,
            "cat2": self.cat2,
            "cat3": self.cat3,
            "cat4": self.cat4,
            "cat5A": self.cat5A,
            "cat5B": self.cat5B,
            "cat5C": self.cat5C,
            "cat5D": self.cat5D,
            "cat6": self.cat6,
            "cat7A": self.cat7A,
            "cat7B": self.cat7B,
            "cat8": self.cat8,
            "cat9": self.cat9,
            "cat10A": self.cat10A,
            "cat10B": self.cat10B,
            "cat11A": self.cat11A,
            "cat11B": self.cat11B,
            "cat12": self.cat12,
            "prohibited_notes": self.prohibited_notes,
            "restricted_notes": self.restricted_notes,
            "specified_notes": self.specified_notes,
        }


@dataclass
class SyncResult:
    """Result of IFRA sync operation."""
    success: bool
    total_entries: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


# =============================================================================
# CSV Column Mapping (Update if CSV format changes)
# =============================================================================

class IFRACSVColumns:
    """
    Column mapping for IFRA CSV files.
    
    Update these mappings if the CSV structure changes.
    Supports multiple possible column names for flexibility.
    """
    
    # Required columns
    NAME: list[str] = ["Name", "Material Name", "Ingredient", "IFRA Name"]
    CAS: list[str] = ["CAS", "CAS Number", "CAS No.", "CAS#"]
    
    # Optional metadata
    AMENDMENT: list[str] = ["Amendment", "IFRA Amendment", "Amendment No."]
    TYPE: list[str] = ["Type", "Standard Type", "Restriction Type"]
    RISK: list[str] = ["Risk", "Endpoint", "Safety Concern"]
    SYNONYMS: list[str] = ["Synonyms", "Other Names", "Alternate Names"]
    FORMULA: list[str] = ["Formula", "Molecular Formula"]
    
    # Category percentage columns
    CATEGORY_PATTERNS: dict[str, list[str]] = {
        "cat1": ["Cat 1", "Category 1", "Cat1", "1"],
        "cat2": ["Cat 2", "Category 2", "Cat2", "2"],
        "cat3": ["Cat 3", "Category 3", "Cat3", "3"],
        "cat4": ["Cat 4", "Category 4", "Cat4", "4"],
        "cat5A": ["Cat 5A", "Category 5A", "Cat5A", "5A"],
        "cat5B": ["Cat 5B", "Category 5B", "Cat5B", "5B"],
        "cat5C": ["Cat 5C", "Category 5C", "Cat5C", "5C"],
        "cat5D": ["Cat 5D", "Category 5D", "Cat5D", "5D"],
        "cat6": ["Cat 6", "Category 6", "Cat6", "6"],
        "cat7A": ["Cat 7A", "Category 7A", "Cat7A", "7A"],
        "cat7B": ["Cat 7B", "Category 7B", "Cat7B", "7B"],
        "cat8": ["Cat 8", "Category 8", "Cat8", "8"],
        "cat9": ["Cat 9", "Category 9", "Cat9", "9"],
        "cat10A": ["Cat 10A", "Category 10A", "Cat10A", "10A"],
        "cat10B": ["Cat 10B", "Category 10B", "Cat10B", "10B"],
        "cat11A": ["Cat 11A", "Category 11A", "Cat11A", "11A"],
        "cat11B": ["Cat 11B", "Category 11B", "Cat11B", "11B"],
        "cat12": ["Cat 12", "Category 12", "Cat12", "12"],
    }


def _find_column(headers: list[str], possible_names: list[str]) -> Optional[int]:
    """Find column index by trying multiple possible names."""
    headers_lower = [h.lower().strip() for h in headers]
    
    for name in possible_names:
        name_lower = name.lower().strip()
        if name_lower in headers_lower:
            return headers_lower.index(name_lower)
    
    return None


def _parse_percentage(value: str) -> float:
    """
    Parse a percentage value from CSV.
    
    Handles formats like:
    - "0.5%" -> 0.5
    - "0.5" -> 0.5
    - "P" or "Prohibited" -> 0.0
    - "-" or "N/A" -> 100.0 (no restriction)
    - Empty -> 100.0
    """
    if not value or value.strip() in ("-", "N/A", "NR", ""):
        return 100.0
    
    value = value.strip().upper()
    
    # Prohibited
    if value.startswith("P") or "PROHIBIT" in value:
        return 0.0
    
    # Remove % sign and parse
    value = value.replace("%", "").strip()
    
    try:
        return float(value)
    except ValueError:
        return 100.0


# =============================================================================
# CSV Parsing
# =============================================================================

def parse_ifra_csv(filepath: Path) -> list[IFRAEntry]:
    """
    Parse IFRA standards from a CSV file.
    
    Supports flexible column mapping to handle different CSV formats.
    
    Args:
        filepath: Path to CSV file
    
    Returns:
        List of parsed IFRAEntry objects
    """
    logger = get_logger()
    entries = []
    
    with open(filepath, "r", encoding="utf-8-sig") as f:
        # Try to detect delimiter
        sample = f.read(1024)
        f.seek(0)
        
        delimiter = ","
        if sample.count(";") > sample.count(","):
            delimiter = ";"
        elif sample.count("\t") > sample.count(","):
            delimiter = "\t"
        
        reader = csv.reader(f, delimiter=delimiter)
        
        # Read until we find the header row
        headers = None
        for row in reader:
            if not row or (row[0] and row[0].strip().startswith(("#", "//"))):
                continue
            
            # Check if this row looks like headers (contains Name/Ingredient)
            if _find_column(row, IFRACSVColumns.NAME) is not None:
                headers = row
                break
        
        if not headers:
            logger.error(f"No valid headers found in {filepath}")
            return []
        
        logger.debug(f"CSV headers: {headers}")
        
        # Find column indices
        name_idx = _find_column(headers, IFRACSVColumns.NAME)
        cas_idx = _find_column(headers, IFRACSVColumns.CAS)
        amendment_idx = _find_column(headers, IFRACSVColumns.AMENDMENT)
        type_idx = _find_column(headers, IFRACSVColumns.TYPE)
        risk_idx = _find_column(headers, IFRACSVColumns.RISK)
        synonyms_idx = _find_column(headers, IFRACSVColumns.SYNONYMS)
        formula_idx = _find_column(headers, IFRACSVColumns.FORMULA)
        
        # Find category columns
        category_indices = {}
        for cat_name, possible_names in IFRACSVColumns.CATEGORY_PATTERNS.items():
            idx = _find_column(headers, possible_names)
            if idx is not None:
                category_indices[cat_name] = idx
        
        if name_idx is None:
            logger.error(f"Could not find Name column in {filepath}")
            return []
        
        logger.info(f"Parsing IFRA CSV with {len(category_indices)} category columns")
        
        # Parse rows
        for row_num, row in enumerate(reader, start=2):
            try:
                if len(row) <= name_idx:
                    continue
                
                name = row[name_idx].strip()
                if not name:
                    continue
                
                entry = IFRAEntry(name=name)
                
                # Basic fields
                if cas_idx is not None and len(row) > cas_idx:
                    entry.cas = row[cas_idx].strip() or None
                
                if amendment_idx is not None and len(row) > amendment_idx:
                    entry.amendment = row[amendment_idx].strip() or None
                
                if type_idx is not None and len(row) > type_idx:
                    entry.type = row[type_idx].strip() or None
                
                if risk_idx is not None and len(row) > risk_idx:
                    entry.risk = row[risk_idx].strip() or None
                
                if synonyms_idx is not None and len(row) > synonyms_idx:
                    entry.synonyms = row[synonyms_idx].strip() or None
                
                if formula_idx is not None and len(row) > formula_idx:
                    entry.formula = row[formula_idx].strip() or None
                
                # Category values
                for cat_name, idx in category_indices.items():
                    if len(row) > idx:
                        value = _parse_percentage(row[idx])
                        setattr(entry, cat_name, value)
                
                entries.append(entry)
                
            except Exception as e:
                logger.warning(f"Error parsing row {row_num}: {e}")
                continue
        
        logger.info(f"Parsed {len(entries)} IFRA entries from {filepath}")
    
    return entries


# =============================================================================
# Online IFRA Sources (Placeholder)
# =============================================================================

def download_ifra_standards(
    url: Optional[str] = None,
    output_dir: Optional[Path] = None
) -> Optional[Path]:
    """
    Download IFRA standards from online source.
    
    Note: The official IFRA website may require authentication or
    have terms of service restrictions. This is a placeholder
    implementation.
    
    For production use, it's recommended to:
    1. Download the CSV manually from IFRA
    2. Place it in the automation/data folder
    3. Use parse_ifra_csv() directly
    
    Args:
        url: URL to download from (optional)
        output_dir: Directory to save the file
    
    Returns:
        Path to downloaded file, or None if download failed
    """
    logger = get_logger()
    config = get_config()
    
    # Default output directory
    if output_dir is None:
        output_dir = Path(config.data_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Note: This is a placeholder. The actual IFRA database
    # may not be freely downloadable.
    logger.warning(
        "IFRA online download not implemented. "
        "Please place your IFRA CSV file in the data folder."
    )
    
    # Check if a file already exists in the data folder
    for ext in ["csv", "xlsx", "json"]:
        potential_file = output_dir / f"ifra_standards.{ext}"
        if potential_file.exists():
            logger.info(f"Found existing IFRA file: {potential_file}")
            return potential_file
    
    return None


# =============================================================================
# Main Sync Function
# =============================================================================

def sync_ifra_library(
    source: Optional[str] = None,
    owner_id: Optional[str] = None,
    fill_missing_only: bool = True,
    db: Optional[DatabaseAdapter] = None,
) -> SyncResult:
    """
    Synchronize IFRA standards library.
    
    Process:
    1. Load IFRA entries from CSV file (or download if URL provided)
    2. For each entry, match by CAS number or name
    3. Insert new or update existing entries
    4. Respect user customizations if fill_missing_only=True
    
    Args:
        source: Path to CSV file or URL (uses default if not provided)
        owner_id: Database owner ID
        fill_missing_only: If True, only populate NULL fields
        db: Optional database adapter
    
    Returns:
        SyncResult with counts and status
    """
    logger = get_logger()
    config = get_config()
    
    db = db or get_db()
    owner = owner_id or config.owner_id
    result = SyncResult(success=False)
    
    try:
        # Determine source
        if source is None:
            # Try default locations
            data_dir = Path(config.data_dir)
            for filename in ["ifra_standards.csv", "ifra.csv", "IFRA_Library.csv"]:
                potential_path = data_dir / filename
                if potential_path.exists():
                    source = str(potential_path)
                    break
        
        if source is None:
            result.errors.append(
                "No IFRA source file found. Please place a CSV file "
                "in the data folder or provide a --source path."
            )
            logger.error(result.errors[0])
            return result
        
        source_path = Path(source)
        
        # Check if it's a URL
        if source.startswith(("http://", "https://")):
            downloaded = download_ifra_standards(url=source)
            if downloaded:
                source_path = downloaded
            else:
                result.errors.append(f"Failed to download from {source}")
                return result
        
        # Parse the CSV file
        if not source_path.exists():
            result.errors.append(f"Source file not found: {source_path}")
            logger.error(result.errors[0])
            return result
        
        entries = parse_ifra_csv(source_path)
        result.total_entries = len(entries)
        
        if not entries:
            result.errors.append("No entries parsed from CSV file")
            logger.warning(result.errors[0])
            return result
        
        logger.info(f"Syncing {len(entries)} IFRA entries to database")
        
        # Process each entry
        for entry in entries:
            try:
                ifra_data = entry.to_dict()
                _, was_created = db.upsert_ifra_entry(
                    ifra_data,
                    fill_missing_only=fill_missing_only,
                    owner_id=owner,
                )
                
                if was_created:
                    result.inserted += 1
                else:
                    result.updated += 1
                    
            except Exception as e:
                result.skipped += 1
                result.errors.append(f"Error processing '{entry.name}': {e}")
                logger.warning(f"Skipped '{entry.name}': {e}")
        
        result.success = True
        logger.info(
            f"IFRA sync complete: {result.inserted} inserted, "
            f"{result.updated} updated, {result.skipped} skipped"
        )
        
    except Exception as e:
        result.errors.append(str(e))
        logger.error(f"IFRA sync failed: {e}")
    
    return result


def update_ingredients_from_ifra(
    owner_id: Optional[str] = None,
    db: Optional[DatabaseAdapter] = None,
) -> dict[str, int]:
    """
    Update ingredient IFRA limits from the IFRALibrary table.
    
    Matches ingredients to IFRA entries by CAS number and copies
    the category limits.
    
    Args:
        owner_id: Database owner ID
        db: Optional database adapter
    
    Returns:
        Dictionary with counts: matched, updated, skipped
    """
    logger = get_logger()
    config = get_config()
    
    db = db or get_db()
    owner = owner_id or config.owner_id
    
    counts = {"matched": 0, "updated": 0, "skipped": 0}
    
    # Get all ingredients with CAS numbers
    ingredients = db.get_all_ingredients(owner_id=owner)
    
    for ingredient in ingredients:
        if not ingredient.cas:
            counts["skipped"] += 1
            continue
        
        # Find matching IFRA entry
        ifra_entry = db.get_ifra_entry_by_cas(ingredient.cas, owner_id=owner)
        
        if not ifra_entry:
            counts["skipped"] += 1
            continue
        
        counts["matched"] += 1
        
        # Build update data with IFRA limits
        update_data = {
            "name": ingredient.name,
        }
        
        # Copy category limits
        category_fields = [
            "cat1", "cat2", "cat3", "cat4", "cat5A", "cat5B", "cat5C", "cat5D",
            "cat6", "cat7A", "cat7B", "cat8", "cat9", "cat10A", "cat10B",
            "cat11A", "cat11B", "cat12"
        ]
        
        for field in category_fields:
            ifra_value = getattr(ifra_entry, field, 100.0)
            update_data[field] = ifra_value
        
        # Update ingredient
        try:
            db.upsert_ingredient(
                update_data,
                fill_missing_only=True,
                owner_id=owner,
            )
            counts["updated"] += 1
        except Exception as e:
            logger.warning(f"Failed to update '{ingredient.name}': {e}")
    
    logger.info(
        f"IFRA limits update: {counts['matched']} matched, "
        f"{counts['updated']} updated, {counts['skipped']} skipped"
    )
    
    return counts
