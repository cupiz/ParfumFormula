"""
Flask API Server for ParfumVault Automation

Exposes the ingredient scraper functionality via REST API
for integration with the PHP frontend.
"""

import os
from flask import Flask, jsonify, request
from flask_cors import CORS

# Import local modules
from config import get_config, setup_logging
from scraper import get_scraper
from models import IngredientProfile, PubChemData

app = Flask(__name__)
CORS(app)  # Enable CORS for PHP frontend

logger = setup_logging()


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker/K8s."""
    return jsonify({
        "status": "healthy",
        "service": "parfum-automation-api",
        "version": "1.0.0"
    })


@app.route('/search', methods=['GET'])
def search_ingredient():
    """
    Search for an ingredient across multiple sources.
    
    Query Parameters:
        name (str): Ingredient name to search for
        
    Returns:
        JSON with combined data from TGSC and PubChem
    """
    name = request.args.get('name', '').strip()
    
    if not name:
        return jsonify({
            "success": False,
            "error": "Missing 'name' parameter"
        }), 400
    
    logger.info(f"API search request for: {name}")
    
    try:
        scraper = get_scraper()
        
        # Search TGSC first (fragrance-specific data)
        tgsc_data = scraper.search_tgsc(name)
        
        # Search PubChem (chemical data)
        pubchem_data = scraper.search_pubchem(name)
        
        if not tgsc_data and not pubchem_data:
            return jsonify({
                "success": False,
                "error": f"No data found for '{name}'",
                "searched_sources": ["TGSC", "PubChem"]
            }), 404
        
        # Merge data from both sources
        result = merge_ingredient_data(name, tgsc_data, pubchem_data)
        
        return jsonify({
            "success": True,
            "ingredient": result,
            "sources": {
                "tgsc": tgsc_data is not None,
                "pubchem": pubchem_data is not None
            }
        })
        
    except Exception as e:
        logger.error(f"API search error for '{name}': {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def merge_ingredient_data(
    name: str,
    tgsc: IngredientProfile = None,
    pubchem: PubChemData = None
) -> dict:
    """
    Merge data from multiple sources into a unified ingredient object.
    
    Priority:
    - CAS: PubChem > TGSC (PubChem is more authoritative)
    - Formula: PubChem
    - Odor: TGSC (fragrance-specific)
    - Weight: PubChem
    """
    result = {
        "name": name,
        "cas": None,
        "formula": None,
        "molecular_weight": None,
        "iupac_name": None,
        "cid": None,
        "odor_description": None,
        "odor_family": None,
        "fema": None,
        "synonyms": [],
        "sources": []
    }
    
    # Merge TGSC data
    if tgsc:
        result["sources"].append("TGSC")
        if tgsc.cas:
            result["cas"] = tgsc.cas
        if tgsc.odor_description:
            result["odor_description"] = tgsc.odor_description
        if tgsc.odor_family:
            result["odor_family"] = tgsc.odor_family
        if tgsc.molecular_formula:
            result["formula"] = tgsc.molecular_formula
        if tgsc.molecular_weight:
            result["molecular_weight"] = tgsc.molecular_weight
        # Check for FEMA in uses
        for use in tgsc.uses:
            if use.startswith("FEMA"):
                result["fema"] = use
                break
    
    # Merge PubChem data (higher priority for chemical data)
    if pubchem:
        result["sources"].append("PubChem")
        if pubchem.cas:
            result["cas"] = pubchem.cas  # Override with PubChem CAS
        if pubchem.molecular_formula:
            result["formula"] = pubchem.molecular_formula
        if pubchem.molecular_weight:
            result["molecular_weight"] = pubchem.molecular_weight
        if pubchem.iupac_name:
            result["iupac_name"] = pubchem.iupac_name
        if pubchem.cid:
            result["cid"] = pubchem.cid
        if pubchem.synonyms:
            result["synonyms"] = pubchem.synonyms[:10]  # Limit to 10
    
    return result


@app.route('/enrich', methods=['POST'])
def enrich_and_save():
    """
    Search, enrich, and save ingredient to database.
    
    This is the endpoint called when user clicks "Add to Library".
    
    Body (JSON):
        name (str): Ingredient name
        owner_id (str): Database owner ID (optional)
        
    Returns:
        JSON with saved ingredient data
    """
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({
            "success": False,
            "error": "Missing 'name' in request body"
        }), 400
    
    name = data['name'].strip()
    owner_id = data.get('owner_id', '1')
    
    logger.info(f"API enrich request for: {name}")
    
    try:
        # Import enrichment module
        from enrichment import enrich_ingredient
        from db_adapter import get_db
        
        db = get_db()
        result = enrich_ingredient(name, owner_id=owner_id, db=db)
        
        if result.success:
            return jsonify({
                "success": True,
                "action": result.action,
                "ingredient": {
                    "name": name,
                    "fields": result.fields_populated,
                    "sources": result.sources_used
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": result.error
            }), 500
            
    except Exception as e:
        logger.error(f"API enrich error for '{name}': {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.getenv('API_PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting ParfumVault Automation API on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
