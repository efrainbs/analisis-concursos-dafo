#!/usr/bin/env python3
"""
Extract responsables from FalloFinal PDFs by searching for each project's monto.
For each juridica without integrante, finds the monto in the PDF text
and extracts the responsable name from nearby lines.

Usage: python fix_fallofinal_integrantes.py [--run] [--lines CGC,CDO,CPF]
"""
import os, re, sqlite3, subprocess, sys, unicodedata, hashlib

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
DRY_RUN = '--run' not in sys.argv

LINES_FILTER = None
for a in sys.argv:
    if a.startswith('--lines='):
        LINES_FILTER = a.split('=')[1].split(',')

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

CACHE_DIR = '/tmp/fallofinal_pdfs'
os.makedirs(CACHE_DIR, exist_ok=True)

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

# Get all juridicas without integrante
projects = db.execute("""
    SELECT po.id as pid, per.razon_social, po.monto_otorgado, lc.codigo, c.anio,
           r.url_pdf, r.numero
    FROM persona per
    JOIN proyecto po ON po.persona_beneficiaria_id = per.id
    JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    JOIN convocatoria c ON c.id = ca.convocatoria_id
    JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
    JOIN resolucion r ON r.id = pr.resolucion_id
    WHERE per.tipo = 'juridica'
      AND lc.codigo IN ('CGC', 'CDO', 'CPF', 'CCM', 'CGS')
      AND po.id NOT IN (SELECT DISTINCT proyecto_id FROM proyecto_integrante)
      AND r.url_pdf LIKE '%Fallo%'
    ORDER BY lc.codigo, c.anio, po.id
""").fetchall()

print(f"Total projects to process: {len(projects)}")

def match_monto_in_text(text, monto):
    """Find all occurrences of a monto value in text. Returns list of positions."""
    # Try different formats
    patterns = [
        rf'S/\.?\s*{monto:,.2f}'.replace(',', r'[.,]?'),
        rf'S/\.?\s*{monto:,.0f}'.replace(',', r'[.,]?'),
        rf'{monto:,.2f}'.replace(',', r'[.,]?'),
        rf'{monto:,.0f}'.replace(',', r'[.,]?'),
    ]
    # Also try with different thousand/decimal separators
    monto_str1 = f"{monto:,.2f}"  # 340,200.00
    monto_str2 = f"{monto:,.2f}".replace(',', '')  # 340200.00
    monto_str3 = f"{monto:,.2f}".replace('.', ',').replace(',', '.')  # 340.200,00
    
    positions = []
    for pat in [monto_str1, monto_str2, monto_str3, str(int(monto))]:
        idx = text.find(pat)
        if idx >= 0:
            positions.append(idx)
    return positions

def extract_name_near_position(text, pos, max_lookback=15):
    """Look backwards from a position to find a responsable name."""
    # Get lines before the position
    before = text[:pos]
    lines = before.split('\n')
    
    # Take the last N lines
    relevant = []
    for line in reversed(lines[-max_lookback:]):
        s = line.strip()
        if not s:
            continue
        # Skip known non-name lines
        skip_words = ['persona', 'jurídica', 'región', 'proyecto', 'director',
                      'monto', 'otorgado', 's/', 'soles', 'ministerio',
                      'cultura', 'decreto', 'artículo', 'resuelve', 'página',
                      'decenio', 'firmado', 'copía', 'clave', 'esta es una',
                      'despacho', 'patrimonio', 'general', 'dirección',
                      'bicentenario', 'año del', 'perú', 'san borja',
                      'ruc', 'lima', 'callao', 'arequipa', 'cusco', 'puno',
                      'junín', 'lambayeque', 'la libertad', 'piura',
                      'cajamarca', 'ica', 'áncash', 'apurímac',
                      'huancavelica', 'huánuco', 'ucayali', 'amazonas',
                      'loreto', 'madre de dios', 'moquegua', 'pasco',
                      'san martín', 'tacna', 'tumbes', 'ayacucho',
                      'inscripción', 'registro', 'público', 'e.i.r.l',
                      's.a.c', 's.r.l', 's.a', 'cerrada', 'empresa',
                      'individual', 'responsabilidad', 'limitada',
                      'asociación', 'asociacion', 'cultural']
        if any(w in s.lower() for w in skip_words):
            continue
        # Upper case name: looks like a person name
        if s.isupper() and len(s) >= 8 and len(s) <= 100:
            # Exclude lines that look like project titles (not all caps usually)
            # A person name in "APELLIDOS, NOMBRES" format has a comma
            # Or "NOMBRE APELLIDO" format with 2-5 words
            words = s.split()
            if 2 <= len(words) <= 8:
                relevant.append(s)
    
    return relevant[-1] if relevant else None

results = []  # (pid, name_text)
for p in projects:
    pid, codigo, anio, url, monto = p['pid'], p['codigo'], p['anio'], p['url_pdf'], p['monto_otorgado']
    razon = p['razon_social']
    
    if LINES_FILTER and codigo not in LINES_FILTER:
        continue
    
    text = get_pdf_text(url)
    if not text:
        continue
    
    # Search for monto in text
    positions = match_monto_in_text(text, monto)
    if not positions:
        print(f"  {codigo} {anio} PID {pid} (S/{monto:,.0f}): monto NOT FOUND in PDF")
        continue
    
    # Try each position
    name = None
    for pos in positions:
        name = extract_name_near_position(text, pos)
        if name:
            break
    
    if name:
        print(f"  {codigo} {anio} PID {pid} (S/{monto:,.0f}): {razon[:50]} → {name}")
        results.append((pid, name))
    else:
        print(f"  {codigo} {anio} PID {pid} (S/{monto:,.0f}): name NOT FOUND near monto")

print(f"\nFound: {len(results)}/{len(projects)}")

db.close()
