"""
Smart ingredient enrichment module.

Combines data from multiple sources to enrich ingredient records
with CAS numbers, odor profiles, IFRA limits, and more.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from config import get_config, get_logger
from db_adapter import get_db, DatabaseAdapter
from scraper import (
    get_scraper,
    FragranceScraper,
    IngredientProfile,
    PubChemData,
)


@dataclass
class EnrichmentResult:
    """Result of an enrichment operation."""
    ingredient_name: str
    success: bool
    was_created: bool = False
    updated_fields: list[str] = field(default_factory=list)
    error_message: Optional[str] = None
    sources_used: list[str] = field(default_factory=list)


@dataclass
class MergedIngredientData:
    """Combined data from multiple sources."""
    name: str
    cas: Optional[str] = None
    cid: Optional[int] = None
    chemical_name: Optional[str] = None
    formula: Optional[str] = None
    molecularWeight: Optional[str] = None
    profile: Optional[str] = None  # Odor description
    type: Optional[str] = None  # AC/EO/etc
    strength: Optional[str] = None
    tenacity: Optional[str] = None
    appearance: Optional[str] = None
    flash_point: Optional[str] = None
    synonyms: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database upsert."""
        result = {}
        
        for field_name in [
            "name", "cas", "cid", "chemical_name", "formula",
            "molecularWeight", "profile", "type", "strength",
            "tenacity", "appearance", "flash_point"
        ]:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value
        
        return result


# =============================================================================
# Name Normalization
# =============================================================================

# Common ingredient name aliases
INGREDIENT_ALIASES: dict[str, list[str]] = {
    "bergamot": ["bergamot oil", "bergamot essential oil", "citrus bergamia"],
    "lavender": ["lavender oil", "lavandula angustifolia", "lavender essential oil"],
    "rose": ["rose oil", "rosa damascena", "rose absolute", "rose otto"],
    "jasmine": ["jasmine absolute", "jasminum grandiflorum", "jasmine oil"],
    "sandalwood": ["sandalwood oil", "santalum album", "east indian sandalwood"],
    "vanilla": ["vanilla absolute", "vanillin", "vanilla extract"],
    "musk": ["musk ketone", "muscone", "white musk"],
    "amber": ["ambergris", "amber accord", "labdanum"],
    "patchouli": ["patchouli oil", "pogostemon cablin"],
    "vetiver": ["vetiver oil", "vetiveria zizanioides"],
    "cedarwood": ["cedarwood oil", "cedrus atlantica", "virginia cedar"],
    "lemon": ["lemon oil", "citrus limon", "lemon essential oil"],
    "orange": ["orange oil", "citrus sinensis", "sweet orange oil"],
    "ylang ylang": ["ylang ylang oil", "cananga odorata"],
    "geranium": ["geranium oil", "pelargonium graveolens"],
    "frankincense": ["frankincense oil", "boswellia sacra", "olibanum"],
    "myrrh": ["myrrh oil", "commiphora myrrha"],
    "benzoin": ["benzoin resinoid", "styrax benzoin"],
    "tonka": ["tonka bean absolute", "dipteryx odorata", "coumarin"],
    "oud": ["oud oil", "agarwood", "aquilaria"],
}

# Odor family mappings
ODOR_FAMILY_MAPPING: dict[str, str] = {
    "citrus": "Citrus",
    "woody": "Woody",
    "floral": "Floral",
    "oriental": "Oriental",
    "fresh": "Fresh",
    "green": "Green",
    "fruity": "Fruity",
    "spicy": "Spicy",
    "balsamic": "Balsamic",
    "amber": "Amber",
    "musk": "Musky",
    "aquatic": "Aquatic",
    "marine": "Marine",
    "gourmand": "Gourmand",
    "powdery": "Powdery",
    "leather": "Leather",
    "animalic": "Animalic",
    "herbal": "Herbal",
    "aromatic": "Aromatic",
    "earthy": "Earthy",
}


