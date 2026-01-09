# 🧪 ParfumFormula
>
> **The Advanced Formulation & Regulatory Platform**  
> *A robust, feature-enhanced fork of [jbparfum/parfumvault](https://github.com/jbparfum/parfumvault)*

![Version](https://img.shields.io/badge/version-2.6.0--mod-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

**ParfumFormula** elevates the original Perfumers Vault by integrating powerful automation tools for ingredient data mining and regulatory compliance. It serves as a comprehensive ecosystem for perfumers, evaluators, and regulatory affairs managers to create, manage, and validate fragrance formulas with precision.

🌟 **Repository:** [https://github.com/cupiz/ParfumFormula](https://github.com/cupiz/ParfumFormula)

---

## ✨ Key Enhancements in This Fork

We have supercharged the core Perfumers Vault with a custom **Automation Suite** (`/automation`) designed to eliminate manual data entry:

### 🚀 1. Auto-Search Online (New Feature!)

**Can't find an ingredient?** No problem!
We have integrated a seamless connection to **PubChem** and **The Good Scents Company (TGSC)** directly into the user interface.

* **Permanently Available:** A yellow **"Search Online"** button is always accessible on the Ingredients page.
* **Smart Search:** Searches 100M+ compounds instantly via our Python automation backend.
* **Instant Import:** Preview chemical data (CAS, Formula, Odor Profile) and add it to your library with **one click**.
* **Zero Configuration:** Works out-of-the-box using an internal secure bridge (`ajax_autosearch.php`)—no complex API keys required.

### 📋 2. Intelligent Ingredient Scraper

Stop manually typing CAS numbers and odor descriptions. Our background Python scraper automatically enriches your database:

* **Multi-Source Mining:** Fetches data from authoritative sources.
* **Smart Matching:** Uses advanced fuzzy matching algorithms.
* **Resilient:** Automatically handles rate limits and connection issues.

### 📦 3. One-Click IFRA Sync & Batch Population

* **IFRA 51st Amendment:** Automatically syncs restriction limits (Cat 1 - Cat 12) for hundreds of materials.
* **Pre-Loaded Library:** Capable of ingesting a curated list of 300+ industry-standard ingredients in one go.

---

## 💎 Core Features

ParfumFormula enables the full lifecycle of fragrance creation:

* **Formula Management:** Version control, comparisons, and history tracking.
* **Inventory Control:** Track suppliers, prices, and stock levels.
* **Regulatory Compliance:** Automated SDS generation and IFRA limit checking during formulation.
* **Cost Verification:** Real-time formula costing based on current inventory prices.
* **Batch & Traceability:** Full history of production batches and modifications.
* **Dark Mode UI:** Modern interface optimized for long formulation sessions.

---

## 🛠️ Installation & Setup (WSL / Docker)

### Prerequisites

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
* **Windows Subsystem for Linux (WSL 2)** (Highly Recommended for Windows users)

### Quick Start (Docker Compose)

1. **Clone the Repository**

    ```bash
    git clone https://github.com/cupiz/ParfumFormula.git
    cd ParfumFormula
    ```

2. **Start the Platform**

    We use a custom port configuration to avoid conflicts with local services.

    ```bash
    # Run from the project root
    docker compose -f docker-compose/compose.yaml up -d --build
    ```

    This will launch:
    * `pvdb`: MariaDB database container (Internal Port 3306)
    * `pvault`: The web application container (Host Port **8082**)
    * `automation`: Python API service (Internal Port 5001)

3. **Access the App**

    Open your browser and navigate to:  
    👉 **[http://localhost:8082](http://localhost:8082)**

    *Default Credentials:*
    * **Email:** `admin@admin.com`
    * **Password:** `password`

---

## 🤖 Using the Automation Module (CLI)

To manually populate your database with bulk data:

### 1. Enter the Environment

Ensure your containers are running, then access the automation folder:

```bash
cd automation
pip install -r requirements.txt
```

### 2. Sync IFRA Standards

Populate the regulatory library first:

```bash
python ingestor.py --target ifra --source ./data/ifra_standards.csv
```

### 3. Enrich Ingredients

Scrape and ingest 300+ ingredients automatically:

```bash
python ingestor.py --target batch --file ./data/ingredients.txt
```

*> Note: This process takes time due to respect for API rate limits. Runs best in background.*

---

---

## ❓ Troubleshooting

### "Search Online" Button Missing

If you don't see the yellow button in the Ingredients toolbar:

1. **Force Refresh** your browser (Ctrl+F5) to clear the cache.
2. Ensure you are accessing the correct port: `http://localhost:8082`.

### Search Returns "Empty Data"

If the search finds the ingredient (name/CAS) but returns no other data:

1. The scraper might be blocked by rate limits.
2. Check the automation logs: `docker compose logs automation`.
3. Retry the search after 1 minute.

### Port Conflicts

If you cannot access the app:

* Error `bind: address already in use`: Stop other services on port **8082** or **3306**.
* Edit `docker-compose/compose.yaml` to change the port mapping if needed.

---

## 🤝 Contributing

We welcome contributions! Please fork the repository and submit a Pull Request.
If you encounter issues with the scraper or IFRA data, please open an Issue.

**Original Author:** [jbparfum](https://github.com/jbparfum)  
**Maintained by:** [Cupiz](https://github.com/cupiz)

---
*This software is provided "as is" under the MIT License.*
