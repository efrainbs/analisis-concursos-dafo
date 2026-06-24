#!/usr/bin/env python3
"""OCR and extract missing EPA 2021 RDs (603-611) using tesseract."""

import subprocess, re, os, sqlite3, sys
from urllib.request import urlopen

PDF_DIR = "/tmp/epa2021"
OCR_DIR = "/tmp/epa_ocr"
os.makedirs(OCR_DIR, exist_ok=True)

DB_PATH = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")

# RDs to process (all scanned, no text layer)
RDS = {
    603: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD603-2021-DGIA_MC.pdf",
    604: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD604-2021-DGIA_MC.pdf",
    605: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD605-2021-DGIA_MC.pdf",
    606: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD606-2021-DGIA_MC.pdf",
    607: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD607-2021-DGIA_MC.pdf",
    608: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD608-2021-DGIA_MC.pdf",
    609: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD609-2021-DGIA_MC.pdf",
    610: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD610-2021-DGIA_MC.pdf",
    611: "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD611-2021-DGIA_MC.pdf",
}

def download_pdf(rd_num, url):
    dest = os.path.join(PDF_DIR, f"rd{rd_num}.pdf")
    if os.path.exists(dest):
        return dest
    try:
        with urlopen(url, timeout=30) as f:
            with open(dest, 'wb') as out:
                out.write(f.read())
        return dest
    except Exception as e:
        print(f"  Download RD{rd_num} failed: {e}")
        return None

def ocr_pdf(pdf_path, rd_num):
    """OCR all pages and return combined text."""
    pages = None
    try:
        result = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True, timeout=30)
        for line in result.stdout.split('\n'):
            if 'Pages' in line:
                pages = int(line.split(':')[1].strip())
    except:
        pass
    if not pages:
        pages = 6  # guess
    
    all_text = []
    for p in range(1, pages + 1):
        ppm_path = os.path.join(OCR_DIR, f"rd{rd_num}_p{p}")
        subprocess.run(['pdftoppm', '-f', str(p), '-l', str(p), '-r', '300',
                       pdf_path, ppm_path], capture_output=True, timeout=60)
        ppm_file = f"{ppm_path}-1.ppm" if p == 1 else f"{ppm_path}-{p}.ppm"
        if not os.path.exists(ppm_file):
            # try alternate naming
            ppm_file = f"{ppm_path}-{p}.ppm"
        if not os.path.exists(ppm_file):
            continue
        out_path = os.path.join(OCR_DIR, f"rd{rd_num}_p{p}")
        subprocess.run(['tesseract', ppm_file, out_path, '-l', 'eng'],
                      capture_output=True, timeout=120)
        txt_path = out_path + '.txt'
        if os.path.exists(txt_path):
            with open(txt_path) as f:
                all_text.append(f.read())
    return '\n'.join(all_text)

def extract_data(text, rd_num):
    """Extract beneficiary, project title, amount from OCR text."""
    # Search for the table with PERSONA JURÍDICA, TÍTULO, MONTO
    # Pattern: look for S/ amount near PERSONA JURÍDICA
    lines = text.split('\n')
    
    # Find the resolution number
    res_num = None
    for m in re.finditer(r'RESOLUCION DIRECTORAL N[°º]\s*(\d+-\d{4}-DGIA/MC)', text):
        res_num = f"000{m.group(1)}" if len(m.group(1).split('-')[0]) < 4 else m.group(1)
    
    # Find PERSONA JURÍDICA block
    beneficiary = None
    project = None
    amount = None
    
    # Look for the table after "SE RESUELVE" or "Artículo Primero"
    table_text = ""
    in_table = False
    for i, line in enumerate(lines):
        if 'PERSONA' in line and 'JURÍDICA' in text[max(0,i-2):i+10]:
            in_table = True
            table_lines = []
        if in_table:
            table_lines.append(line)
            # Check for S/ amount
            amt_match = re.search(r'S[/]\s*(\d[\d\s]*,\d{2})', line)
            if amt_match:
                amount = amt_match.group(1).replace(' ', '')
                in_table = False
    
    # Alternative: look for amount with beneficiary name
    if not amount:
        for m in re.finditer(r'S[/]\s*(\d[\d\s]*,\d{2})', text):
            amount = m.group(1).replace(' ', '')
    
    # Extract beneficiary name - look for company name in the table area
    # Usually appears after "PERSONA JURÍDICA" header
    # Companies end with S.A.C., E.I.R.L., S.R.L., etc.
    
    # Find beneficiary in the text block
    person_match = re.search(
        r'PERSONA\s*JUR[IÍ]DICA.*?(?:\n\s*)([A-Z][A-Z\s&.]+(?:S\.?A\.?C?\.?|E\.?I\.?R\.?L\.?|S\.?R\.?L\.?))',
        text, re.DOTALL
    )
    if person_match:
        beneficiary = person_match.group(1).strip()
    
    # Try to find the project title
    title_indicators = ['T[IÍ]TULO', 'PROYECTO', 'OBRA']
    for indicator in title_indicators:
        idx = text.find(indicator)
        if idx >= 0:
            # Look for the text after the title header, before REGIÓN or RESPONSABLE
            chunk = text[idx:idx+500]
            lines_after = chunk.split('\n')[1:6]
            title_lines = []
            for tl in lines_after:
                tl = tl.strip()
                if not tl or any(w in tl.upper() for w in ['RESPONSABLE', 'MONTO', 'REGIÓN', 'REGION', 'S/']):
                    break
                title_lines.append(tl)
            if title_lines:
                project = ' '.join(title_lines)
                break
    
    return beneficiary, project, amount, res_num

