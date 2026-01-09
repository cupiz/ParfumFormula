"""
Web scraping module for fragrance ingredient data.

Features:
- Rate limiting to respect external servers
- User-Agent rotation to avoid blocks
- Response caching to reduce redundant requests
- Clean, maintainable selector configuration
- Robust error handling with retries
"""

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import get_config, get_logger


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class IngredientProfile:
    """Scraped ingredient data from TGSC or similar sources."""
    name: str
    cas: Optional[str] = None
    odor_description: Optional[str] = None
    odor_family: Optional[str] = None
    odor_strength: Optional[str] = None  # Low/Medium/High/Extreme
    appearance: Optional[str] = None
    flash_point: Optional[str] = None
    specific_gravity: Optional[str] = None
    boiling_point: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[str] = None
    # New fields
    tenacity: Optional[str] = None
    logp: Optional[str] = None
    soluble: Optional[str] = None
    shelf_life: Optional[str] = None
    einecs: Optional[str] = None
    reach: Optional[str] = None
    
    synonyms: list[str] = field(default_factory=list)
    uses: list[str] = field(default_factory=list)
    source: str = "unknown"


@dataclass
class PubChemData:
    """Chemical data from PubChem API."""
    cid: int
    name: str
    cas: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[str] = None
    iupac_name: Optional[str] = None
    synonyms: list[str] = field(default_factory=list)


@dataclass
class IFRAData:
    """IFRA restriction data for an ingredient."""
    name: str
    cas: Optional[str] = None
    amendment: Optional[str] = None
    type: Optional[str] = None  # Prohibited/Restricted/Specified
    risk: Optional[str] = None
    categories: dict[str, float] = field(default_factory=dict)  # cat1: 0.5, etc.


# =============================================================================
# Selector Configuration (Easy to Update)
# =============================================================================

class TGSCSelectors:
    """
    CSS selectors for The Good Scents Company website.
    
    TGSC search is available at search.html and submits to search.php.
    The search returns HTML with ingredient data tables.
    
    Update these patterns if the website structure changes.
    """
    # Base URLs - VERIFIED WORKING
    BASE_URL = "http://www.thegoodscentscompany.com"
    SEARCH_URL = "http://www.thegoodscentscompany.com/search.php"
    SEARCH_PAGE = "http://www.thegoodscentscompany.com/search.html"
    
    # CAS pattern for extraction
    CAS_PATTERN = r"\b(\d{2,7}-\d{2}-\d)\b"
    
    # Odor-related keywords for extraction
    ODOR_KEYWORDS = ["odor", "smell", "aroma", "scent", "fragrance"]
    
    # Label patterns for table parsing (case-insensitive)
    LABEL_PATTERNS = {
        "cas": ["cas number", "cas", "cas#", "cas no"],
        "fema": ["fema", "fema no", "fema number"],
        "einecs": ["einecs", "einecs#", "ec number"],
        "reach": ["reach", "reach reg", "reach registration"],
        "odor": ["odor description", "odor", "aroma", "smell"],
        "odor_type": ["odor type", "odor family", "family", "note"],
        "flavor": ["flavor description", "flavor", "taste"],
        "strength": ["strength", "intensity", "odor strength"],
        "appearance": ["appearance", "physical form", "form"],
        "flash_point": ["flash point", "flashpoint"],
        "specific_gravity": ["specific gravity", "density", "sp. gr."],
        "boiling_point": ["boiling point", "bp", "b.p."],
        "molecular_formula": ["molecular formula", "formula", "mol formula"],
        "molecular_weight": ["molecular weight", "mol weight", "mw"],
        "synonyms": ["synonyms", "other names", "alternate names"],
        # New Enriched Fields
        "tenacity": ["substantivity", "tenacity", "lasting"],
        "logp": ["logp", "log p", "octanol water"],
        "soluble": ["soluble in", "solubility"],
        "shelf_life": ["shelf life", "shelf-life", "storage"],
    }