def normalize_ingredient_name(name: str) -> str:
    """
    Normalize an ingredient name for consistent searching.
    
    Handles common variations, aliases, and formatting.
    
    Args:
        name: Raw ingredient name
    
    Returns:
        Normalized name suitable for searching
    """
    # Clean whitespace and lowercase
    normalized = name.strip().lower()
    
    # Remove common suffixes that may not be in databases
    suffixes_to_remove = [
        " essential oil",
        " absolute",
        " resinoid", 
        " concrète",
        " co2 extract",
        " oil",
    ]
    
    for suffix in suffixes_to_remove:
        if normalized.endswith(suffix):
            base_name = normalized[:-len(suffix)].strip()
            # Return the full version if we have an alias for the base
            if base_name in INGREDIENT_ALIASES:
                return INGREDIENT_ALIASES[base_name][0]
            break
    
    # Check if this is an alias
    for primary, aliases in INGREDIENT_ALIASES.items():
        if normalized == primary or normalized in [a.lower() for a in aliases]:
            # Return the first (preferred) alias
            return aliases[0]
    
    return name.strip()


def get_search_variants(name: str) -> list[str]:
    """
    Get search variants for an ingredient name.
    
    Returns multiple forms to try if the first search fails.
    """
    normalized = normalize_ingredient_name(name)
    variants = [normalized]
    
    # Add the original name if different
    if name.strip() != normalized:
        variants.append(name.strip())
    
    # Check for aliases
    name_lower = name.strip().lower()
    for primary, aliases in INGREDIENT_ALIASES.items():
        if name_lower == primary or name_lower in [a.lower() for a in aliases]:
            variants.extend(aliases)
            break
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variants = []
    for v in variants:
        v_lower = v.lower()
        if v_lower not in seen:
            seen.add(v_lower)
            unique_variants.append(v)
    
    return unique_variants[:5]  # Limit to 5 variants


def infer_ingredient_type(name: str, profile: Optional[str] = None) -> Optional[str]:
    """
    Infer ingredient type (AC/EO/etc) from name and profile.
    
    Returns one of: AC (Aroma Chemical), EO (Essential Oil), Carrier, Solvent, etc.
    """
    name_lower = name.lower()
    profile_lower = (profile or "").lower()
    
    # Essential oils typically have these patterns
    if any(kw in name_lower for kw in ["essential oil", " eo ", "oil of"]):
        return "EO"
    
    # Absolutes and concretes
    if any(kw in name_lower for kw in ["absolute", "concrète", "resinoid"]):
        return "EO"  # Classify with natural extracts
    
    # Carriers and solvents
    if any(kw in name_lower for kw in ["alcohol", "ethanol", "dpg", "ipm"]):
        return "Solvent"
    
    if any(kw in name_lower for kw in ["fractionated coconut", "jojoba", "carrier"]):
        return "Carrier"
    
    # Synthetic musks and aroma chemicals
    synthetic_indicators = [
        "musk", "aldehyde", "ketone", "ester", "acetate",
        "ionone", "coumarin", "vanillin", "heliotropin"
    ]
    if any(kw in name_lower for kw in synthetic_indicators):
        return "AC"
    
    # Check profile for clues
    if "synthetic" in profile_lower or "aroma chemical" in profile_lower:
        return "AC"
    
    if "natural" in profile_lower or "botanical" in profile_lower:
        return "EO"
    
    return None  # Unknown


def infer_tenacity(name: str, profile: Optional[str] = None) -> Optional[str]:
    """
    Infer ingredient tenacity/longevity from name and profile.
    
    Returns hours as a string (e.g., "24+ hours", "4-6 hours").
    """
    name_lower = name.lower()
    profile_lower = (profile or "").lower()
    
    # Base notes typically have high tenacity
    base_note_keywords = [
        "musk", "amber", "sandalwood", "vetiver", "patchouli",
        "oud", "benzoin", "vanilla", "tonka", "labdanum",
        "cedarwood", "oak", "leather"
    ]
    
    # Top notes have low tenacity
    top_note_keywords = [
        "lemon", "bergamot", "grapefruit", "mandarin", "lime",
        "eucalyptus", "mint", "basil"
    ]
    
    # Heart notes have medium tenacity
    heart_note_keywords = [
        "rose", "jasmine", "ylang", "geranium", "lavender",
        "iris", "violet"
    ]
    
    if any(kw in name_lower for kw in base_note_keywords):
        return "24+ hours"
    
    if any(kw in name_lower for kw in top_note_keywords):
        return "2-4 hours"
    
    if any(kw in name_lower for kw in heart_note_keywords):
        return "6-12 hours"
    
    return None


