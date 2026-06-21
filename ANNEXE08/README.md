Updated ANNEXE08 README with Docker and multi-certificate split instructions.

Run with Docker:

1. Build and start the service:
   docker-compose -f ANNEXE08/docker-compose.yml up --build -d

2. The service will be available at http://localhost:8000

Notes:
- The Docker image installs Tesseract and language packs (fra, ara) and poppler-utils required for PDF processing.
- Persistent uploads/exports and the SQLite DB are mounted to the host paths under ANNEXE08/ so you can access them.

Multi-certificate splitting:
- The OCR pipeline now attempts to detect multiple certificate regions on a single page and segments them automatically before OCR.
- This uses OpenCV contour detection and heuristics; adjust thresholds in annexe_ocr.py if needed for your documents.