class CommonChemistryAPI:
    """
    Common Chemistry from CAS (Chemical Abstracts Service).
    
    Note: The API endpoint requires an X-API-KEY header.
    Public pages are available at:
    - Search results: https://commonchemistry.cas.org/results?q={name}
    - Detail page: https://commonchemistry.cas.org/detail?cas_rn={cas}&search={name}
    
    For scraping, we use the search results page which returns JSON data
    embedded in the JavaScript.
    
    Documentation: https://commonchemistry.cas.org/api
    """
    BASE_URL = "https://commonchemistry.cas.org"
    
    # Public URLs (no API key required, but rendered by JavaScript)
    SEARCH_RESULTS = "https://commonchemistry.cas.org/results?q={name}"
    DETAIL_PAGE = "https://commonchemistry.cas.org/detail?cas_rn={cas}&search={name}"
    
    # API endpoints (requires X-API-KEY header)
    API_BASE = "https://commonchemistry.cas.org/api"
    
    @staticmethod
    def search_by_name(name: str) -> str:
        """Get search results URL (public, but JavaScript-rendered)."""
        encoded = quote_plus(name)
        return CommonChemistryAPI.SEARCH_RESULTS.format(name=encoded)
    
    @staticmethod
    def get_detail_page(cas: str, name: str = "") -> str:
        """Get detail page URL."""
        encoded_name = quote_plus(name) if name else cas
        return CommonChemistryAPI.DETAIL_PAGE.format(cas=cas, name=encoded_name)
    
    @staticmethod
    def api_search(name: str) -> str:
        """API search URL (requires X-API-KEY header)."""
        encoded = quote_plus(name)
        return f"{CommonChemistryAPI.API_BASE}/search?q={encoded}"
    
    @staticmethod
    def api_detail(cas: str) -> str:
        """API detail URL (requires X-API-KEY header)."""
        return f"{CommonChemistryAPI.API_BASE}/detail?cas_rn={cas}"


class PubChemAPI:
    """
    PubChem REST API endpoints.
    
    Documentation: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
    """
    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    
    @staticmethod
    def search_by_name(name: str) -> str:
        """Get compound search URL by name."""
        encoded = quote_plus(name)
        return f"{PubChemAPI.BASE_URL}/compound/name/{encoded}/JSON"
    
    @staticmethod
    def get_synonyms(cid: int) -> str:
        """Get synonyms URL for a compound."""
        return f"{PubChemAPI.BASE_URL}/compound/cid/{cid}/synonyms/JSON"
    
    @staticmethod
    def get_properties(cid: int, properties: list[str]) -> str:
        """Get specific properties URL."""
        props = ",".join(properties)
        return f"{PubChemAPI.BASE_URL}/compound/cid/{cid}/property/{props}/JSON"


# =============================================================================
# Cache Implementation
# =============================================================================

class ResponseCache:
    """
    Simple file-based cache for HTTP responses.
    
    Reduces redundant requests to external services.
    """
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cache_path(self, url: str) -> Path:
        """Get cache file path for URL."""
        key = self._get_cache_key(url)
        return self.cache_dir / f"{key}.json"
    
    def get(self, url: str) -> Optional[dict]:
        """Get cached response if valid."""
        cache_path = self._get_cache_path(url)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            cached_time = datetime.fromisoformat(data["cached_at"])
            if datetime.now() - cached_time > self.ttl:
                cache_path.unlink()  # Expired
                return None
            
            return data["response"]
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def set(self, url: str, response: dict) -> None:
        """Cache a response."""
        cache_path = self._get_cache_path(url)
        
        data = {
            "url": url,
            "cached_at": datetime.now().isoformat(),
            "response": response,
        }
        
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# Main Scraper Class
# =============================================================================

