import os
import shutil
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from annexe_ocr import process_file
from models import init_db, SessionLocal, UploadedFile, ExtractedRecord, ExportedFile
import uuid
import pathlib
from datetime import datetime
import io
import openpyxl

app = FastAPI()
BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'templates'))
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'static')), name='static')

init_db()

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse('index.html', {'request': request})

@app.post('/upload')
async def upload(files: list[UploadFile] = File(...)):
    db = SessionLocal()
    results = []
    for up in files:
        contents = await up.read()
        filename = f"{uuid.uuid4().hex}_{up.filename}"
        path = os.path.join(UPLOAD_DIR, filename)
        with open(path, 'wb') as f:
            f.write(contents)
        uf = UploadedFile(original_name=up.filename, stored_path=path)
        db.add(uf)
        db.commit()
        db.refresh(uf)
        # process
        recs = process_file(path)
        saved = []
        for r in recs:
            cand = r['candidate']
            spouse = r['spouse']
            er = ExtractedRecord(
                file_id=uf.id,
                nom=cand.get('nom'),
                prenom=cand.get('prenom'),
                date_naissance=cand.get('date_naissance'),
                nature_date=cand.get('nature_date'),
                lieu_naissance=cand.get('lieu_naissance'),
                nom_pere=cand.get('nom_pere'),
                nom_mere=cand.get('nom_mere'),
                sexe=cand.get('sexe'),
                situation_familiale=cand.get('situation_familiale'),
                spouse_nom=spouse.get('nom') if spouse else None,
                raw_text=r['raw_text']
            )
            db.add(er)
            db.commit()
            db.refresh(er)
            saved.append({'record_id': er.id, 'candidate': cand, 'spouse': spouse})
        results.append({'file_id': uf.id, 'original_name': up.filename, 'records': saved})
    db.close()
    return JSONResponse({'status': 'ok', 'results': results})

@app.get('/files')
async def list_files():
    db = SessionLocal()
    files = db.query(UploadedFile).order_by(UploadedFile.uploaded_at.desc()).all()
    out = [{'id': f.id, 'original_name': f.original_name, 'stored_path': f.stored_path, 'uploaded_at': f.uploaded_at.isoformat()} for f in files]
    db.close()
    return JSONResponse({'files': out})

@app.get('/records')
async def list_records():
    db = SessionLocal()
    recs = db.query(ExtractedRecord).order_by(ExtractedRecord.processed_at.desc()).all()
    out = []
    for r in recs:
        out.append({
            'id': r.id,
            'file_id': r.file_id,
            'nom': r.nom,
            'prenom': r.prenom,
            'date_naissance': r.date_naissance,
            'nature_date': r.nature_date,
            'lieu_naissance': r.lieu_naissance,
            'nom_pere': r.nom_pere,
            'nom_mere': r.nom_mere,
            'sexe': r.sexe,
            'situation_familiale': r.situation_familiale,
            'spouse_nom': r.spouse_nom,
            'raw_text': r.raw_text
        })
    db.close()
    return JSONResponse({'records': out})

@app.post('/save-records')
async def save_records(request: Request):
    data = await request.json()
    db = SessionLocal()
    for rec in data.get('records', []):
        rid = rec.get('id')
        r = db.query(ExtractedRecord).filter(ExtractedRecord.id==rid).first()
        if not r:
            continue
        # Update fields from provided editable form
        for field in ['nom','prenom','date_naissance','nature_date','lieu_naissance','nom_pere','nom_mere','sexe','situation_familiale','spouse_nom']:
            if field in rec:
                setattr(r, field, rec[field])
        db.add(r)
    db.commit()
    db.close()
    return JSONResponse({'status': 'saved'})

@app.post('/export')
async def export_records(request: Request):
    data = await request.json()
    records = data.get('records', [])
    # generate xlsx
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'ANNEXE 08'
    headers = ['Nom','Prénom','Date de naissance','Nature date','Lieu de naissance','Nom père','Nom mère','Sexe','Situation familiale','Spouse Nom']
    ws.append(headers)
    for r in records:
        row = [r.get('nom'), r.get('prenom'), r.get('date_naissance'), r.get('nature_date'), r.get('lieu_naissance'), r.get('nom_pere'), r.get('nom_mere'), r.get('sexe'), r.get('situation_familiale'), r.get('spouse_nom')]
        ws.append(row)
    filename = f'annexe08_{datetime.utcnow().strftime("%Y%m%d%H%M%S")}.xlsx'
    path = os.path.join(EXPORT_DIR, filename)
    wb.save(path)
    db = SessionLocal()
    ef = ExportedFile(path=path)
    db.add(ef)
    db.commit()
    db.refresh(ef)
    db.close()
    return JSONResponse({'status': 'ok', 'export_path': path, 'filename': filename})

@app.get('/download/{export_filename}')
async def download_export(export_filename: str):
    path = os.path.join(EXPORT_DIR, export_filename)
    if not os.path.exists(path):
        return JSONResponse({'error': 'not found'}, status_code=404)
    return FileResponse(path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=export_filename)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=8000, reload=True)
