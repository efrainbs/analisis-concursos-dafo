#!/usr/bin/env python3
"""
Extract EDI tipo (Comercial/Alternativa) from each RD PDF and assign modalidad.
Creates modalidad records per (concurso_anual_id, tipo) if needed.

Usage:
  python fix_edi_modalidades.py [--run]
"""
import os, re, sqlite3, subprocess, sys, hashlib, unicodedata

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
DRY_RUN = '--run' not in sys.argv

PDF_DIR = '/tmp/edi_pdfs'
os.makedirs(PDF_DIR, exist_ok=True)

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

projects = db.execute("""
    SELECT po.id, po.monto_otorgado, c.anio, ca.id as concurso_anual_id,
           r.url_pdf
    FROM proyecto po
    JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
    JOIN convocatoria c ON c.id = ca.convocatoria_id
    JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
    JOIN resolucion r ON r.id = pr.resolucion_id
    WHERE ca.linea_concursable_id = (SELECT id FROM linea_concursable WHERE codigo = 'EDI')
    ORDER BY c.anio, po.id
""").fetchall()

print(f"EDI projects: {len(projects)}")

def download_and_extract(url):
    # Use hash of URL as filename for reliability
    fname = hashlib.md5(url.encode()).hexdigest()
    fpath = os.path.join(PDF_DIR, fname + '.txt')
    if os.path.exists(fpath):
        with open(fpath) as f:
            return f.read()
    pdf_path = os.path.join(PDF_DIR, fname + '.pdf')
    try:
        subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url],
                       capture_output=True, timeout=35)
        result = subprocess.run(['pdftotext', '-layout', pdf_path, '-'],
                                capture_output=True, text=True, timeout=30)
        text = result.stdout
        with open(fpath, 'w') as f:
            f.write(text)
        return text
    except Exception as e:
        print(f"  Error: {e}")
        return ''

results = []  # (proyecto_id, tipo)
for p in projects:
    pid, monto, anio, ca_id, url = p['id'], p['monto_otorgado'], p['anio'], p['concurso_anual_id'], p['url_pdf']
    
    # Only download if monto <= 70000 (ambiguous) or if we haven't seen this URL
    text = download_and_extract(url)
    
    tipo = None
    # Normalize to NFC (precomposed accents)
    text = unicodedata.normalize('NFC', text)
    text_lower = text.lower()
    
    # Search for the specific model line: "postula con el modelo de distribución ..."
    # The text may have newlines between words, so use \s+
    model_match = re.search(
        r'modelo de\s+distribuci[oó]n\s+(comercial|alternativa|en l[ií]nea)',
        text_lower
    )
    if model_match:
        tipo_raw = model_match.group(1)
        if tipo_raw == 'en l\xednea' or tipo_raw == 'en línea':
            tipo = 'En línea'
        elif tipo_raw == 'comercial':
            tipo = 'Comercial'
        elif tipo_raw == 'alternativa':
            tipo = 'Alternativa'
    
    # Fallback: search for "distribución comercial/alternativa" near "postula"
    if not tipo:
        fallback = re.search(
            r'postula.*?distribuci[oó]n\s+(comercial|alternativa)',
            text_lower, re.DOTALL
        )
        if fallback:
            tipo_raw = fallback.group(1)
            if tipo_raw == 'comercial':
                tipo = 'Comercial'
            elif tipo_raw == 'alternativa':
                tipo = 'Alternativa'
    
    # Last resort: search for standalone mentions
    if not tipo:
        lines = [l for l in text_lower.split('\n') if 'comercial' in l or 'alternativa' in l]
        for line in lines:
            if 'modelo de distribución comercial' in line.replace('\n', ' '):
                tipo = 'Comercial'
                break
            if 'modelo de distribución alternativa' in line.replace('\n', ' '):
                tipo = 'Alternativa'
                break
    
    if tipo:
        results.append((pid, tipo, anio, ca_id, monto))
        print(f"  ID {pid} ({anio}, S/{monto:,.0f}): {tipo}")
    else:
        print(f"  ID {pid} ({anio}, S/{monto:,.0f}): NO TYPE FOUND")

print(f"\nClassified: {len(results)}/{len(projects)}")

if not results:
    print("No results to process")
    sys.exit(0)

if DRY_RUN:
    print("\n=== DRY RUN ===")
    print(f"  Comercial: {sum(1 for r in results if r[1]=='Comercial')}")
    print(f"  Alternativa: {sum(1 for r in results if r[1]=='Alternativa')}")
else:
    db.execute("BEGIN")
    
    # Create modalidad records: one per (concurso_anual_id, tipo)
    tipo_por_ca = {}  # (concurso_anual_id, tipo) -> modalidad_id
    for pid, tipo, anio, ca_id, monto in results:
        key = (ca_id, tipo)
        if key not in tipo_por_ca:
            # Check if modalidad already exists
            existing = db.execute(
                "SELECT id FROM modalidad WHERE concurso_anual_id=? AND nombre=?",
                (ca_id, tipo)
            ).fetchone()
            if existing:
                tipo_por_ca[key] = existing['id']
                print(f"  Modalidad exists: {anio} {tipo} (ID {existing['id']})")
            else:
                cur = db.execute(
                    "INSERT INTO modalidad (concurso_anual_id, nombre) VALUES (?, ?)",
                    (ca_id, tipo)
                )
                tipo_por_ca[key] = cur.lastrowid
                print(f"  Created modalidad: {anio} {tipo} (ID {cur.lastrowid})")
    
    # Assign modalidad_id to each project
    for pid, tipo, anio, ca_id, monto in results:
        mod_id = tipo_por_ca[(ca_id, tipo)]
        db.execute("UPDATE proyecto SET modalidad_id=? WHERE id=?", (mod_id, pid))
    
    db.commit()
    c = sum(1 for r in results if r[1]=='Comercial')
    a = sum(1 for r in results if r[1]=='Alternativa')
    print(f"\nDone! {c} Comercial, {a} Alternativa assigned.")

db.close()
