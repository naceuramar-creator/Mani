# ANNEXE 08

This repository contains a deployable web application that performs the requested pipeline:
Upload → OCR (Arabic & French) → Data extraction → Translation → Fill ANNEXE 08 → Export XLSX

Requirements and notes

- Backend: FastAPI (Python)
- OCR: Tesseract via pytesseract. You MUST install tesseract and language packs for French and Arabic on the host.
  - Debian/Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-fra tesseract-ocr-ara
  - macOS (brew): brew install tesseract-lang
- PDF support: pdf2image requires poppler. On Ubuntu: sudo apt-get install poppler-utils

Install Python deps:

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

Run:

uvicorn main:app --reload --host 0.0.0.0 --port 8000

Open http://localhost:8000 in your browser.

How it works

- Upload single or multiple files (.pdf, .jpg, .jpeg, .png) via the top control.
- Each file is saved under uploads/ and processed: each PDF page becomes a record.
- OCR uses both Arabic and French languages and image enhancement heuristics.
- Extraction uses heuristics for French and Arabic keywords; then Arabic pieces are passed through googletrans to translate to French.
- Extracted records are stored in SQLite annexe08.db and visible in the UI where they are editable.
- Export to XLSX button generates an Excel file saved under exports/ and a download link appears.

Limitations & notes

- Extraction heuristics are intentionally generic and may need tuning for varied certificate layouts.
- Translation uses the community googletrans library which may be rate-limited; consider a dedicated translation service for production.
- For very large uploads or heavy processing, consider background workers (Celery/RQ) instead of synchronous processing.

Files added:
- main.py - FastAPI app
- annexe_ocr.py - OCR and extraction pipeline
- models.py - SQLAlchemy models and DB init
- templates/index.html - Frontend
- static/app.js, static/style.css
- requirements.txt, README.md

