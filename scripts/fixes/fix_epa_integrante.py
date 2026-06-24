"""
Extraer responsables de EPA 2021 RDs individuales.
Cada RD tiene UN beneficiario con columna RESPONSABLE en formato bloque.
Uso: python3 fix_epa_integrante.py [--run]
"""
import os, re, sqlite3, subprocess, sys, unicodedata

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
TMP_DIR = "/tmp/dafo_pdfs"
DRY_RUN = '--run' not in sys.argv
os.makedirs(TMP_DIR, exist_ok=True)

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

def get_layout_text(url):
    pdf_name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('/')[-1])[:80] + ".pdf"
    pdf_path = os.path.join(TMP_DIR, pdf_name)
    txt_path = pdf_path.replace('.pdf', '_layout.txt')
    if not os.path.exists(pdf_path):
        r = subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url], capture_output=True, timeout=45)
        if r.returncode != 0:
            return None
    if not os.path.exists(txt_path):
        r = subprocess.run(['pdftotext', '-layout', pdf_path, txt_path], capture_output=True, timeout=30)
        if r.returncode != 0:
            return None
    with open(txt_path, encoding='utf-8') as f:
        return unicodedata.normalize('NFC', f.read())

def extract_article_1(text):
    m = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO|Artículo\s(?!Primero))', text, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|ART[ÍI]CULO SEGUNDO)', text, re.DOTALL)
    return m.group(1) if m else text

def find_responsable_in_block(block_text):
    """Find the RESPONSABLE column text from the article 1 block."""
    lines = block_text.split('\n')
    
    # Find the "RESPONSABLE" header position
    resp_pos = None
    monto_pos = None
    for line in lines:
        m = re.search(r'RESPONSABLE', line)
        if m:
            resp_pos = m.start()
        m = re.search(r'MONTO', line)
        if m:
            monto_pos = m.start()
            break
    
    if resp_pos is None:
        resp_pos = 80
    if monto_pos is None:
        monto_pos = 120
    
    # Collect text from RESPONSABLE column for non-header, non-blank lines
    resp_texts = []
    for line in lines:
        s = line.strip()
        if not s or any(kw in s for kw in ['PERSONA', 'JURÍDICA', 'REGIÓN', 'TÍTULO', 'RESPONSABLE', 'MONTO', 'ESTÍMULO']):
            continue
        if re.match(r'^Artículo|^SE RESUELVE', s):
            continue
        if len(line) > resp_pos:
            col = line[resp_pos:monto_pos].strip()
            col = re.sub(r'S/?\.?\s*[\d\s]+[.,]\d{2}', '', col).strip()
            if col and len(col) >= 3:
                resp_texts.append(col)
    
    # Join and clean
    if not resp_texts:
        return ''
    
    full = ' '.join(resp_texts)
    full = re.sub(r'\s+', ' ', full).strip()
    full = re.sub(r'^[^A-Za-zÁÉÍÓÚÑáéíóúñ]+', '', full)
    full = full.rstrip('/').strip()
    return full

def split_names(text):
    """Split 'NAME1 / NAME2' into individual names."""
    if not text or len(text) < 5:
        return []
    parts = re.split(r'\s*/\s*', text)
    results = []
    for p in parts:
        p = p.strip().strip(',').strip()
        if not p or len(p) < 5:
            continue
        if not re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}', p):
            continue
        results.append(p)
    return results

def parse_name(name_text):
    """Parse 'APELLIDOS, NOMBRES' or 'NOMBRES APELLIDOS'."""
    name_text = name_text.strip()
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

def get_person_id(nom, ape):
    cur = db.execute("SELECT id FROM persona WHERE tipo='natural' AND nombres=? AND apellidos=?", (nom, ape))
    r = cur.fetchone()
    if r:
        return r['id']
    db.execute("INSERT INTO persona (tipo, nombres, apellidos) VALUES ('natural', ?, ?)", (nom, ape))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]