# Connect to DB
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get concurso_anual_id for EPA 2021
ca = c.execute("""
    SELECT ca.id FROM concurso_anual ca
    JOIN convocatoria c ON c.id = ca.convocatoria_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    WHERE c.anio = 2021 AND lc.codigo = 'EPA'
    LIMIT 1
""").fetchone()
if not ca:
    print("EPA 2021 not found in DB!")
    sys.exit(1)
ca_id = ca[0]
print(f"concurso_anual_id: {ca_id}")

for rd_num, url in sorted(RDS.items()):
    print(f"\n=== RD{rd_num} ===")
    pdf = download_pdf(rd_num, url)
    if not pdf:
        continue
    
    text = ocr_pdf(pdf, rd_num)
    if len(text) < 100:
        print(f"  OCR failed (only {len(text)} chars)")
        continue
    
    beneficiary, project, amount, res_num = extract_data(text, rd_num)
    
    print(f"  Resolución: {res_num}")
    print(f"  Beneficiario: {beneficiary}")
    print(f"  Proyecto: {project}")
    print(f"  Monto: {amount}")
    
    if not amount:
        print("  SKIP: no amount found")
        continue
    if not beneficiary:
        print("  SKIP: no beneficiary found")
        continue
    
    # Check if this resolution already exists
    existing = c.execute(
        "SELECT id FROM resolucion WHERE numero = ?", (res_num,)
    ).fetchone()
    if existing:
        print(f"  Already exists: res ID {existing[0]}")
        continue
    
    # Insert
    # Parse amount
    amt_float = float(amount.replace(',', '.'))
    
    # Find or create persona
    per = c.execute(
        "SELECT id FROM persona WHERE razon_social = ? AND tipo = 'juridica'",
        (beneficiary,)
    ).fetchone()
    if per:
        per_id = per[0]
    else:
        c.execute("INSERT INTO persona (tipo, razon_social) VALUES ('juridica', ?)",
                  (beneficiary,))
        per_id = c.lastrowid
        print(f"  New persona: {per_id}")
    
    # Create project
    c.execute("INSERT INTO obra (titulo) VALUES (?)", (project or f"Proyecto RD{rd_num}",))
    proj_id = c.lastrowid
    
    # Create postulación
    c.execute("""
        INSERT INTO proyecto (concurso_anual_id, obra_id, persona_beneficiaria_id, monto_otorgado)
        VALUES (?, ?, ?, ?)
    """, (ca_id, proj_id, per_id, amt_float))
    post_id = c.lastrowid
    
    # Create resolución
    c.execute("""
        INSERT INTO resolucion (concurso_anual_id, numero, tipo, url_pdf)
        VALUES (?, ?, 'resolucion_beneficiario', ?)
    """, (ca_id, res_num, url))
    res_id = c.lastrowid
    
    # Link
    c.execute("INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
              (post_id, res_id))
    
    print(f"  INSERTED: post={post_id}, proj={proj_id}, per={per_id}, res={res_id}")

conn.commit()
conn.close()
print("\nDone!")