# =============================================================================
# Data Merging
# =============================================================================

def merge_data_sources(
    name: str,
    tgsc_data: Optional[IngredientProfile],
    pubchem_data: Optional[PubChemData],
) -> MergedIngredientData:
    """
    Intelligently combine data from multiple sources.
    
    Priority:
    1. TGSC for fragrance-specific data (odor, strength)
    2. PubChem for chemical data (CAS, formula, molecular weight)
    3. Inferred data as fallback
    
    Args:
        name: Original ingredient name
        tgsc_data: Data from The Good Scents Company
        pubchem_data: Data from PubChem
    
    Returns:
        MergedIngredientData with best available data
    """
    merged = MergedIngredientData(name=name)
    
    # Track sources
    if tgsc_data:
        merged.sources.append("TGSC")
    if pubchem_data:
        merged.sources.append("PubChem")
    
    # CAS Number: Prefer TGSC (more reliable for fragrances)
    if tgsc_data and tgsc_data.cas:
        merged.cas = tgsc_data.cas
    elif pubchem_data and pubchem_data.cas:
        merged.cas = pubchem_data.cas
    
    # PubChem CID
    if pubchem_data:
        merged.cid = pubchem_data.cid
    
    # Chemical name (IUPAC)
    if pubchem_data and pubchem_data.iupac_name:
        merged.chemical_name = pubchem_data.iupac_name
    
    # Molecular formula
    if pubchem_data and pubchem_data.molecular_formula:
        merged.formula = pubchem_data.molecular_formula
    elif tgsc_data and tgsc_data.molecular_formula:
        merged.formula = tgsc_data.molecular_formula
    
    # Molecular weight
    if pubchem_data and pubchem_data.molecular_weight:
        merged.molecularWeight = pubchem_data.molecular_weight
    elif tgsc_data and tgsc_data.molecular_weight:
        merged.molecularWeight = tgsc_data.molecular_weight
    
    # Odor profile (fragrance-specific - TGSC only)
    if tgsc_data and tgsc_data.odor_description:
        merged.profile = tgsc_data.odor_description
    
    # Strength (TGSC only)
    if tgsc_data and tgsc_data.odor_strength:
        merged.strength = tgsc_data.odor_strength
    
    # Appearance
    if tgsc_data and tgsc_data.appearance:
        merged.appearance = tgsc_data.appearance
    
    # Flash point
    if tgsc_data and tgsc_data.flash_point:
        merged.flash_point = tgsc_data.flash_point
    
    # Infer type if not available
    if not merged.type:
        merged.type = infer_ingredient_type(name, merged.profile)
    
    # Infer tenacity if not available
    if not merged.tenacity:
        merged.tenacity = infer_tenacity(name, merged.profile)
    
    # Combine synonyms
    synonyms = []
    if tgsc_data:
        synonyms.extend(tgsc_data.synonyms)
    if pubchem_data:
        synonyms.extend(pubchem_data.synonyms)
    merged.synonyms = list(set(synonyms))[:50]  # Dedupe and limit
    
    return merged


# =============================================================================
# Main Enrichment Function
# =============================================================================

