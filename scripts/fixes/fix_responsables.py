"""
Fix responsables for juridical projects using extractor's PDF parser.

Usage: python3 fix_responsables.py [--run]
"""
import os
import re
import sqlite3
import subprocess
import sys
import unicodedata

DB_PATH = "/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
TMP_DIR = "/tmp/fix_resp_pdfs"
os.makedirs(TMP_DIR, exist_ok=True)

# Import extractor's parser
sys.path.insert(0, os.path.dirname(DB_PATH))
from extract_2024 import parse_fallo_beneficiaries, FALLO_HEADER_KEYWORDS

DRY_RUN = "--run" not in sys.argv

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

# ── Get FalloFinal PDFs ──

def get_fallo_urls():
    rows = db.execute("""
        SELECT DISTINCT r.url_pdf
        FROM proyecto p
        JOIN persona pe ON p.persona_beneficiaria_id = pe.id AND pe.tipo = 'juridica'
        JOIN proyecto_integrante pi ON p.id = pi.proyecto_id AND pi.persona_id = p.persona_beneficiaria_id AND pi.rol = 'responsable'
        JOIN proyecto_resolucion pr ON p.id = pr.proyecto_id
        JOIN resolucion r ON pr.resolucion_id = r.id
        JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
        JOIN convocatoria c ON ca.convocatoria_id = c.id
        WHERE r.url_pdf LIKE '%Fallo%'
          AND c.anio = 2025
          AND NOT EXISTS (
            SELECT 1 FROM proyecto_integrante pi2 
            WHERE pi2.proyecto_id = p.id AND pi2.persona_id != p.persona_beneficiaria_id
          )
    """).fetchall()
    return [r["url_pdf"] for r in rows]

def get_incorrect_projects():
    rows = db.execute("""
        SELECT p.id, pe.razon_social, o.titulo, ca.id as ca_id, r.id as resolucion_id, r.url_pdf, c.anio
        FROM proyecto p
        JOIN persona pe ON p.persona_beneficiaria_id = pe.id AND pe.tipo = 'juridica'
        JOIN proyecto_integrante pi ON p.id = pi.proyecto_id AND pi.persona_id = p.persona_beneficiaria_id AND pi.rol = 'responsable'
        JOIN obra o ON p.obra_id = o.id
        JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
        JOIN convocatoria c ON ca.convocatoria_id = c.id
        JOIN proyecto_resolucion pr ON p.id = pr.proyecto_id
        JOIN resolucion r ON pr.resolucion_id = r.id
        WHERE r.url_pdf LIKE '%Fallo%'
          AND c.anio = 2025
          AND NOT EXISTS (
            SELECT 1 FROM proyecto_integrante pi2 
            WHERE pi2.proyecto_id = p.id AND pi2.persona_id != p.persona_beneficiaria_id
          )
    """).fetchall()
    return [dict(r) for r in rows]

# ── Parse FalloFinal PDF ──

def parse_pdf(url):
    pdf_name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('/')[-1])[:80]
    pdf_path = os.path.join(TMP_DIR, pdf_name)
    txt_path = pdf_path + "_layout.txt"

    if not os.path.exists(pdf_path):
        ret = subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url],
                           capture_output=True, timeout=45)
        if ret.returncode != 0:
            return None, f"download failed"

    if not os.path.exists(txt_path):
        ret = subprocess.run(['pdftotext', '-layout', pdf_path, txt_path],
                           capture_output=True, timeout=30)
        if ret.returncode != 0:
            return None, f"pdftotext failed"

    with open(txt_path) as f:
        text = f.read()
    text = unicodedata.normalize('NFC', text)

    # Extract Artículo Primero section
    a1_match = re.search(
        r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO|Artículo\s)',
        text, re.DOTALL
    )
    if not a1_match:
        a1_match = re.search(
            r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|ART[ÍI]CULO SEGUNDO|Artículo\s|ART[ÍI]CULO\s)',
            text, re.DOTALL
        )
    if not a1_match:
        return None, "No ARTÍCULO PRIMERO"

    a1 = a1_match.group(1)

    # Use extractor's parser
    beneficiaries = parse_fallo_beneficiaries(a1)

    return beneficiaries, None

# ── Match to DB ──

def normalize(s):
    s = (s or '').upper()
    s = re.sub(r'[^A-ZÁÉÍÓÚÑ0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def score_match(entry, db_proj):
    emp_norm = normalize(entry.get('empresa', ''))
    proy_norm = normalize(entry.get('proyecto', ''))
    razon = normalize(db_proj['razon_social'])
    titulo = normalize(db_proj['titulo'])

    score = 0.0

    # empresa similarity
    ew = set(emp_norm.split())
    rw = set(razon.split())
    if ew and rw:
        common = ew & rw
        score += len(common) * 2.0  # up to ~20 points for empresa

    # obra similarity  
    ow = set(proy_norm.split())
    tw = set(titulo.split())
    if ow and tw:
        common = ow & tw
        score += len(common) * 2.0  # up to ~20 points for obra

    return score

def find_persona(nombres, apellidos):
    return db.execute("""
        SELECT id FROM persona 
        WHERE tipo = 'natural' AND nombres = ? AND apellidos = ?
    """, (nombres, apellidos)).fetchone()

def create_persona(nombres, apellidos):
    db.execute("""
        INSERT INTO persona (tipo, nombres, apellidos, dni)
        VALUES ('natural', ?, ?, '')
    """, (nombres, apellidos))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]

