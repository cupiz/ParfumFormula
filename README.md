# 🧪 ParfumFormula
>
> **The Advanced Formulation & Regulatory Platform**  
> *A feature-enhanced fork of [jbparfum/parfumvault](https://github.com/jbparfum/parfumvault)*

![Version](https://img.shields.io/badge/version-2.6.0--mod-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-green.svg)
![License](https://img.shields.io/badge/license-MIT-orange.svg)

**ParfumFormula** elevates the original Perfumers Vault by integrating powerful automation tools for ingredient data mining and regulatory compliance. It serves as a comprehensive ecosystem for perfumers, evaluators, and regulatory affairs managers to create, manage, and validate fragrance formulas with precision.

🌟 **Repository:** [https://github.com/cupiz/ParfumFormula](https://github.com/cupiz/ParfumFormula)

---

## ✨ Key Enhancements in This Fork

We have supercharged the core Perfumers Vault with a custom **Automation Suite** (`/automation`) designed to eliminate manual data entry:

### 🚀 1. Intelligent Ingredient Scraper

Stop manually typing CAS numbers and odor descriptions. Our Python-based scraper automatically enriches your database:

* **Multi-Source Mining:** Fetches data from **PubChem** (Chemical properties, IUPAC names) and **The Good Scents Company** (Odor profiles, FEMA numbers).
* **Smart Matching:** Uses advanced fuzzy matching and CAS verification to ensure accuracy.
* **Rate-Limit Complaint:** Built-in safeguards to respect API limits (delayed requests, user-agent rotation).

### 📋 2. One-Click IFRA Sync

Stay compliant effortlessly. The automation module synchronizes your database with the **IFRA Standards (51st Amendment)**:

* **Automatic Limits:** Populates restriction limits (Cat 1 - Cat 12) for hundreds of restricted materials.
* **Risk Analysis:** Flags prohibited ingredients (e.g., Lilial, Lyral) and those with specific warnings (Phototoxicity).

### 📦 3. Batch Population

Your vault comes pre-loaded with a curated list of **300+ Industry-Standard Ingredients**:

* Oraganized by family (Citrus, Floral, Woody, Musk, etc.)
* Ready to ingest with a single command.

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

## 🛠️ Installation & Setup

### Prerequisites

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
* **Windows Subsystem for Linux (WSL 2)** (Recommended for Windows users)

### Quick Start (Docker Compose)

1. **Clone the Repository**

    ```bash
    git clone https://github.com/cupiz/ParfumFormula.git
    cd ParfumFormula
    ```

2. **Start the Platform**

    ```bash
    docker-compose up -d
    ```

    This will launch:
    * `pvdb`: MariaDB database container
    * `pvault`: The web application container

3. **Access the App**
    Open your browser and navigate to:  
    👉 **<http://localhost:8000>**

    *Default Credentials:*
    * **Email:** `admin@example.com`
    * **Password:** `password`

---

## 🤖 Using the Automation Module

To populate your empty database with real-world data, use our CLI tools.

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

## 🤝 Contributing

We welcome contributions! Please fork the repository and submit a Pull Request.
If you encounter issues with the scraper or IFRA data, please open an Issue.

**Original Author:** [jbparfum](https://github.com/jbparfum)  
**Maintained by:** [Cupiz](https://github.com/cupiz)

---
*This software is provided "as is" under the MIT License.*
