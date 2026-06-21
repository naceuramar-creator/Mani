import os
import re
import tempfile
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageFilter, ImageOps
import cv2
import numpy as np
from googletrans import Translator

translator = Translator()

# Enhancement helpers

def enhance_image_pil(image: Image.Image) -> Image.Image:
    # Convert to grayscale, increase contrast, denoise via PIL filters
    image = image.convert('L')
    image = ImageOps.autocontrast(image)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    return image


def enhance_image_cv(img_cv):
    # img_cv: numpy array BGR or grayscale
    if len(img_cv.shape) == 3:
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    else:
        gray = img_cv
    # denoise
    den = cv2.fastNlMeansDenoising(gray, h=10)
    # adaptive threshold
    thr = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15)
    # morphological opening to reduce noise
    kernel = np.ones((1,1),np.uint8)
    opening = cv2.morphologyEx(thr, cv2.MORPH_OPEN, kernel)
    return opening


def image_from_path(path):
    img = Image.open(path)
    return img


def pdf_to_images(path):
    images = []
    try:
        pages = convert_from_path(path, dpi=300)
        images.extend(pages)
    except Exception as e:
        print('pdf2image error', e)
    return images


def ocr_image_pil(image: Image.Image):
    # Use both Arabic and French
    try:
        text = pytesseract.image_to_string(image, lang='ara+fra')
    except Exception:
        text = pytesseract.image_to_string(image)
    return text


def ocr_image_cv(cv_img):
    pil = Image.fromarray(cv_img)
    return ocr_image_pil(pil)

# New: split page into multiple certificate regions using OpenCV

def split_page_into_segments(pil_image: Image.Image, min_area=50000):
    """
    Attempts to find multiple certificate-like rectangular regions on the page and returns list of PIL Image segments.
    min_area: minimum contour area to consider a segment (tune for your document resolution)
    """
    img = np.array(pil_image.convert('RGB'))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # blur and adaptive threshold
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    thresh = cv2.adaptiveThreshold(blur,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,51,15)
    # dilate to join text blocks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25,25))
    dilated = cv2.dilate(thresh, kernel, iterations=1)
    contours, hierarchy = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    h_img, w_img = gray.shape
    for cnt in contours:
        x,y,w,h = cv2.boundingRect(cnt)
        area = w*h
        # filter unlikely boxes: too small or nearly full page
        if area < min_area: continue
        if w > 0.9*w_img and h > 0.9*h_img: continue
        # expand box slightly
        pad_x = int(w*0.03)
        pad_y = int(h*0.03)
        x1 = max(0, x-pad_x)
        y1 = max(0, y-pad_y)
        x2 = min(w_img, x+w+pad_x)
        y2 = min(h_img, y+h+pad_y)
        boxes.append((x1,y1,x2,y2))
    # If no boxes found, return empty list
    if not boxes:
        return []
    # Remove nested/overlapping boxes: keep largest
    boxes_sorted = sorted(boxes, key=lambda b: (b[1], b[0]))
    final = []
    for b in boxes_sorted:
        bx1,b y1,bx2,by2 = b if False else b  # placeholder to keep format
    # The above line is only to satisfy some linters; rebuild proper logic below
    final = []
    for (x1,y1,x2,y2) in boxes_sorted:
        keep = True
        for (ox1,oy1,ox2,oy2) in final:
            # if b is inside existing
            if x1 >= ox1 and y1 >= oy1 and x2 <= ox2 and y2 <= oy2:
                keep = False
                break
            # if existing is inside b, replace
            if ox1 >= x1 and oy1 >= y1 and ox2 <= x2 and oy2 <= y2:
                # mark for removal
                final.remove((ox1,oy1,ox2,oy2))
        if keep:
            final.append((x1,y1,x2,y2))
    segments = []
    for (x1,y1,x2,y2) in final:
        crop = img[y1:y2, x1:x2]
        seg_pil = Image.fromarray(crop)
        segments.append(seg_pil)
    # sort segments top-to-bottom, left-to-right
    segments_sorted = sorted(segments, key=lambda im: im.size[1], reverse=True)
    return segments