def main():
    print("EPA 2021 — Extracción de responsables de RDs individuales")
    print(f"{'DRY RUN' if DRY_RUN else 'APLICANDO'}\n")
    
    rows = db.execute("""
        SELECT p.id, c.anio, per.razon_social, o.titulo, r.url_pdf
        FROM proyecto p
        JOIN persona per ON per.id = p.persona_beneficiaria_id AND per.tipo = 'juridica'
        LEFT JOIN proyecto_integrante pi ON pi.proyecto_id = p.id AND pi.rol IN ('responsable', 'director')
        JOIN concurso_anual ca ON ca.id = p.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        JOIN proyecto_resolucion pr ON pr.proyecto_id = p.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        LEFT JOIN obra o ON o.id = p.obra_id
        WHERE pi.id IS NULL AND lc.codigo = 'EPA'
        ORDER BY c.anio, p.id
    """).fetchall()
    
    total_fixed = 0
    total_failed = 0
    
    for r in rows:
        proj_id = r['id']
        url = r['url_pdf']
        empresa = r['razon_social']
        
        print(f"\nP{proj_id} ({r['anio']}): {empresa[:40]}")
        if r['titulo']:
            print(f"  Obra: {r['titulo'][:60]}")
        
        text = get_layout_text(url)
        if text is None:
            print(f"  ERROR: no se pudo descargar PDF")
            total_failed += 1
            continue
        
        a1 = extract_article_1(text)
        resp_text = find_responsable_in_block(a1)
        
        if not resp_text:
            print(f"  No se encontró responsable en el PDF")
            # Try to find in full text
            dn_match = re.search(r'\(DNI[^)]*\)', text)
            if dn_match:
                print(f"  Pero se encontró (DNI...) — buscar nombre alrededor")
                # Try to find name before DNI
                idx = dn_match.start()
                prev_text = text[max(0,idx-80):idx]
                lines = prev_text.split('\n')
                names = [l.strip() for l in lines if l.strip() and len(l.strip())>5
                        and not re.search(r'^(S/|Artículo|RESOLUCIÓN|San Borja)', l.strip())]
                if names:
                    resp_text = names[-1]
                    print(f"  Nombre extraído de contexto: {resp_text[:60]}")
                else:
                    print(f"  No se pudo extraer nombre del contexto")
                    total_failed += 1
                    continue
            else:
                total_failed += 1
                continue
        
        names = split_names(resp_text)
        if not names:
            print(f"  Responsable '{resp_text[:60]}' — no se pudo parsear nombre válido")
            total_failed += 1
            continue
        
        valid = []
        for n in names:
            nom, ape = parse_name(n)
            if nom and len(nom) >= 2 and (ape or len(nom.split()) >= 2):
                valid.append((nom, ape))
        
        if not valid:
            print(f"  Nombres parseados no válidos: {names}")
            total_failed += 1
            continue
        
        names_str = "; ".join(f"{n} {a}" for n, a in valid)
        print(f"  → {names_str}")
        
        if DRY_RUN:
            total_fixed += 1
        else:
            for nom, ape in valid:
                pid = get_person_id(nom, ape)
                exists = db.execute(
                    "SELECT 1 FROM proyecto_integrante WHERE proyecto_id=? AND persona_id=? AND rol='responsable'",
                    (proj_id, pid)
                ).fetchone()
                if not exists:
                    db.execute(
                        "INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, 'responsable')",
                        (proj_id, pid)
                    )
                    print(f"    +integrante: {nom} {ape}")
                    total_fixed += 1
    
    if not DRY_RUN:
        db.commit()
    
    print(f"\n{'='*40}")
    print(f"Fijados: {total_fixed} | Fallaron: {total_failed}")
    if DRY_RUN:
        print(f"DRY RUN — pasa --run para aplicar")
    db.close()

if __name__ == '__main__':
    main()
