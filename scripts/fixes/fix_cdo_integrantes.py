#!/usr/bin/env python3
"""
Extract responsables from CDO FalloFinal PDFs.
CDO columns: PERSONA JURÍDICA | REGIÓN | PROYECTO | DIRECTOR(ES/AS) or RESPONSABLE(S) | MONTO

Usage: python fix_cdo_integrantes.py [--run]
"""
import os, re, sqlite3, subprocess, sys, unicodedata, hashlib

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
DRY_RUN = '--run' not in sys.argv

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Get CDO projects without integrante, grouped by URL
groups = db.execute("""
    SELECT r.url_pdf, c.anio,
           GROUP_CONCAT(po.id, ',') as proj_ids,
           GROUP_CONCAT(per.razon_social, '|||') as razones,
           GROUP_CONCAT(po.monto_otorgado, ',') as montos
    FROM persona per
    JOIN proyecto po ON po.persona_beneficiaria_id = per.id
    JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    JOIN convocatoria c ON c.id = ca.convocatoria_id
    JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
    JOIN resolucion r ON r.id = pr.resolucion_id
    WHERE per.tipo = 'juridica'
      AND lc.codigo = 'CDO'
      AND po.id NOT IN (SELECT DISTINCT proyecto_id FROM proyecto_integrante)
      AND r.url_pdf LIKE '%Fallo%'
    GROUP BY r.id
    ORDER BY c.anio
""").fetchall()

def get_pdf_text(url):
    h = hashlib.md5(url.encode()).hexdigest()
    txt = os.path.join('/tmp/fallofinal_pdfs', f'{h}.txt')
    if os.path.exists(txt):
        with open(txt) as f:
            return unicodedata.normalize('NFC', f.read())
    pdf = os.path.join('/tmp/fallofinal_pdfs', f'{h}.pdf')
    subprocess.run(['curl', '-sLk', '--max-time', '45', '-o', pdf, url], capture_output=True, timeout=50)
    r = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True, timeout=30)
    t = unicodedata.normalize('NFC', r.stdout)
    with open(txt, 'w') as f:
        f.write(t)
    return t

def extract_table(text):
    """Extract table rows between Artículo Primero and Artículo Segundo."""
    text_lower = text.lower()
    start = text_lower.find('artículo primero')
    if start < 0:
        start = text_lower.find('articulo primero')
    if start < 0:
        return []
    
    # Find end markers
    end = len(text)
    for m in ['artículo segundo', 'articulo segundo', 'artículo tercero', 'articulo tercero']:
        i = text_lower.find(m, start + 10)
        if 0 < i < end:
            end = i
    
    block = text[start:end]
    
    # Parse rows: each row has multiple lines
    # Pattern: juridica name on its own line, followed by region, project, director, monto
    lines = block.split('\n')
    
    # Find which lines look like juridica names (all caps, 3+ words, not boilerplate)
    rows = []
    current = []
    for line in lines:
        s = line.strip()
        if not s:
            if current:
                rows.append(current)
                current = []
            continue
        # Skip header/boilerplate lines
        skip_words = ['persona jurídica', 'región', 'proyecto', 'director', 'responsable',
                      'monto', 'otorgado', 's/', 'soles', 'ministerio', 'cultura',
                      'decreto', 'artículo', 'resuelve', 'página', 'decenio',
                      'año del', 'perú', 'esta es una copia', 'firmado']
        if any(w in s.lower() for w in skip_words):
            continue
        current.append(s)
    
    if current:
        rows.append(current)
    
    return rows

for g in groups:
    url, anio = g['url_pdf'], g['anio']
    proj_ids = [int(x) for x in g['proj_ids'].split(',')]
    razones = g['razones'].split('|||')
    montos = [float(x) for x in g['montos'].split(',')]
    
    print(f"\n=== CDO {anio} ({len(proj_ids)} projects) ===")
    text = get_pdf_text(url)
    rows = extract_table(text)
    
    if not rows:
        print("  [NO ROWS FOUND]")
        # Print raw text for debugging
        idx = text.lower().find('artículo primero')
        if idx >= 0:
            print(text[idx:idx+500])
        continue
    
    print(f"  Rows: {len(rows)}")
    for i, row in enumerate(rows):
        print(f"  Row {i}: {' | '.join(row[:4])}")

db.close()