# Extraction heuristics

# French and Arabic keys
F_KEYS = {
    'nom': [r'Nom[\s:]*([A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜŸa-zàâäéèêëîïôöùûüÿ\-\s]+)', r'Nom\s+de\s+famille[\s:]*([\w\s\-]+)'],
    'prenom': [r'Pr[eé]nom[\s:]*([A-ZÀÂÄÉÈÊËÎÏÔÖÙÛÜŸa-zàâäéèêëîïôöùûüÿ\-\s]+)'],
    'date': [r'Date\s+de\s+naissance[\s:]*([0-9]{1,2}[\-/ ][0-9]{1,2}[\-/ ][0-9]{2,4})', r'N[eé]\s+le[\s:]*([0-9]{1,2}[\-/ ][0-9]{1,2}[\-/ ][0-9]{2,4})', r'([0-9]{4})'],
    'lieu': [r'Lieu\s+de\s+naissance[\s:]*([\w\s\-\'"À-ÿ]+)'],
    'pere': [r'Nom\s+du\s+p[eè]re[\s:]*([\w\s\-À-ÿ]+)', r'P[eè]re[\s:]*([\w\s\-À-ÿ]+)'],
    'mere': [r'Nom\s+de\s+la\s+m[eè]re[\s:]*([\w\s\-À-ÿ]+)', r'M[eè]re[\s:]*([\w\s\-À-ÿ]+)'],
    'sexe': [r'Sexe[\s:]*([MFmfHfFf])', r'Sexe[\s:]*([Ff]emme|[Hh]omme|[Mm]ale|[Ff]emale)'],
    'situation': [r'Situation\s+de\s+famille[\s:]*([A-Za-zéàâäèêëîïôöûü\-\s]+)']
}

A_KEYS = {
    'nom': [r'الاسم[:\s]*([\u0600-\u06FF\s\-]+)'],
    'prenom': [r'اللقب[:\s]*([\u0600-\u06FF\s\-]+)', r'الاسم\s+واللقب[:\s]*([\u0600-\u06FF\s\-]+)'],
    'date': [r'تاريخ\s+الولادة[:\s]*([0-9]{1,2}[\-/ ][0-9]{1,2}[\-/ ][0-9]{2,4})', r'سنة\s+([0-9]{4})', r'([0-9]{4})'],
    'lieu': [r'مكان\s+الولادة[:\s]*([\u0600-\u06FF\s\-]+)'],
    'pere': [r'اسم\s+الوالد[:\s]*([\u0600-\u06FF\s\-]+)', r'اسم\s+الأب[:\s]*([\u0600-\u06FF\s\-]+)'],
    'mere': [r'اسم\s+الوالدة[:\s]*([\u0600-\u06FF\s\-]+)', r'اسم\s+الأم[:\s]*([\u0600-\u06FF\s\-]+)'],
    'sexe': [r'الجنس[:\s]*([\u0600-\u06FF\s\-]+)'],
    'situation': [r'الحالة\s+العائلية[:\s]*([\u0600-\u06FF\s\-]+)']
}


def find_first(patterns, text, flags=re.I | re.U):
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m.group(1).strip()
    return None


def detect_spouse_from_text(text):
    # Look for French spouse keywords
    sp = None
    m = re.search(r'(Epoux|\bepoux\b|\bepouse\b|\bépoux\b|\bépouse\b|زوج|الزوج|الزوجة|زوجة|époux[:\s]*([\w\s\-]+))', text, re.I)
    if m:
        # attempt to extract name nearby
        try:
            after = text[m.end():m.end()+120]
            name = re.search(r'([A-ZÀ-ÿ\'"\-\s]{3,})', after)
            if name:
                sp = name.group(1).strip()
        except Exception:
            sp = None
    return sp


def normalize_sexe(val):
    if not val: return None
    v = val.strip().lower()
    if any(x in v for x in ['m', 'homme', 'male', 'ذكر']):
        return 'M'
    if any(x in v for x in ['f', 'femme', 'female', 'أنثى']):
        return 'F'
    return None


