# ParfumVault Data Auto-Population Module

A Python-based automation microservice that automatically finds, fetches, and inserts
ingredient data into the ParfumVault database, eliminating manual entry.

## Features

- **Smart Ingredient Enrichment**: Input "Bergamot" and automatically fetch CAS number,
  molecular formula, weight, and IFRA limits
- **Multi-Source Data**: Combines data from PubChem (primary) and TGSC (odor profiles)
- **IFRA Standards Sync**: Parse official IFRA limits from CSV and populate compliance tables
- **REST API Server**: Flask-based API for real-time ingredient search from the web UI
- **Auto-Search Online**: Integrated with PHP frontend—search 100M+ compounds when not found locally
- **Safe Updates**: Only fills missing fields—never overwrites user customizations
- **Rate Limiting**: Respects external servers with configurable delays
- **Caching**: Avoids redundant requests with response caching

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- ParfumVault stack running (database must be accessible)

### Build the Automation Container

```bash
cd /path/to/parfumvault

# Build with the override file
docker compose -f docker-compose/compose.yaml -f docker-compose.override.yml build automation
```

### Test Database Connection

```bash
docker compose -f docker-compose/compose.yaml -f docker-compose.override.yml run automation python ingestor.py --test-db
```

### Enrich a Single Ingredient

```bash
# Enrich "Bergamot" - fetches CAS, odor profile, etc.
docker compose -f docker-compose/compose.yaml -f docker-compose.override.yml run automation \
    python ingestor.py --target ingredient --name "Bergamot"
```

### Sync IFRA Library

```bash
# Place your IFRA CSV file in automation/data/ifra_standards.csv first

docker compose -f docker-compose/compose.yaml -f docker-compose.override.yml run automation \
    python ingestor.py --target ifra --source /app/data/ifra_standards.csv
```

### Batch Enrich from File

```bash
# Create a text file with ingredient names (one per line)
# automation/data/ingredients.txt

docker compose -f docker-compose/compose.yaml -f docker-compose.override.yml run automation \
    python ingestor.py --target batch --file /app/data/ingredients.txt
```

### Enrich All Existing Ingredients

```bash
# Process all ingredients already in the database
docker compose -f docker-compose/compose.yaml -f docker-compose.override.yml run automation \
    python ingestor.py --target all --limit 50
```

## CLI Reference

```text
Usage: ingestor.py [OPTIONS]

Options:
  --target [ingredient|ifra|batch|all|update-ifra-limits]
                                  Target operation type
  --name TEXT                     Ingredient name (for --target ingredient)
  --source PATH                   Source file path (for --target ifra)
  --file PATH                     Batch file with ingredient names
  --limit INTEGER                 Limit number of ingredients (for --target all)
  --owner-id TEXT                 Owner ID for database records
  --overwrite                     Overwrite existing data
  --test-db                       Test database connection and exit
  -v, --verbose                   Enable verbose logging
  --help                          Show this message and exit
```

### Additional Commands

```bash
# Quick enrich multiple ingredients
docker compose run automation python ingestor.py quick "Lavender" "Rose" "Jasmine"

# Show database status
docker compose run automation python ingestor.py status

# Update ingredient IFRA limits from library
docker compose run automation python ingestor.py --target update-ifra-limits
```

## REST API Server

The automation module includes a **Flask-based REST API** that integrates with the PHP frontend for real-time ingredient search.

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (returns service status) |
| `GET` | `/search?name=xxx` | Search TGSC + PubChem for ingredient |
| `POST` | `/enrich` | Search and save ingredient to database |

### Example Response (`/search?name=Linalool`)

```json
{
  "success": true,
  "ingredient": {
    "name": "Linalool",
    "cas": "78-70-6",
    "cid": 6549,
    "formula": "C10H18O",
    "molecular_weight": "154.25",
    "iupac_name": "3,7-dimethylocta-1,6-dien-3-ol",
    "odor_description": "floral woody citrus",
    "fema": "FEMA 2635"
  },
  "sources": {"tgsc": true, "pubchem": true}
}
```

### Running the API Server

The API server runs automatically via Docker Compose on port 5001 (internal network).
For standalone testing:

```bash
cd automation
pip install -r requirements.txt
python api_server.py  # Runs on http://localhost:5001
```

## Configuration

Configure via environment variables in `docker-compose.override.yml`:

| Variable             | Default  | Description                             |
| -------------------- | -------- | --------------------------------------- |
| `DB_HOST`            | `pvdb`   | Database hostname                       |
| `DB_USER`            | `pvault` | Database username                       |
| `DB_PASS`            | `pvault` | Database password                       |
| `DB_NAME`            | `pvault` | Database name                           |
| `OWNER_ID`           | `1`      | Default owner for inserted records      |
| `SCRAPER_DELAY`      | `2`      | Seconds between scraper requests        |
| `LOG_LEVEL`          | `INFO`   | Logging level (DEBUG/INFO/WARNING/ERROR)|
| `USER_AGENT_ROTATION`| `true`   | Enable User-Agent rotation              |
| `CACHE_ENABLED`      | `true`   | Enable response caching                 |
| `CACHE_TTL_HOURS`    | `24`     | Cache time-to-live in hours             |

## Data Sources

All sources verified working as of 2026-01-07.

### TGSC - The Good Scents Company

The premier fragrance ingredient database (search.php):

- CAS numbers and FEMA numbers
- **Odor descriptions** (citrus, floral, woody, etc.)
- Flavor descriptions
- Appearance and physical properties

### PubChem (NCBI)

The authoritative chemical database (REST API):

- CAS numbers (extracted from synonyms)
- Molecular formulas and weights
- IUPAC names
- PubChem CID
- Extensive synonym lists (50+ per compound)

## IFRA CSV Format

The module expects IFRA data in CSV format with these columns:

| Column              | Description                                        |
| ------------------- | -------------------------------------------------- |
| `Name`              | Material name                                      |
| `CAS`               | CAS registry number                                |
| `Amendment`         | IFRA amendment (e.g., "51st")                      |
| `Type`              | Prohibition/Restriction/Specification              |
| `Risk`              | Sensitization/Phototoxicity/etc.                   |
| `Cat 1` - `Cat 12`  | Category percentage limits (0-100, "P" = prohibited)|

See `data/ifra_standards_template.csv` for an example.

## Architecture

```text
automation/
├── __init__.py          # Package init
├── config.py            # Configuration management
├── models.py            # SQLAlchemy ORM models
├── db_adapter.py        # Database operations
├── scraper.py           # Web scraping (TGSC, PubChem)
├── enrichment.py        # Smart matcher logic
├── ifra_sync.py         # IFRA standards sync
├── ingestor.py          # Main CLI entry point
├── Dockerfile           # Container definition
├── requirements.txt     # Python dependencies
└── data/                # Data/cache directory
    └── ifra_standards_template.csv
```

## Updating Scraper Selectors

If the website structure changes, update the selector classes in `scraper.py`:

```python
class TGSCSelectors:
    """Update these if TGSC website structure changes."""
    SEARCH_URL = "http://www.thegoodscentscompany.com/search2.php"
    CAS_PATTERN = r"\b(\d{2,7}-\d{2}-\d)\b"
    # ... other selectors
```

## Safety Features

1. **Fill Missing Only**: By default, only NULL fields are populated
2. **Connection Pooling**: Efficient database connections
3. **Rate Limiting**: Configurable delays between requests
4. **Response Caching**: Avoids redundant API calls
5. **Retry Logic**: Automatic retry with exponential backoff

## License

MIT License - Same as ParfumVault
