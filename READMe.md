
# 🌍 Immigration Document Intelligence System

> "Automating the journey from chaos to clarity in immigration documentation."

## ✨ Overview

This Streamlit-based system is a full-fledged document intelligence platform for immigration forms. It discovers, downloads, processes, validates, and exports official immigration documents using AI and a PostgreSQL database backend.

From fetching publicly available visa forms to extracting structured data, performing AI-driven validation, and generating summaries, this tool turns unstructured documents into clean, usable information for legal professionals, immigration experts, and data teams.

---

## 🛠️ Features

* **🔍 Document Discovery**
  Automatically discovers immigration documents (PDFs, Word files, etc.) using the Tavily API based on country and visa type.

* **📥 Document Processing Pipeline**
  Downloads, extracts text, and applies AI (OpenAI/OpenRouter) to identify structured fields such as form names, fees, submission methods, and more.

* **✅ Validation & Review**
  AI validation and manual review interface for legal professionals to assess and annotate document data.

* **📄 Document Viewer**
  Explore processed documents, view original and extracted text, and download them for reference.

* **📊 Export Panel**
  Export structured data as JSON, Excel, or summaries for reporting or downstream workflows.

* **🗄️ Database Viewer**
  Search, filter, and inspect all stored documents from the PostgreSQL database.

* **🩺 Health Checker**
  Validate database connection status and monitor system reliability.

---

## 🧠 Tech Stack

* **Frontend/UI:** [Streamlit](https://streamlit.io/)
* **Backend Database:** PostgreSQL (via `psycopg2`)
* **AI Integration:** OpenAI / OpenRouter for LLM-based field extraction & validation
* **Discovery Service:** Tavily API
* **File Processing:** Python standard libs + custom parsers
* **Export Tools:** Excel/JSON/PDF generation
* **Config Management:** Environment-based via a `config.py`

---

## 📂 Directory Structure (High-level)

```bash
.
├── app.py                     # Streamlit entry point
├── config.py                  # API keys and directory paths
├── database.py                # DB manager class
├── discovery_service.py       # Fetches documents from web APIs
├── document_processor.py      # Handles downloads, extraction
├── ai_service.py              # AI-powered field extraction and validation
├── export_service.py          # Export to JSON, Excel, PDFs
├── requirements.txt
└── README.md                  # ← you’re here
```

---

## 🚀 How It Works

1. **Start the app**

   ```bash
   streamlit run app.py
   ```

2. **Select your task**
   Use the sidebar to jump between:

   * Discovery
   * Viewer
   * Validation
   * Export
   * Database Health Checks

3. **Discover Documents**
   Choose a country and visa type. The system fetches relevant documents from trusted public sources.

4. **Process Automatically**
   Documents are downloaded, text extracted, and AI is used to identify key immigration data.

5. **Review & Validate**
   Human reviewers can assess the AI output and leave comments, approvals, or re-run AI validation.

6. **Export to Files**
   Easily export everything as JSON, Excel sheets, or readable summaries for your team or organization.

---

## ⚠️ Notes

* Ensure your `.env` or `config.py` contains correct API keys and database credentials.
* LLM APIs (OpenAI/OpenRouter) may incur costs — manage your tokens carefully.
* Only process official, publicly available documents to stay compliant.

---

## ❤️ Why It Matters

Immigration processes are riddled with complex, redundant paperwork. This tool exists to make sense of it all—giving lawyers, applicants, and institutions a smart, transparent, and reliable way to manage immigration data.

---

## 👨‍⚖️ Built For

* Legal Tech Startups
* Government Agencies
* Immigration Firms
* Researchers & Data Analysts

---

## 📬 Questions or Contributions?

Pull requests are welcome. If you’d like to collaborate or inquire more about this system, feel free to reach out.

---

Crafted with purpose, debugged with patience, and deployed with love 💼🛂

---

Let me know if you want a `requirements.txt` template, Dockerfile, or deployment guide added!
