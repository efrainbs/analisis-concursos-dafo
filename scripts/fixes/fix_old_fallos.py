"""
Fix older FalloFinal PDFs (2019-2024) using regex-based director/responsable extraction.
Strategy:
1. Download PDF, run pdftotext -layout
2. Extract Artículo Primero section  
3. Use extractor's block grouping + regex to find director/responsable names
4. Match empresa→obra→director to DB records
5. Insert correct integrante

Usage: python3 fix_old_fallos.py [--run]
"""
import os, re, sqlite3, subprocess, sys, unicodedata
sys.path.insert(0, "/home/efrain/Projects/Analisis_Concursos_DAFO")
from extract_2024 import parse_fallo_beneficiaries, FALLO_HEADER_KEYWORDS

DB_PATH = "/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
TMP_DIR = "/tmp/fix_resp_pdfs"
os.makedirs(TMP_DIR, exist_ok=True)
DRY_RUN = "--run" not in sys.argv

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

def get_fallo_urls():
    rows = db.execute("""
        SELECT DISTINCT r.url_pdf
        FROM proyecto p
        JOIN persona pe ON p.persona_beneficiaria_id = pe.id AND pe.tipo = 'juridica'
        JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
        JOIN convocatoria c ON ca.convocatoria_id = c.id
        JOIN proyecto_resolucion pr ON p.id = pr.proyecto_id
        JOIN resolucion r ON pr.resolucion_id = r.id
        WHERE r.url_pdf LIKE '%Fallo%' AND c.anio <= 2024
          AND NOT EXISTS (
            SELECT 1 FROM proyecto_integrante pi WHERE pi.proyecto_id = p.id
          )
    """).fetchall()
    return [r["url_pdf"] for r in rows]

def get_projects_by_url():
    rows = db.execute("""
        SELECT r.url_pdf, p.id, pe.razon_social, o.titulo
        FROM proyecto p
        JOIN persona pe ON p.persona_beneficiaria_id = pe.id AND pe.tipo = 'juridica'
        JOIN obra o ON p.obra_id = o.id
        JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
        JOIN convocatoria c ON ca.convocatoria_id = c.id
        JOIN proyecto_resolucion pr ON p.id = pr.proyecto_id
        JOIN resolucion r ON pr.resolucion_id = r.id
        WHERE r.url_pdf LIKE '%Fallo%' AND c.anio <= 2024
          AND NOT EXISTS (
            SELECT 1 FROM proyecto_integrante pi WHERE pi.proyecto_id = p.id
          )
    """).fetchall()
    by_url = {}
    for r in rows:
        by_url.setdefault(r["url_pdf"], []).append(dict(r))
    return by_url

def get_layout_text(url):
    pdf_name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('/')[-1])[:80]
    pdf_path = os.path.join(TMP_DIR, pdf_name)
    txt_path = pdf_path + "_layout.txt"
    if not os.path.exists(pdf_path):
        subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url],
                      capture_output=True, timeout=45)
    if not os.path.exists(txt_path):
        subprocess.run(['pdftotext', '-layout', pdf_path, txt_path], capture_output=True, timeout=30)
    with open(txt_path) as f:
        text = unicodedata.normalize('NFC', f.read())
    return text

