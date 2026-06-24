#!/usr/bin/env python3
"""
Extract missing DNI/RUC from PDFs for resolutions where documento is missing.

Approach: for each resolution with missing documentos, download the PDF,
run pdftotext, and search for DNI (8 digits) / RUC (11 digits) patterns
near the beneficiary's name.
"""

import sqlite3, os, subprocess, re, sys, time
from collections import defaultdict
from urllib.request import urlopen
from urllib.error import URLError

PDF_DIR = "/tmp/dafo_dni_ruc"
os.makedirs(PDF_DIR, exist_ok=True)

DB_PATH = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")
BACKUP_PATH = DB_PATH + ".pre_dni_ruc_fix"
os.system(f"cp {DB_PATH} {BACKUP_PATH}")
print(f"Backup: {BACKUP_PATH}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ── Build list of (person_id, persona_tipo, nombres, apellidos, razon_social, url_pdf) ──
rows = c.execute("""
    SELECT DISTINCT p.id as person_id, p.tipo, p.nombres, p.apellidos, p.razon_social,
           r.url_pdf, r.id as resolucion_id
    FROM persona p
    JOIN proyecto po ON po.persona_beneficiaria_id = p.id
    JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
    JOIN convocatoria co ON co.id = ca.convocatoria_id
    JOIN proyecto_resolucion pr2 ON pr2.proyecto_id = po.id
    JOIN resolucion r ON r.id = pr2.resolucion_id
    WHERE ((p.tipo = 'natural' AND (p.dni IS NULL OR p.dni = ''))
       OR (p.tipo = 'juridica' AND (p.ruc IS NULL OR p.ruc = '')))
      AND r.url_pdf IS NOT NULL
    ORDER BY co.anio DESC, r.id
""").fetchall()

print(f"Total personas to check: {len(rows)}")

DNI_RE = re.compile(r'(?<!\d)(\d{8})(?!\d)')
RUC_RE = re.compile(r'(?<!\d)(10|20)\d{9}(?!\d)')
LBL_DNI = re.compile(r'DNI\s*N[°º]?\s*(\d{8})', re.IGNORECASE)
LBL_RUC = re.compile(r'RUC\s*N[°º]?\s*(\d{11})', re.IGNORECASE)

def download_pdf(url, dest):
    try:
        with urlopen(url, timeout=30) as f:
            data = f.read()
        with open(dest, 'wb') as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  Download failed: {e}")
        return False

def extract_text(pdf_path):
    try:
        result = subprocess.run(
            ['pdftotext', pdf_path, '-'],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except Exception:
        return ''

def name_variants(nombres, apellidos):
    """Generate name variations for matching."""
    full = f"{nombres} {apellidos}" if apellidos else nombres or ''
    variants = {full}
    if apellidos:
        # "ENRIQUE MIGUEL MÉNDEZ VALVERDE" split as nombres="ENRIQUE MIGUEL MÉNDEZ" apellidos="VALVERDE"
        variants.add(f"{nombres} {apellidos}")
        # Also with comma: "MÉNDEZ VALVERDE, ENRIQUE MIGUEL"
        variants.add(f"{apellidos}, {nombres}")
        # Try each word
        name_words = set((nombres or '').split() + (apellidos or '').split())
        if len(name_words) >= 2:
            variants.add(' '.join(name_words))
    return {v.upper().strip() for v in variants if v.strip()}

def find_doc_in_text(text, tipo, name_variants_set):
    """
    Find DNI or RUC near the beneficiary's name in the text.
    Returns (doc_number, match_confidence) or (None, 0).
    """
    text_upper = text.upper()
    
    if tipo == 'natural':
        # Try labeled DNI first (most reliable)
        for m in LBL_DNI.finditer(text_upper):
            doc = m.group(1)
            # Check if name is nearby (within 500 chars)
            start = max(0, m.start() - 500)
            end = min(len(text_upper), m.end() + 100)
            context = text_upper[start:end]
            for nv in name_variants_set:
                if nv in context:
                    return doc, 3  # high confidence: labeled + name proximity
        
        # Try DNI near name (no label)
        for nv in name_variants_set:
            idx = text_upper.find(nv)
            if idx >= 0:
                # Search within 200 chars of name
                chunk = text_upper[max(0,idx-200):idx+200]
                for m in DNI_RE.finditer(chunk):
                    return m.group(1), 2
        
        # Last resort: any DNI in document (low confidence)
        dnies = DNI_RE.findall(text_upper)
        if dnies:
            return dnies[0], 1
        return None, 0
    
    else:  # juridica
        for m in LBL_RUC.finditer(text_upper):
            doc = m.group(1)
            start = max(0, m.start() - 500)
            end = min(len(text_upper), m.end() + 100)
            context = text_upper[start:end]
            for nv in name_variants_set:
                if nv in context:
                    return doc, 3
        
        for nv in name_variants_set:
            idx = text_upper.find(nv)
            if idx >= 0:
                chunk = text_upper[max(0,idx-200):idx+200]
                for m in RUC_RE.finditer(chunk):
                    return m.group(1), 2
        
        rucs = RUC_RE.findall(text_upper)
        if rucs:
            return rucs[0], 1
        return None, 0

# Group by URL to avoid re-downloading
url_groups = defaultdict(list)
for r in rows:
    url_groups[r['url_pdf']].append(r)

fixed_dni = 0
fixed_ruc = 0
total_pdf = len(url_groups)

for pdf_idx, (url, persons) in enumerate(url_groups.items(), 1):
    pdf_name = re.sub(r'[^a-zA-Z0-9._-]', '_', url.split('/')[-1] or f'pdf_{pdf_idx}')
    pdf_path = os.path.join(PDF_DIR, pdf_name)
    
    if not os.path.exists(pdf_path):
        if not download_pdf(url, pdf_path):
            continue
        time.sleep(0.5)  # rate limit
    
    text = extract_text(pdf_path)
    if not text.strip():
        continue
    
    print(f"  [{pdf_idx}/{total_pdf}] {pdf_name}")
    
    for p in persons:
        nv = name_variants(p['nombres'], p['apellidos']) if p['tipo'] == 'natural' else name_variants(p['razon_social'], '')
        doc, conf = find_doc_in_text(text, p['tipo'], nv)
        
        if doc and conf >= 2:  # Only use medium+ confidence
            if p['tipo'] == 'natural':
                old = c.execute("SELECT dni FROM persona WHERE id = ?", (p['person_id'],)).fetchone()['dni']
                if not old:
                    c.execute("UPDATE persona SET dni = ? WHERE id = ?", (doc, p['person_id']))
                    fixed_dni += 1
                    print(f"    DNI {doc} → persona {p['person_id']} ({p['nombres']} {p['apellidos']}) conf={conf}")
            else:
                old = c.execute("SELECT ruc FROM persona WHERE id = ?", (p['person_id'],)).fetchone()['ruc']
                if not old:
                    c.execute("UPDATE persona SET ruc = ? WHERE id = ?", (doc, p['person_id']))
                    fixed_ruc += 1
                    print(f"    RUC {doc} → persona {p['person_id']} ({p['razon_social']}) conf={conf}")

conn.commit()

# Summary
total = c.execute("SELECT COUNT(*) FROM persona").fetchone()[0]
with_dni = c.execute("SELECT COUNT(*) FROM persona WHERE tipo='natural' AND dni IS NOT NULL AND dni != ''").fetchone()[0]
with_ruc = c.execute("SELECT COUNT(*) FROM persona WHERE tipo='juridica' AND ruc IS NOT NULL AND ruc != ''").fetchone()[0]
all_nat = c.execute("SELECT COUNT(*) FROM persona WHERE tipo='natural'").fetchone()[0]
all_jur = c.execute("SELECT COUNT(*) FROM persona WHERE tipo='juridica'").fetchone()[0]

print(f"\nDNI fixed: {fixed_dni}")
print(f"RUC fixed: {fixed_ruc}")
print(f"Naturales: {with_dni}/{all_nat} con DNI ({(with_dni/all_nat*100):.0f}%)")
print(f"Jurídicas: {with_ruc}/{all_jur} con RUC ({(with_ruc/all_jur*100):.0f}%)")
print(f"Done! Backup at: {BACKUP_PATH}")

conn.close()
