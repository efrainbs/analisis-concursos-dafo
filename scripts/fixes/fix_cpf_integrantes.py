#!/usr/bin/env python3
"""
Fix CPF integrantes - parse FalloFinal PDFs and add responsables.
Uses detect_table_columns from extract_2024.py for format detection.
"""
import sys, os, re, sqlite3, subprocess, unicodedata, hashlib

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
sys.path.insert(0, os.path.dirname(__file__))
DRY_RUN = '--run' not in sys.argv

from extract_2024 import detect_table_columns, normalize_name

CACHE_DIR = '/tmp/fallofinal_pdfs'
os.makedirs(CACHE_DIR, exist_ok=True)

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

def get_pdf_text(url):
    h = hashlib.md5(url.encode()).hexdigest()
    txt = os.path.join(CACHE_DIR, f'{h}.txt')
    if os.path.exists(txt):
        with open(txt) as f:
            return unicodedata.normalize('NFC', f.read())
    pdf = os.path.join(CACHE_DIR, f'{h}.pdf')
    subprocess.run(['curl', '-sLk', '--max-time', '45', '-o', pdf, url], capture_output=True, timeout=50)
    r = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True, timeout=30)
    t = unicodedata.normalize('NFC', r.stdout)
    with open(txt, 'w') as f:
        f.write(t)
    return t

# Get CPF projects grouped by PDF URL
projects = db.execute("""
    SELECT p.id as pid, per.razon_social, po.monto_otorgado, o.titulo,
           lc.codigo, c.anio, r.url_pdf
    FROM persona per
    JOIN proyecto po ON po.persona_beneficiaria_id = per.id
    JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    JOIN convocatoria c ON c.id = ca.convocatoria_id
    JOIN obra o ON o.id = po.obra_id
    JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
    JOIN resolucion r ON r.id = pr.resolucion_id
    WHERE lc.codigo = 'CPF'
      AND po.id NOT IN (SELECT proyecto_id FROM proyecto_integrante)
    ORDER BY r.url_pdf, po.id
""").fetchall()

print(f"Total CPF projects without integrante: {len(projects)}")

# Group by PDF URL
from collections import defaultdict
pdf_groups = defaultdict(list)
for p in projects:
    pdf_groups[p['url_pdf']].append(p)

for url, group in sorted(pdf_groups.items()):
    short = url.rsplit('/', 1)[-1]
    print(f"\n=== {len(group)} projects in {short} ===")
    
    text = get_pdf_text(url)
    if not text:
        print("  ERROR: Could not download/extract PDF")
        continue
    
    lines = text.split('\n')
    
    # Detect table columns using the extract_2024 function
    try:
        col_defs = detect_table_columns(lines, extra_keywords=['RESPONSABLE', 'DIRECTOR'])
    except Exception as e:
        print(f"  ERROR detecting columns: {e}")
        continue
    
    if not col_defs:
        print("  WARNING: No columns detected")
        continue
    
    print(f"  Columns: {[c[0] for c in col_defs]}")
    
    # Parse rows
    found = 0
    for p in group:
        razon = p['razon_social'].strip().upper()
        monto = p['monto_otorgado']
        
        # Try to find this project in the PDF by empresa name + monto
        # Search for empresa name first
        best_match = None
        best_score = 0
        
        for i, line in enumerate(lines):
            s = line.strip().upper()
            if not s:
                continue
            # Check if empresa name appears on this line
            # Extract empresa from the line based on column defs
            for col_name, start, end in col_defs:
                if col_name == 'empresa':
                    empresa_text = s[start:end].strip() if end <= len(s) else s[start:].strip()
                    if empresa_text and len(empresa_text) > 5:
                        # Simple match: empresa name is substring of line
                        if razon[:20] in empresa_text.upper() or empresa_text[:20] in razon:
                            score = len(set(razon) & set(empresa_text))
                            if score > best_score:
                                best_score = score
                                best_match = (i, empresa_text, col_defs)
        
        if best_match:
            found += 1
            line_idx, empresa_text, cols = best_match
            # Extract responsable from this line
            responsable = ''
            for col_name, start, end in cols:
                if col_name in ('responsable', 'director'):
                    row_text = lines[line_idx]
                    responsable = row_text[start:end].strip() if end <= len(row_text) else row_text[start:].strip()
                    break
            
            if responsable:
                # Clean responsable name
                resp_clean = re.sub(r'\d{8}', '', responsable)
                resp_clean = re.sub(r'[()]', '', resp_clean)
                resp_clean = re.sub(r'DNI\s*N?[°º]?\s*', '', resp_clean, flags=re.IGNORECASE)
                resp_clean = resp_clean.strip().rstrip(',')
                resp_clean = re.sub(r'\s+', ' ', resp_clean).strip()
                resp_clean = re.sub(r'\s+[A-Z]{1,2}$', '', resp_clean).strip()
                
                print(f'  PID {p["pid"]}: {razon[:40]} → {resp_clean[:40]}')

print(f"\nDone. Matched {found}/{len(projects)} projects.")
db.close()