def normalize_situation(val):
    if not val: return None
    v = val.strip().lower()
    if any(x in v for x in ['célibataire','celibataire','célib','أعزب','single']):
        return 'C'
    if any(x in v for x in ['mari','marié','mariée','متزوج','زوج']):
        return 'M'
    if any(x in v for x in ['divorc','divorcé','مطلق']):
        return 'D'
    if any(x in v for x in ['veuf','veuve','أرمل']):
        return 'V'
    return None


def normalize_date_and_nature(raw_date):
    if not raw_date: return None, None
    raw = raw_date.strip()
    # Try dd/mm/YYYY
    m = re.search(r'([0-9]{1,2})[\-/ ]([0-9]{1,2})[\-/ ]([0-9]{2,4})', raw)
    if m:
        d = int(m.group(1)); mo = int(m.group(2)); y = int(m.group(3))
        if y < 100: y += 1900
        return f"{d:02d}/{mo:02d}/{y:04d}", 'N'
    # If only year
    m2 = re.search(r'([0-9]{4})', raw)
    if m2:
        y = int(m2.group(1))
        return f"01/01/{y:04d}", 'P'
    return raw, 'N'


def translate_to_french(text):
    if not text: return None
    try:
        res = translator.translate(text, dest='fr')
        return res.text
    except Exception as e:
        # fallback: return original
        return text


def extract_from_text(text):
    # unify
    text = text.replace('\r','\n')
    candidate = {}
    # Try French keys first
    candidate['nom'] = find_first(F_KEYS['nom'], text) or find_first(A_KEYS['nom'], text)
    candidate['prenom'] = find_first(F_KEYS['prenom'], text) or find_first(A_KEYS['prenom'], text)
    raw_date = find_first(F_KEYS['date'], text) or find_first(A_KEYS['date'], text)
    date_norm, nature = normalize_date_and_nature(raw_date)
    candidate['date_naissance'] = date_norm
    candidate['nature_date'] = nature
    candidate['lieu_naissance'] = find_first(F_KEYS['lieu'], text) or find_first(A_KEYS['lieu'], text)
    candidate['nom_pere'] = find_first(F_KEYS['pere'], text) or find_first(A_KEYS['pere'], text)
    candidate['nom_mere'] = find_first(F_KEYS['mere'], text) or find_first(A_KEYS['mere'], text)
    candidate['sexe'] = normalize_sexe(find_first(F_KEYS['sexe'], text) or find_first(A_KEYS['sexe'], text))
    candidate['situation_familiale'] = normalize_situation(find_first(F_KEYS['situation'], text) or find_first(A_KEYS['situation'], text))

    # Spouse detection
    spouse_name = detect_spouse_from_text(text)
    spouse = None
    if spouse_name:
        spouse = {'nom': spouse_name}

    # Translate Arabic pieces if necessary
    for k in ['nom','prenom','lieu_naissance','nom_pere','nom_mere']:
        v = candidate.get(k)
        if v:
            cand = translate_to_french(v)
            candidate[k] = cand
    if spouse:
        spouse['nom'] = translate_to_french(spouse.get('nom'))

    return candidate, spouse, text


def process_file(path):
    records = []
    lower = path.lower()
    pages = []
    if lower.endswith('.pdf'):
        images = pdf_to_images(path)
        pages = images
    else:
        img = Image.open(path)
        pages = [img]

    for img in pages:
        # Attempt to split into segments (multiple certificates per page)
        segments = split_page_into_segments(img)
        if segments:
            to_process = segments
        else:
            to_process = [img]

        for seg in to_process:
            # enhance and OCR
            try:
                enhanced = enhance_image_pil(seg)
                text = ocr_image_pil(enhanced)
            except Exception as e:
                # fallback: raw OCR
                text = pytesseract.image_to_string(seg, lang='ara+fra')
            candidate, spouse, raw = extract_from_text(text)
            record = {
                'candidate': candidate,
                'spouse': spouse,
                'raw_text': raw
            }
            records.append(record)
    return records