def enrich_ingredient(
    name: str,
    owner_id: Optional[str] = None,
    fill_missing_only: bool = True,
    db: Optional[DatabaseAdapter] = None,
    scraper: Optional[FragranceScraper] = None,
) -> EnrichmentResult:
    """
    Main enrichment function for a single ingredient.
    
    Process:
    1. Normalize the ingredient name
    2. Search TGSC for fragrance-specific data
    3. Search PubChem for chemical data
    4. Merge data from all sources
    5. Update the database (filling missing fields only by default)
    6. Add synonyms
    
    Args:
        name: Ingredient name to enrich
        owner_id: Database owner ID (uses default if not provided)
        fill_missing_only: If True, only populate NULL fields
        db: Optional database adapter (uses global if not provided)
        scraper: Optional scraper (uses global if not provided)
    
    Returns:
        EnrichmentResult with status and updated fields
    """
    logger = get_logger()
    config = get_config()
    
    db = db or get_db()
    scraper = scraper or get_scraper()
    owner = owner_id or config.owner_id
    
    result = EnrichmentResult(ingredient_name=name, success=False)
    
    try:
        logger.info(f"Starting enrichment for: {name}")
        
        # Get search variants
        variants = get_search_variants(name)
        logger.debug(f"Search variants: {variants}")
        
        # Search TGSC
        tgsc_data = None
        for variant in variants:
            tgsc_data = scraper.search_tgsc(variant)
            if tgsc_data:
                break
        
        # Search PubChem
        pubchem_data = None
        for variant in variants:
            pubchem_data = scraper.search_pubchem(variant)
            if pubchem_data:
                break
        
        # Check if we found any data
        if not tgsc_data and not pubchem_data:
            result.error_message = f"No data found for '{name}' in any source"
            logger.warning(result.error_message)
            return result
        
        # Merge data from all sources
        merged = merge_data_sources(name, tgsc_data, pubchem_data)
        result.sources_used = merged.sources
        
        # Upsert to database
        ingredient_data = merged.to_dict()
        ingredient, was_created = db.upsert_ingredient(
            ingredient_data,
            fill_missing_only=fill_missing_only,
            owner_id=owner,
        )
        
        result.was_created = was_created
        result.updated_fields = list(ingredient_data.keys())
        
        # Add synonyms
        for synonym in merged.synonyms[:20]:  # Limit synonyms
            if synonym.lower() != name.lower():
                db.add_synonym(
                    ingredient_name=name,
                    synonym=synonym,
                    source=", ".join(merged.sources),
                    cid=merged.cid,
                    owner_id=owner,
                )
        
        result.success = True
        logger.info(
            f"Enrichment complete for '{name}': "
            f"{'created' if was_created else 'updated'}, "
            f"fields: {result.updated_fields}"
        )
        
    except Exception as e:
        result.error_message = str(e)
        logger.error(f"Enrichment failed for '{name}': {e}")
    
    return result


def enrich_all_ingredients(
    owner_id: Optional[str] = None,
    fill_missing_only: bool = True,
    limit: Optional[int] = None,
) -> list[EnrichmentResult]:
    """
    Enrich all existing ingredients in the database.
    
    Args:
        owner_id: Database owner ID
        fill_missing_only: Only populate NULL fields
        limit: Maximum number of ingredients to process
    
    Returns:
        List of EnrichmentResult for each ingredient
    """
    logger = get_logger()
    db = get_db()
    config = get_config()
    
    owner = owner_id or config.owner_id
    
    # Get all ingredients
    ingredients = db.get_all_ingredients(owner_id=owner, limit=limit)
    logger.info(f"Found {len(ingredients)} ingredients to enrich")
    
    results = []
    for ingredient in ingredients:
        result = enrich_ingredient(
            name=ingredient.name,
            owner_id=owner,
            fill_missing_only=fill_missing_only,
        )
        results.append(result)
    
    # Summary
    successful = sum(1 for r in results if r.success)
    created = sum(1 for r in results if r.was_created)
    
    logger.info(
        f"Enrichment complete: {successful}/{len(results)} successful, "
        f"{created} new ingredients created"
    )
    
    return results


def batch_enrich_from_file(
    filepath: str,
    owner_id: Optional[str] = None,
    fill_missing_only: bool = True,
) -> list[EnrichmentResult]:
    """
    Batch enrich ingredients from a text file (one name per line).
    
    Args:
        filepath: Path to text file with ingredient names
        owner_id: Database owner ID
        fill_missing_only: Only populate NULL fields
    
    Returns:
        List of EnrichmentResult for each ingredient
    """
    logger = get_logger()
    logger.info(f"Batch enriching from {filepath}")
    
    with open(filepath, "r", encoding="utf-8") as f:
        # Read non-empty lines that don't start with #
        names = [
            line.strip() for line in f 
            if line.strip() and not line.strip().startswith("#")
        ]
    
    logger.info(f"Found {len(names)} valid ingredients to process")
    
    results = []
    for name in names:
        result = enrich_ingredient(
            name=name,
            owner_id=owner_id,
            fill_missing_only=fill_missing_only,
        )
        results.append(result)
    
    return results