def find_director_in_lines(block_lines):
    """Find director/responsable name in a block of text lines without column slicing."""
    full_text = ' '.join(block_lines)
    
    # Remove known non-director content
    text = re.sub(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', ' ', full_text)  # montos
    
    # Look for patterns: "LASTNAME, FIRSTNAME" or "/" separated list
    # Directors typically contain a comma separating surname from given name
    comma_patterns = re.findall(r'([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]+(?:[,]\s*[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+))', text)
    
    for match in comma_patterns:
        match = match.strip().strip(',').strip()
        # Validate: should have letters, a comma, and at least 4 total chars
        if ',' in match and len(match) >= 6:
            parts = match.split(',')
            if len(parts[0].split()) >= 1 and len(parts[1].split()) >= 1:
                return match
    
    # No comma found - try to find uppercase name sequences (2+ words) that look like directors
    # This handles "HUARACALLO APAZA ZULMA YASMÍN" style
    # Filter out obra titles and regions
    regiones = {'LIMA', 'PUNO', 'CALLAO', 'SAN MARTIN', 'LORETO', 'CUSCO', 'AREQUIPA', 
                'LA LIBERTAD', 'JUNIN', 'ANCASH', 'CAJAMARCA', 'HUANUCO', 'PIURA',
                'LAMBAYEQUE', 'ICA', 'AYACUCHO', 'HUANCAVELICA', 'APURIMAC', 'PASCO',
                'TACNA', 'TUMBES', 'MADRE DE DIOS', 'AMAZONAS', 'MOQUEGUA', 'UCAYALI',
                'LIMA METROPOLITANA'}
    
    # Try to find name sequences that don't match obra/region patterns
    all_caps_seqs = re.findall(r'([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+[A-ZÁÉÍÓÚÑ])', text)
    for seq in all_caps_seqs:
        seq = seq.strip()
        words = seq.split()
        if len(words) < 3:
            continue
        if words[0] in regiones or words[-1] in {'E.I.R.L.', 'S.A.C.', 'S.A.', 'EIRL', 'SAC'}:
            continue
        # Check it's not an obra title (obra titles often have special chars)
        if seq.startswith(('WIPHAY', 'SERPENTINA', 'MOCHILA', 'DUNA', 'CARTA', 'FESTIVAL')):
            continue
        return seq
    
    return None

def parse_director_from_a1(a1_text):
    """
    Parse director/responsable names from Artículo Primero text.
    Uses line-by-line analysis to extract empresa→director pairs.
    Each entry: empresa line(s) → obra line(s) → director line(s) → monto
    """
    lines = a1_text.split('\n')
    
    # Detect director keyword from header (RESPONSABLE or DIRECTOR)
    # and its approximate column position
    dir_key = None
    dir_pos = 90  # default
    for line in lines[:30]:
        m = re.search(r'(RESPONSABLE|DIRECTOR)', line)
        if m:
            dir_key = m.group(1)
            dir_pos = m.start()
            break
    
    # Detect empresa column end
    emp_end = 45  # default
    for line in lines[:30]:
        m = re.search(r'JUR[IÍ]DICA', line)
        if m:
            emp_end = m.start()
            break
    
    # Split lines into entries
    entries_raw = []
    current_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(kw in stripped for kw in ['Artículo Segundo', 'ARTÍCULO SEGUNDO',
                                          'copia auténtica', 'Regístrese']):
            if current_lines:
                entries_raw.append(current_lines)
            break
        
        # Check if line starts a new entry (has empresa text in left column)
        emp_text = line[:emp_end].strip() if len(line) > emp_end else ''
        is_new = (len(emp_text) >= 3 and not re.match(r'^[\d\s(]+$', emp_text)
                  and not any(kw in line for kw in FALLO_HEADER_KEYWORDS))
        
        if is_new and current_lines:
            entries_raw.append(current_lines)
            current_lines = [line]
        else:
            current_lines.append(line)
    
    if current_lines:
        entries_raw.append(current_lines)
    
    # Extract data from each entry
    entries = []
    for block in entries_raw:
        empresa = ''
        obra = ''
        director = ''
        monto = ''
        
        for line in block:
            emp_text = line[:emp_end].strip() if len(line) > emp_end else ''
            if emp_text and len(emp_text) >= 3:
                empresa = (empresa + ' ' + emp_text).strip()
            
            # Look for monto
            mm = re.search(r'S/?\.?\s*([\d\s,]+[.,]\d{2})', line)
            if mm:
                monto = mm.group()
        
        # Extract director using text from the right portion of lines
        if dir_key and dir_pos:
            dir_texts = []
            for line in block:
                if len(line) > dir_pos - 5:
                    col_text = line[dir_pos - 5:].strip()
                    # Filter out header keywords and monto
                    if any(kw in col_text for kw in FALLO_HEADER_KEYWORDS):
                        continue
                    if re.match(r'^S/?\.?\s*[\d]', col_text):
                        continue
                    col_text = re.sub(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', '', col_text).strip()
                    if col_text and len(col_text) > 3:
                        dir_texts.append(col_text)
            
            if dir_texts:
                director = ' '.join(dir_texts)
                # Remove known non-director content
                director = re.sub(r'\s+', ' ', director).strip()
                director = re.sub(r'\b(REGIÓN|PROYECTO|OTORGADO|RESPONSABLE)\b.*', '', director).strip()
        
        # Clean
        empresa = re.sub(r'\s+', ' ', empresa).strip()
        obra = re.sub(r'\s+', ' ', obra).strip()
        
        if empresa and director:
            entries.append({
                'empresa': empresa,
                'director': director,
                'monto': monto,
                '_lines': block
            })
    
    return entries

def normalize(s):
    s = (s or '').upper()
    s = re.sub(r'[^A-ZÁÉÍÓÚÑ0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def score_match(e, dp):
    emp = normalize(e.get('empresa', ''))
    raz = normalize(dp['razon_social'])
    ew = set(emp.split())
    rw = set(raz.split())
    score = len(ew & rw) * 2
    
    obra_entry = normalize(e.get('obra', ''))
    obra_db = normalize(dp['titulo'])
    if obra_entry and obra_db:
        score += len(set(obra_entry.split()) & set(obra_db.split())) * 2
    
    return score

def clean_director(text):
    """Clean director name text."""
    # Remove monto values
    text = re.sub(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', '', text)
    # Remove RUC
    text = re.sub(r'\(\d{11}\)', '', text)
    # Remove header leftovers
    text = re.sub(r'(RESPONSABLE|DIRECTOR)\s*\(\s*S?\s*\)?\s*(DEL\s*PROYECTO)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove trailing/leading junk
    text = re.sub(r'^[^A-Za-z]+', '', text)
    text = text.strip().rstrip(',').strip()
    return text

def split_entries(dir_text):
    """Split multiple responsables (separated by /) and clean each."""
    dir_text = clean_director(dir_text)
    parts = re.split(r'\s*/\s*', dir_text)
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Check if looks like a name: has letters, not just numbers, not too short
        if re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}', p) and len(p) >= 5:
            result.append(p)
    return result

def parse_name(name_text):
    """Parse 'APELLIDOS, NOMBRES' or 'NOMBRES APELLIDOS'."""
    if ',' in name_text:
        ap, nom = name_text.split(',', 1)
        return nom.strip().title(), ap.strip().title()
    words = name_text.split()
    if len(words) >= 4:
        return ' '.join(words[:-2]).title(), ' '.join(words[-2:]).title()
    elif len(words) == 3:
        return words[0].title(), ' '.join(words[1:]).title()
    elif len(words) == 2:
        return words[0].title(), words[1].title()
    return name_text.title(), ''

def main():
    urls = get_fallo_urls()
    proj_by_url = get_projects_by_url()
    
    print(f"FalloFinal PDFs (<=2024): {len(urls)}")
    print(f"Projects to fix: {sum(len(v) for v in proj_by_url.values())}\n")
    
    total_fixed = 0
    total_skipped = 0
    
    for i, url in enumerate(urls):
        fname = url.split('/')[-1][:50]
        print(f"[{i+1}/{len(urls)}] {fname}")
        
        text = get_layout_text(url)
        
        # Extract Artículo Primero
        a1_match = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO|Artículo\s)', text, re.DOTALL)
        if not a1_match:
            a1_match = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|ART[ÍI]CULO SEGUNDO|Artículo\s|ART[ÍI]CULO\s)', text, re.DOTALL)
        if not a1_match:
            print(f"  SKIP: no ARTÍCULO PRIMERO")
            continue
        
        a1 = a1_match.group(1)
        
        # Try extractor parser first
        try:
            entries = parse_fallo_beneficiaries(a1)
        except Exception:
            entries = []
        
        if entries:
            # Use extractor's output
            parsed = []
            for e in entries:
                empresa = e.get('empresa', '')
                director = e.get('responsable', e.get('director', ''))
                if empresa and director:
                    parsed.append({'empresa': empresa, 'director': director, 'obra': e.get('proyecto', '')})
        else:
            # Fallback to custom line-based parsing
            parsed = parse_director_from_a1(a1)
            if not parsed:
                print(f"  No entries found")
                continue
        
        db_projs = proj_by_url.get(url, [])
        if not db_projs:
            print(f"  No DB projects for this URL")
            continue
        
        print(f"  Entries: {len(parsed)}, DB projects: {len(db_projs)}")
        
        for dp in db_projs:
            best = None
            best_score = 0
            for e in parsed:
                s = score_match(e, dp)
                if s > best_score:
                    best_score = s
                    best = e
            
            if best and best_score >= 4:
                dir_text = best.get('director', '')
                dir_names = split_entries(dir_text)
                
                valid = []
                for n in dir_names:
                    nom, ape = parse_name(n)
                    if nom and len(nom) >= 2 and (ape or len(nom.split()) >= 2):
                        valid.append((nom, ape))
                
                if not valid:
                    print(f"  ✗ proj={dp['id']}: '{dir_text[:40]}' no válido (score={best_score})")
                    total_skipped += 1
                    continue
                
                if DRY_RUN:
                    names = "; ".join(f"{n} {a}" for n, a in valid)
                    print(f"  ✓ proj={dp['id']}: {dp['razon_social'][:25]} → {names} (score={best_score})")
                    continue
                
                for nom, ape in valid:
                    existing = db.execute("""
                        SELECT id FROM persona WHERE tipo='natural' AND nombres=? AND apellidos=?
                    """, (nom, ape)).fetchone()
                    if existing:
                        pid = existing['id']
                    else:
                        db.execute("INSERT INTO persona (tipo, nombres, apellidos, dni) VALUES ('natural', ?, ?, '')", (nom, ape))
                        pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                    
                    exists = db.execute("""SELECT id FROM proyecto_integrante WHERE proyecto_id=? AND persona_id=? AND rol='responsable'""", (dp['id'], pid)).fetchone()
                    if not exists:
                        db.execute("INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, 'responsable')", (dp['id'], pid))
                        print(f"    + integrante: proj={dp['id']}, {nom} {ape}")
                        total_fixed += 1
            else:
                print(f"  ✗ proj={dp['id']}: no match (score={best_score})")
                total_skipped += 1
    
    if not DRY_RUN:
        db.commit()
    
    print(f"\n{'='*50}")
    print(f"Insertados: {total_fixed} | Skipped: {total_skipped}")
    if DRY_RUN:
        print("🔶 DRY RUN — pasa --run para aplicar")

if __name__ == '__main__':
    main()