def clean_resp_text(text):
    text = re.sub(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', '', text)  # remove S/ amounts
    text = re.sub(r'\(\d{11}\)', '', text)  # remove RUC
    text = re.sub(r'\d{8}', '', text)  # remove DNI
    text = re.sub(r'RESPONSABLE\s*\(\s*S?\s*\)?\s*DEL\s*PROYECTO', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[()]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_responsable(resp_text):
    """Parse 'APELLIDOS, NOMBRES' or 'NOMBRES APELLIDOS'."""
    resp_text = clean_resp_text(resp_text)
    entries = []
    parts = re.split(r'\s*/\s*', resp_text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if ',' in part:
            ap, nom = part.split(',', 1)
            entries.append((nom.strip(), ap.strip()))
        else:
            words = part.split()
            if len(words) >= 4:
                entries.append((' '.join(words[:-2]), ' '.join(words[-2:])))
            elif len(words) == 3:
                entries.append((words[0], ' '.join(words[1:])))
            elif len(words) == 2:
                entries.append((words[0], words[1]))
            else:
                entries.append((part, ''))
    # Title case each part, strip trailing junk
    result = []
    for n, a in entries:
        n = re.sub(r'\s+[A-Za-z]\s*$', '', n).strip()  # trailing single letter
        a = a.strip().rstrip(',').strip()
        if n and len(n) >= 2:
            result.append((n.title(), a.title()))
    return result

def is_valid_name(nombres, apellidos):
    if len(nombres) < 2 and len(apellidos) < 2:
        return False
    full = f"{nombres} {apellidos}".strip()
    if re.match(r'^[\d\s,.S/]+$', full):
        return False  # just numbers, monto values
    if len(full.split()) < 2:
        return False  # need at least 2 words
    if len(full) < 5:
        return False
    # Check it's a person name, not a fragment
    if re.search(r'S/?\s*\d', full):
        return False  # contains monto value
    return True

def main():
    urls = get_fallo_urls()
    all_projects = get_incorrect_projects()
    
    # Group projects by URL
    proj_by_url = {}
    for p in all_projects:
        proj_by_url.setdefault(p['url_pdf'], []).append(p)
    
    print(f"FalloFinal PDFs: {len(urls)}")
    print(f"Incorrect projects: {len(all_projects)}")
    
    total_inserts = 0
    total_skipped = 0
    
    for i, url in enumerate(urls):
        fname = url.split('/')[-1][:60]
        print(f"\n[{i+1}/{len(urls)}] {fname}")
        
        entries, err = parse_pdf(url)
        if err:
            print(f"  SKIP: {err}")
            continue
        if not entries:
            print(f"  No beneficiaries found")
            continue
        
        db_projs = proj_by_url.get(url, [])
        if not db_projs:
            print(f"  No DB projects for this URL")
            continue
        
        print(f"  PDF entries: {len(entries)}, DB projects: {len(db_projs)}")
        
        # Find best match for each DB project
        for dp in db_projs:
            best = None
            best_score = 0
            for e in entries:
                s = score_match(e, dp)
                if s > best_score:
                    best_score = s
                    best = e
            
            if best and best_score >= 6:
                resp_text = best.get('responsable', best.get('director', ''))
                if not resp_text:
                    print(f"  - proj={dp['id']}: matched but no responsable (score={best_score})")
                    continue
                
                responsables = parse_responsable(resp_text)
                # Filter valid names only
                valid_resp = [(n, a) for n, a in responsables if is_valid_name(n, a)]
                
                if not valid_resp:
                    print(f"  ✗ proj={dp['id']}: invalid name '{resp_text[:40]}' (score={best_score})")
                    total_skipped += 1
                    continue
                
                if DRY_RUN:
                    names = ", ".join(f"{n} {a}" for n, a in valid_resp)
                    print(f"  ✓ proj={dp['id']}: {dp['razon_social'][:30]} → {names} (score={best_score})")
                    continue
                
                for nom, ape in valid_resp:
                    existing = find_persona(nom, ape)
                    if existing:
                        pid = existing['id']
                    else:
                        pid = create_persona(nom, ape)
                        print(f"    + persona: {nom} {ape} (id={pid})")
                    
                    exists = db.execute("""
                        SELECT id FROM proyecto_integrante
                        WHERE proyecto_id = ? AND persona_id = ? AND rol = 'responsable'
                    """, (dp['id'], pid)).fetchone()
                    
                    if not exists:
                        db.execute("""
                            INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol)
                            VALUES (?, ?, 'responsable')
                        """, (dp['id'], pid))
                        print(f"    + integrante: proj={dp['id']}, {nom} {ape}")
                        total_inserts += 1
                
                # Remove company-as-responsable
                db.execute("""
                    DELETE FROM proyecto_integrante 
                    WHERE proyecto_id = ? AND persona_id = (
                        SELECT persona_beneficiaria_id FROM proyecto WHERE id = ?
                    ) AND rol = 'responsable'
                """, (dp['id'], dp['id']))
            else:
                print(f"  ✗ proj={dp['id']}: no match (best={best_score})")
                total_skipped += 1
                if best:
                    print(f"    best: {best.get('empresa','')[:30]} / {best.get('proyecto','')[:30]}")
    
    if not DRY_RUN:
        db.commit()
    
    print(f"\n{'='*50}")
    print(f"Resumen:")
    print(f"  PDFs procesados: {len(urls)}")
    if DRY_RUN:
        print(f"  Skipped (invalid/unmatched): {total_skipped}")
        print(f"  🔶 DRY RUN")
    else:
        print(f"  Responsables insertados: {total_inserts}")
        print(f"  Skipped (invalid/unmatched): {total_skipped}")
        print(f"  ✅ Hecho")

if __name__ == '__main__':
    main()