class FragranceScraper:
    """
    Web scraper for fragrance ingredient data.
    
    Features:
    - Rate limiting (configurable delay between requests)
    - User-Agent rotation
    - Response caching
    - Retry with exponential backoff
    """
    
    # Common User-Agents as fallback
    FALLBACK_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    ]
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        
        # Initialize cache
        cache_dir = Path(self.config.data_dir) / "cache"
        self.cache = ResponseCache(
            cache_dir, 
            ttl_hours=self.config.scraper.cache_ttl_hours
        )
        
        # Initialize User-Agent rotator
        try:
            self.ua = UserAgent()
        except Exception:
            self.ua = None
            self.logger.warning("fake-useragent failed, using fallback agents")
        
        self._ua_index = 0
        self._last_request_time = 0.0
        
        # Session for connection reuse
        self.session = requests.Session()
    
    def _get_user_agent(self) -> str:
        """Get next User-Agent string."""
        if self.config.scraper.enable_user_agent_rotation:
            if self.ua:
                try:
                    return self.ua.random
                except Exception:
                    pass
            
            # Fallback rotation
            agent = self.FALLBACK_USER_AGENTS[self._ua_index]
            self._ua_index = (self._ua_index + 1) % len(self.FALLBACK_USER_AGENTS)
            return agent
        
        return self.FALLBACK_USER_AGENTS[0]
    
    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        delay = self.config.scraper.delay_seconds
        
        if elapsed < delay:
            sleep_time = delay - elapsed
            self.logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    )
    def _fetch(
        self, 
        url: str, 
        use_cache: bool = True,
        custom_headers: Optional[dict] = None
    ) -> requests.Response:
        """
        Fetch URL with rate limiting, caching, and retries.
        
        Args:
            url: URL to fetch
            use_cache: Whether to use cache (default: True)
            custom_headers: Optional headers to override/merge
        
        Returns:
            Response object
        """
        # Check cache first
        if use_cache and self.config.scraper.cache_enabled:
            cached = self.cache.get(url)
            if cached:
                self.logger.debug(f"Cache hit: {url}")
                # Create a mock response-like object
                class CachedResponse:
                    def __init__(self, data):
                        self.text = data.get("text", "")
                        self.status_code = data.get("status_code", 200)
                        self.content = self.text.encode()
                    def json(self):
                        return json.loads(self.text)
                    def raise_for_status(self):
                        pass
                return CachedResponse(cached)
        
        self._rate_limit()
        
        headers = {
            "User-Agent": self._get_user_agent(),
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        if custom_headers:
            headers.update(custom_headers)
        
        self.logger.debug(f"Fetching: {url}")
        
        try:
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.config.scraper.timeout_seconds,
            )
            
            # Handle 429 specially
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 30))
                self.logger.warning(f"Rate limited (429). Waiting {retry_after}s...")
                time.sleep(retry_after)
                # Retry once
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.config.scraper.timeout_seconds,
                )
            
            response.raise_for_status()
            
            # Cache successful responses
            if use_cache and self.config.scraper.cache_enabled:
                self.cache.set(url, {
                    "text": response.text,
                    "status_code": response.status_code,
                })
            
            return response
            
        except requests.HTTPError as e:
            # Don't retry 404s
            if e.response.status_code == 404:
                return e.response
            raise e
    
    # -------------------------------------------------------------------------
    # Common Chemistry API (CAS)
    # -------------------------------------------------------------------------
    
    def search_common_chemistry(self, name: str) -> Optional[IngredientProfile]:
        """
        Search Common Chemistry (CAS) for ingredient data.
        
        This is a reliable API from the Chemical Abstracts Service.
        
        Args:
            name: Ingredient name to search for
        
        Returns:
            IngredientProfile or None if not found
        """
        self.logger.info(f"Searching Common Chemistry for: {name}")
        
        try:
            # Step 1: Search for the compound
            search_url = CommonChemistryAPI.search_by_name(name)
            response = self._fetch(search_url)
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                self.logger.debug(f"No Common Chemistry results for '{name}'")
                return None
            
            # Get first result
            first_result = results[0]
            cas = first_result.get("rn")
            
            if not cas:
                return None
            
            # Step 2: Get detailed info
            detail_url = CommonChemistryAPI.get_detail(cas)
            detail_response = self._fetch(detail_url)
            detail_data = detail_response.json()
            
            # Extract data
            profile = IngredientProfile(name=name)
            profile.cas = cas
            profile.source = "CommonChemistry"
            
            # Molecular info
            if "molecularFormula" in detail_data:
                profile.molecular_formula = detail_data["molecularFormula"]
            
            if "molecularMass" in detail_data:
                profile.molecular_weight = str(detail_data["molecularMass"])
            
            # Synonyms
            synonyms = detail_data.get("synonyms", [])
            profile.synonyms = [s for s in synonyms if isinstance(s, str)][:20]
            
            # Name from CAS
            if "name" in detail_data:
                if detail_data["name"] != name:
                    profile.synonyms.insert(0, detail_data["name"])
            
            self.logger.info(f"Found Common Chemistry data for '{name}' (CAS: {cas})")
            return profile
            
        except requests.RequestException as e:
            self.logger.debug(f"Common Chemistry request failed for '{name}': {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.debug(f"Common Chemistry parsing error for '{name}': {e}")
            return None
    
    # -------------------------------------------------------------------------
    # TGSC (The Good Scents Company) - VERIFIED WORKING
    # -------------------------------------------------------------------------
    
    def search_tgsc(self, name: str) -> Optional[IngredientProfile]:
        """
        Search The Good Scents Company for ingredient data.
        Now uses DuckDuckGo to find the direct page, bypassing the broken search form.
        """
        # Strategy 1: Direct TGSC Search (Most Reliable)
        try:
            self.logger.info(f"Searching TGSC directly: {name}")
            search_url = TGSCSelectors.SEARCH_URL
            data = {"qName": name, "submit": "Search"}
            
            # Use session to maintain cookies/headers
            headers = {
                "User-Agent": self._get_user_agent(),
                "Referer": TGSCSelectors.SEARCH_PAGE,
                "Origin": TGSCSelectors.BASE_URL,
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            self._rate_limit()
            response = self.session.post(
                search_url, 
                data=data, 
                headers=headers,
                timeout=self.config.scraper.timeout_seconds
            )
            
            if response.status_code == 200:
                # Parse search results
                soup = BeautifulSoup(response.text, "html.parser")
                links = soup.find_all("a", href=True)
                
                tgsc_url = None
                for link in links:
                    href = link.get("href", "")
                    if "data/rw" in href:
                        tgsc_url = href
                        break
                
                # Fallback: Regex search if soup fails (e.g. link in JS or malformed HTML)
                if not tgsc_url:
                    import re
                    # Look for pattern data/rw followed by digits
                    match = re.search(r'data/rw\d+\.html', response.text)
                    if match:
                        tgsc_url = match.group(0)
                        self.logger.info(f"Found TGSC URL via Regex: {tgsc_url}")

                if tgsc_url:
                    self.logger.info("Normalizing TGSC URL...")
                    # Normalize URL
                    if not tgsc_url.startswith("http"):
                        if tgsc_url.startswith("/"):
                            tgsc_url = TGSCSelectors.BASE_URL + tgsc_url
                        else:
                            tgsc_url = TGSCSelectors.BASE_URL + "/" + tgsc_url
                            
                    self.logger.info(f"Found TGSC URL (Direct): {tgsc_url}")
                    result = self._fetch_and_parse_tgsc(tgsc_url, name)
                    if result:
                         self.logger.info("Direct Search Returns VALID Result")
                         return result
                    else:
                         self.logger.warning("Direct Search fetched page but returned None (Parsing failed?)")
                else:
                    self.logger.warning(f"No data link found in TGSC Direct Search response (Length: {len(response.text)})")
            else:
                 self.logger.warning(f"TGSC Direct Search returned {response.status_code}")
                 
        except Exception as e:
            import traceback
            self.logger.error(f"TGSC Direct Search CRASHED: {e}")
            self.logger.error(traceback.format_exc())

        # Strategy 2: DuckDuckGo Search
        try:
            from duckduckgo_search import DDGS
            self.logger.info(f"Searching TGSC via DuckDuckGo: {name}")
            
            # Use 'lite' backend as it's often more lenient
            results = DDGS().text(f"site:thegoodscentscompany.com {name} ingredient", max_results=3, backend="lite")
            
            if results:
                for r in results:
                    href = r.get("href", "")
                    if "thegoodscentscompany.com/data/rw" in href:
                        self.logger.info(f"Found TGSC URL (DDG): {href}")
                        return self._fetch_and_parse_tgsc(href, name)
        except Exception as e:
            self.logger.warning(f"DuckDuckGo search failed: {e}")

        # Strategy 3: Google Search (googlesearch-python)
        try:
            from googlesearch import search
            self.logger.info(f"Searching TGSC via Google: {name}")
            
            # search() yields URLs
            results = search(f"site:thegoodscentscompany.com {name} ingredient", num_results=3, advanced=True)
            for res in results:
                # res might be a string or object depending on version
                url = res.url if hasattr(res, 'url') else res
                if "thegoodscentscompany.com/data/rw" in url:
                    self.logger.info(f"Found TGSC URL (Google): {url}")
                    return self._fetch_and_parse_tgsc(url, name)
        except Exception as e:
            self.logger.warning(f"Google search failed: {e}")
            
        self.logger.warning(f"All TGSC search methods failed for: {name}")
        return None

    def _fetch_and_parse_tgsc(self, url: str, name: str) -> Optional[IngredientProfile]:
        """Helper to fetch and parse a TGSC page."""
        response = self._fetch(url)
        if response.status_code != 200:
            self.logger.warning(f"Failed to fetch TGSC page: {response.status_code}")
            return None
        return self._parse_tgsc_page(response.text, name)
    
    def _parse_tgsc_page(
        self, 
        page_content: str, 
        name: str
    ) -> Optional[IngredientProfile]:
        """
        Parse TGSC search results page for ingredient data.
        """
        self.logger.info(f"Parsing TGSC page for '{name}' (Length: {len(page_content)})")
        try:
            soup = BeautifulSoup(page_content, "html.parser")
            profile = IngredientProfile(name=name)
            
            # Extract table data
            tables = soup.find_all("table")
            page_text = soup.get_text()
            self.logger.info(f"Found {len(tables)} tables")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        if "cas" in label and not profile.cas:
                             # try to find cas pattern in value
                             match = re.search(TGSCSelectors.CAS_PATTERN, value)
                             if match:
                                 profile.cas = match.group(1)
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["fema"]):
                            profile.uses.append(f"FEMA {value}")
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["odor"]):
                            if len(value) > 3:
                                profile.odor_description = value
                                
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["odor_type"]):
                            if value:
                                 profile.odor_family = value
                                 
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["strength"]):
                             profile.odor_strength = value
                             
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["appearance"]):
                             profile.appearance = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["flash_point"]):
                             profile.flash_point = value
                             
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["molecular_weight"]):
                             profile.molecular_weight = value
                             
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["molecular_formula"]):
                             profile.molecular_formula = value
                             
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["synonyms"]):
                            synonyms = [s.strip() for s in value.split(",")]
                            profile.synonyms.extend(synonyms)
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["tenacity"]):
                            profile.tenacity = value
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["logp"]):
                            profile.logp = value
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["soluble"]):
                            profile.soluble = value
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["shelf_life"]):
                            profile.shelf_life = value
    
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["einecs"]):
                            profile.einecs = value
    
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["reach"]):
                            profile.reach = value
            
            # Fallback to text parsing if tables failed (old logic)
            if not profile.cas:
                # Extract CAS number - first match in page
                cas_matches = re.findall(TGSCSelectors.CAS_PATTERN, page_text)
                if cas_matches:
                    profile.cas = cas_matches[0]
            
            if not profile.odor_description:
                # Extract odor description from text patterns
                # TGSC format: "odor: citrus floral sweet woody"
                odor_pattern = r'odor[:\s]+([a-zA-Z\s,]+?)(?:flavor|$|\n|\r|<)'
                # ... (rest of regex logic is fine if needed, but table is preferred)
                odor_match = re.search(odor_pattern, page_text, re.IGNORECASE)
                if odor_match:
                    odor_text = odor_match.group(1).strip()
                    # Clean up the odor description
                    odor_text = re.sub(r'\s+', ' ', odor_text)
                    if len(odor_text) > 3:
                        profile.odor_description = odor_text
            
            # Extract flavor description
            flavor_pattern = r'flavor[:\s]+([a-zA-Z\s,]+?)(?:odor|$|\n|\r|<)'
            flavor_match = re.search(flavor_pattern, page_text, re.IGNORECASE)
            if flavor_match:
                flavor_text = flavor_match.group(1).strip()
                flavor_text = re.sub(r'\s+', ' ', flavor_text)
                if len(flavor_text) > 3:
                    profile.uses.append(f"Flavor: {flavor_text}")
            
            # Look for data in tables (fallback method)
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        # Map common labels to fields
                        if any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["cas"]):
                            cas_match = re.search(TGSCSelectors.CAS_PATTERN, value)
                            if cas_match:
                                profile.cas = cas_match.group(1)
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["odor"]):
                            if not profile.odor_description:
                                profile.odor_description = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["odor_type"]):
                            profile.odor_family = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["strength"]):
                            profile.odor_strength = self._normalize_strength(value)
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["appearance"]):
                            profile.appearance = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["flash_point"]):
                            profile.flash_point = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["specific_gravity"]):
                            profile.specific_gravity = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["boiling_point"]):
                            profile.boiling_point = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["molecular_formula"]):
                            profile.molecular_formula = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["molecular_weight"]):
                            profile.molecular_weight = value
                        
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["synonyms"]):
                            synonyms = [s.strip() for s in value.split(",")]
                            profile.synonyms.extend(synonyms)
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["tenacity"]):
                            profile.tenacity = value
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["logp"]):
                            profile.logp = value
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["soluble"]):
                            profile.soluble = value
                            
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["shelf_life"]):
                            profile.shelf_life = value
    
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["einecs"]):
                            profile.einecs = value
    
                        elif any(lbl in label for lbl in TGSCSelectors.LABEL_PATTERNS["reach"]):
                            profile.reach = value
            
            # Check if we found any useful data
            if profile.cas or profile.odor_description or profile.odor_family:
                return profile
    
            return None
    
        except Exception as e:
            import traceback
            self.logger.error(f"TGSC Parsing CRASHED: {e}")
            self.logger.error(traceback.format_exc())
            return None
    
    def _normalize_strength(self, value: str) -> str:
        """Normalize odor strength to standard values."""
        value_lower = value.lower()
        
        if "extreme" in value_lower or "very high" in value_lower:
            return "Extreme"
        elif "high" in value_lower or "strong" in value_lower:
            return "High"
        elif "low" in value_lower or "weak" in value_lower:
            return "Low"
        else:
            return "Medium"
    
    # -------------------------------------------------------------------------
    # PubChem API
    # -------------------------------------------------------------------------
    
    def search_pubchem(self, name: str) -> Optional[PubChemData]:
        """
        Query PubChem API for chemical data.
        
        Args:
            name: Compound name to search for
        
        Returns:
            PubChemData or None if not found
        """
        self.logger.info(f"Searching PubChem for: {name}")
        
        # PubChem requires specific User-Agent with contact info
        pubchem_headers = {
            "User-Agent": "ParfumVault/1.0 (admin@parfumvault.local)"
        }
        
        try:
            # Step 1: Search for compound by name
            search_url = PubChemAPI.search_by_name(name)
            response = self._fetch(search_url, custom_headers=pubchem_headers)
            
            if response.status_code == 404:
                return None
            
            data = response.json()
            compounds = data.get("PC_Compounds", [])
            
            if not compounds:
                self.logger.warning(f"No PubChem data found for '{name}'")
                return None
            
            compound = compounds[0]
            cid = compound.get("id", {}).get("id", {}).get("cid")
            
            if not cid:
                return None
            
            # Step 2: Get properties
            props_url = PubChemAPI.get_properties(
                cid, 
                ["MolecularFormula", "MolecularWeight", "IUPACName"]
            )
            props_response = self._fetch(props_url, custom_headers=pubchem_headers)
            props_data = props_response.json()
            
            properties = props_data.get("PropertyTable", {}).get("Properties", [{}])[0]
            
            # Step 3: Get synonyms
            synonyms_url = PubChemAPI.get_synonyms(cid)
            syn_response = self._fetch(synonyms_url, custom_headers=pubchem_headers)
            syn_data = syn_response.json()
            
            synonyms = (
                syn_data
                .get("InformationList", {})
                .get("Information", [{}])[0]
                .get("Synonym", [])
            )
            
            # Extract CAS from synonyms (often first one)
            cas = None
            for syn in synonyms[:20]:  # Check first 20
                if re.match(TGSCSelectors.CAS_PATTERN, syn):
                    cas = syn
                    break
            
            result = PubChemData(
                cid=cid,
                name=name,
                cas=cas,
                molecular_formula=properties.get("MolecularFormula"),
                molecular_weight=str(properties.get("MolecularWeight", "")),
                iupac_name=properties.get("IUPACName"),
                synonyms=synonyms[:50],  # Limit synonyms
            )
            
            self.logger.info(f"Found PubChem data for '{name}' (CID: {cid})")
            return result
            
        except requests.RequestException as e:
            self.logger.error(f"PubChem request failed for '{name}': {e}")
            return None
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"PubChem parsing error for '{name}': {e}")
            return None
    
    # -------------------------------------------------------------------------
    # IFRA Data (placeholder for future implementation)
    # -------------------------------------------------------------------------
    
    def search_ifra_online(self, name: str) -> Optional[IFRAData]:
        """
        Search online IFRA sources for restriction data.
        
        Note: The official IFRA database may require authentication.
        This is a placeholder for future implementation.
        
        For now, use sync_ifra_library() with a CSV file.
        """
        self.logger.warning(
            f"IFRA online search not implemented. "
            f"Use CSV import for '{name}'"
        )
        return None


# Singleton instance
_scraper: Optional[FragranceScraper] = None


def get_scraper() -> FragranceScraper:
    """Get or create the global scraper instance."""
    global _scraper
    if _scraper is None:
        _scraper = FragranceScraper()
    return _scraper
