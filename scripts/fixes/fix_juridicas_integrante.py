"""
Re-extraer responsables de FalloFinal PDFs + EPA RDs para juridicas sin integrante.
Uso: python3 fix_juridicas_integrante.py [--run]
"""
import os, re, sqlite3, subprocess, sys, unicodedata, json
sys.path.insert(0, "/home/efrain/Projects/Analisis_Concursos_DAFO")
from dafo_common import DB_PATH, TMP_DIR, REGIONS, FALLO_HEADER_KEYWORDS, split_name, q
from extract_2024 import parse_fallo_beneficiaries, detect_table_columns

DRY_RUN = "--run" not in sys.argv
os.makedirs(TMP_DIR, exist_ok=True)

db = sqlite3.connect(DB_PATH)
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

def norm(s):
    s = (s or '').upper()
    s = re.sub(r'[^A-ZÁÉÍÓÚÑ0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def score_empresa(pdf_empresa, db_razon):
    pe = norm(pdf_empresa)
    dr = norm(db_razon)
    if not pe or not dr:
        return 0
    if pe == dr:
        return 100
    if pe in dr or dr in pe:
        return 80
    pw = set(pe.split())
    dw = set(dr.split())
    common = pw & dw
    if len(common) >= 2:
        return int(60 * len(common) / max(len(pw), len(dw), 1))
    return 0

def score_obra(pdf_obra, db_obra):
    if not pdf_obra or not db_obra:
        return 0
    po = norm(pdf_obra)
    do = norm(db_obra)
    if po == do:
        return 100
    if po in do or do in po:
        return 70
    pw = set(po.split())
    dw = set(do.split())
    common = pw & dw
    if len(common) >= 2:
        return int(50 * len(common) / max(len(pw), len(dw), 1))
    return 0

def clean_director(text):
    text = re.sub(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', '', text)
    text = re.sub(r'S/?\.?\s*[\d\s]+', '', text)
    text = re.sub(r'\(\d{11}\)', '', text)
    text = re.sub(r'(RESPONSABLE|DIRECTOR)\s*\(\s*S?\s*\)?\s*(DEL\s*PROYECTO)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[.,]\d{2}', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'^[^A-Za-zÁÉÍÓÚÑáéíóúñ]+', '', text)
    text = text.strip().rstrip(',').strip()
    # If after cleaning, text is just numbers or too short, reject
    if re.match(r'^[\d\s,.]*$', text) or len(text) < 3:
        return ''
    return text

def parse_responsable_names(text):
    text = clean_director(text)
    if not text or len(text) < 5:
        return []
    parts = re.split(r'\s*/\s*', text)
    results = []
    for p in parts:
        p = p.strip()
        if not p or len(p) < 5:
            continue
        if not re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}', p):
            continue
        # Reject if mostly numbers after cleaning
        alpha_count = sum(1 for c in p if c.isalpha())
        if alpha_count < 3:
            continue
        results.append(p)
    return results

def get_person_id(nom, ape):
    cur = db.execute("SELECT id FROM persona WHERE tipo='natural' AND nombres=? AND apellidos=?", (nom, ape))
    r = cur.fetchone()
    if r:
        return r['id']
    db.execute("INSERT INTO persona (tipo, nombres, apellidos) VALUES ('natural', ?, ?)", (nom, ape))
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]

def get_projects_by_url_fallo():
    """Returns {url: [{id, razon_social, titulo}]} for juridicas sin integrante with FalloFinal PDF"""
    rows = db.execute("""
        SELECT r.url_pdf, p.id, pe.razon_social, ob.titulo AS obra_titulo, lc.codigo, c.anio
        FROM proyecto p
        JOIN persona pe ON p.persona_beneficiaria_id = pe.id AND pe.tipo = 'juridica'
        LEFT JOIN proyecto_integrante pi ON pi.proyecto_id = p.id AND pi.rol IN ('responsable', 'director')
        JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
        JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
        JOIN convocatoria c ON ca.convocatoria_id = c.id
        JOIN proyecto_resolucion pr ON p.id = pr.proyecto_id
        JOIN resolucion r ON pr.resolucion_id = r.id
        LEFT JOIN obra ob ON ob.id = p.obra_id
        WHERE pi.id IS NULL AND r.tipo = 'fallo_final'
          AND r.url_pdf IS NOT NULL
        ORDER BY r.url_pdf, p.id
    """).fetchall()
    by_url = {}
    for r in rows:
        by_url.setdefault(r['url_pdf'], []).append(dict(r))
    return by_url

def get_projects_by_url_epa():
    """Returns {url: [{id, razon_social, titulo}]} for juridicas EPA sin integrante (individual RDs)"""
    rows = db.execute("""
        SELECT r.url_pdf, p.id, pe.razon_social, ob.titulo AS obra_titulo, lc.codigo, c.anio
        FROM proyecto p
        JOIN persona pe ON p.persona_beneficiaria_id = pe.id AND pe.tipo = 'juridica'
        LEFT JOIN proyecto_integrante pi ON pi.proyecto_id = p.id AND pi.rol IN ('responsable', 'director')
        JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
        JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
        JOIN convocatoria c ON ca.convocatoria_id = c.id
        JOIN proyecto_resolucion pr ON p.id = pr.proyecto_id
        JOIN resolucion r ON pr.resolucion_id = r.id
        LEFT JOIN obra ob ON ob.id = p.obra_id
        WHERE pi.id IS NULL AND lc.codigo = 'EPA'
          AND r.url_pdf IS NOT NULL
        ORDER BY r.url_pdf, p.id
    """).fetchall()
    by_url = {}
    for r in rows:
        by_url.setdefault(r['url_pdf'], []).append(dict(r))
    return by_url

def extract_a1_section(text):
    m = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO|Artículo\s(?!Primero))', text, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|ART[ÍI]CULO SEGUNDO)', text, re.DOTALL)
    if m:
        return m.group(1)
    return text

def fallback_parse_director_from_a1(a1_text, dir_keyword='RESPONSABLE'):
    """Fallback: try to find director/responsable names by scanning empresa blocks.
    Returns [(empresa_text, director_text), ...]"""
    lines = a1_text.split('\n')
    lines = [l.rstrip() for l in lines if l.strip()]

    dir_pos = 90
    for line in lines[:30]:
        m = re.search(r'(RESPONSABLE|DIRECTOR)', line)
        if m:
            dir_keyword = m.group(1)
            dir_pos = m.start()
            break

    emp_end = 45
    for line in lines[:30]:
        m = re.search(r'JUR[IÍ]DICA', line)
        if m:
            emp_end = m.start()
            break

    entries = []
    current_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(kw in stripped for kw in ['Artículo Segundo', 'ARTÍCULO SEGUNDO', 'copia auténtica', 'Regístrese']):
            if current_lines:
                entries.append(current_lines)
            break
        emp_text = line[:emp_end].strip() if len(line) > emp_end else ''
        is_new = (len(emp_text) >= 3 and not re.match(r'^[\d\s(]+$', emp_text)
                  and not any(kw in line for kw in FALLO_HEADER_KEYWORDS))
        if is_new and current_lines:
            entries.append(current_lines)
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_lines:
        entries.append(current_lines)

    result = []
    for block in entries:
        empresa = ''
        for line in block:
            emp_text = line[:emp_end].strip() if len(line) > emp_end else ''
            if emp_text and len(emp_text) >= 3:
                empresa = (empresa + ' ' + emp_text).strip()
        empresa = re.sub(r'\s+', ' ', empresa).strip()

        dir_texts = []
        for line in block:
            if len(line) > dir_pos - 5:
                col_text = line[dir_pos - 5:].strip()
                if any(kw in col_text for kw in FALLO_HEADER_KEYWORDS):
                    continue
                if re.match(r'^S/?\.?\s*[\d]', col_text):
                    continue
                col_text = re.sub(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', '', col_text).strip()
                if col_text and len(col_text) > 3:
                    dir_texts.append(col_text)
        director = ' '.join(dir_texts) if dir_texts else ''
        director = re.sub(r'\s+', ' ', director).strip()
        director = re.sub(r'\b(REGIÓN|REGION|PROYECTO|OTORGADO|RESPONSABLE|DIRECTOR)\b.*', '', director).strip()

        if empresa and director:
            result.append({'empresa': empresa, 'director': director})
    return result

def process_fallo_pdf(url, db_projs):
    fname = url.split('/')[-1][:50]
    print(f"\n{'='*60}")
    print(f"PDF: {fname}")
    print(f"DB projects: {len(db_projs)}")

    text = get_layout_text(url)
    if text is None:
        print(f"  ERROR: no se pudo descargar/convertir PDF")
        return 0, len(db_projs)

    a1 = extract_a1_section(text)

    entries = []
    try:
        parsed = parse_fallo_beneficiaries(a1)
        if parsed:
            for e in parsed:
                empresa = e.get('empresa', '')
                director = e.get('responsable', e.get('director', ''))
                obra = e.get('proyecto', '')
                if empresa and director:
                    entries.append({'empresa': empresa, 'director': director, 'obra': obra})
    except Exception:
        pass

    if not entries:
        entries = fallback_parse_director_from_a1(a1)

    if not entries:
        print(f"  No se pudo extraer entries del PDF")
        return 0, len(db_projs)

    print(f"  Entries extraídos: {len(entries)}")

    fixed = 0
    skipped = 0
    for dp in db_projs:
        best = None
        best_score = 0
        for e in entries:
            s = score_empresa(e.get('empresa', ''), dp['razon_social'])
            if dp.get('titulo'):
                s += score_obra(e.get('obra', ''), dp.get('obra_titulo', ''))
            if s > best_score:
                best_score = s
                best = e

        if best and best_score >= 30:
            dir_text = best.get('director', '')
            names = parse_responsable_names(dir_text)
            valid = []
            for n in names:
                nom, ape = split_name(n)
                if nom and len(nom) >= 2 and (ape or len(nom.split()) >= 2):
                    valid.append((nom, ape))
            if not valid:
                print(f"  ✗ P{dp['id']:>6}: '{dir_text[:50]}' (score={best_score}) — nombre no válido")
                skipped += 1
                continue
            if DRY_RUN:
                names_str = "; ".join(f"{n} {a}" for n, a in valid)
                print(f"  ✓ P{dp['id']:>6}: {dp['razon_social'][:30]} → {names_str} (score={best_score})")
                fixed += 1
            else:
                for nom, ape in valid:
                    pid = get_person_id(nom, ape)
                    exists = db.execute(
                        "SELECT 1 FROM proyecto_integrante WHERE proyecto_id=? AND persona_id=? AND rol='responsable'",
                        (dp['id'], pid)
                    ).fetchone()
                    if not exists:
                        db.execute(
                            "INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, 'responsable')",
                            (dp['id'], pid)
                        )
                        print(f"  ✓ P{dp['id']:>6}: +integrante {nom} {ape} (score={best_score})")
                        fixed += 1
        else:
            empresa_text = best['empresa'][:40] if best else '(sin match)'
            print(f"  ✗ P{dp['id']:>6}: {dp['razon_social'][:30]} — no match (score={best_score}, empresa='{empresa_text}')")
            skipped += 1

    return fixed, skipped

def process_epa_rd(url, db_projs):
    """Process EPA individual RDs — extract responsable from article 1 text"""
    fname = url.split('/')[-1][:50]
    print(f"\n{'='*60}")
    print(f"EPA RD: {fname}")
    print(f"DB projects: {len(db_projs)}")

    text = get_layout_text(url)
    if text is None:
        print(f"  ERROR: no se pudo descargar/convertir PDF")
        return 0, len(db_projs)

    a1 = extract_a1_section(text)
    if not a1:
        print(f"  No ARTÍCULO PRIMERO found")
        return 0, len(db_projs)

    lines = a1.split('\n')
    lines = [l.rstrip() for l in lines if l.strip()]

    dir_pos = 90
    for line in lines[:20]:
        m = re.search(r'(RESPONSABLE|DIRECTOR)', line)
        if m:
            dir_pos = m.start()
            break

    entries = []
    current_empresa = ''
    current_director = ''
    for line in lines:
        s = line.strip()
        if not s or any(kw in s for kw in FALLO_HEADER_KEYWORDS):
            continue
        if re.match(r'^S/?\.?\s*[\d]', s):
            if current_empresa and current_director:
                entries.append({'empresa': current_empresa, 'director': current_director})
            current_empresa = ''
            current_director = ''
            continue
        if len(line) > dir_pos - 5:
            emp_part = line[:dir_pos - 5].strip()
            dir_part = line[dir_pos - 5:].strip()
            dir_part = re.sub(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', '', dir_part).strip()
            if emp_part and len(emp_part) >= 3:
                current_empresa = emp_part
                if dir_part and len(dir_part) >= 5:
                    current_director = dir_part

    if current_empresa and current_director:
        entries.append({'empresa': current_empresa, 'director': current_director})

    if not entries:
        print(f"  No entries extraídos del RD")
        return 0, len(db_projs)

    print(f"  Entries extraídos: {len(entries)}")

    fixed = 0
    skipped = 0
    for dp in db_projs:
        best = None
        best_score = 0
        for e in entries:
            s = score_empresa(e.get('empresa', ''), dp['razon_social'])
            if s > best_score:
                best_score = s
                best = e
        if best and best_score >= 30:
            dir_text = best.get('director', '')
            names = parse_responsable_names(dir_text)
            valid = []
            for n in names:
                nom, ape = split_name(n)
                if nom and len(nom) >= 2 and (ape or len(nom.split()) >= 2):
                    valid.append((nom, ape))
            if not valid:
                print(f"  ✗ P{dp['id']:>6}: '{dir_text[:50]}' (score={best_score}) — nombre no válido")
                skipped += 1
                continue
            if DRY_RUN:
                names_str = "; ".join(f"{n} {a}" for n, a in valid)
                print(f"  ✓ P{dp['id']:>6}: {dp['razon_social'][:30]} → {names_str} (score={best_score})")
                fixed += 1
            else:
                for nom, ape in valid:
                    pid = get_person_id(nom, ape)
                    exists = db.execute(
                        "SELECT 1 FROM proyecto_integrante WHERE proyecto_id=? AND persona_id=? AND rol='responsable'",
                        (dp['id'], pid)
                    ).fetchone()
                    if not exists:
                        db.execute(
                            "INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, 'responsable')",
                            (dp['id'], pid)
                        )
                        print(f"  ✓ P{dp['id']:>6}: +integrante {nom} {ape} (score={best_score})")
                        fixed += 1
        else:
            print(f"  ✗ P{dp['id']:>6}: {dp['razon_social'][:30]} — no match (score={best_score})")
            skipped += 1

    return fixed, skipped

def main():
    print(f"{'='*60}")
    print(f"JURÍDICAS SIN INTEGRANTE — Re-extracción")
    print(f"{'DRY RUN' if DRY_RUN else 'APLICANDO CAMBIOS'}")
    print(f"{'='*60}")

    total_fixed = 0
    total_skipped = 0

    # Phase 1: FalloFinal PDFs
    print(f"\n{'#'*60}")
    print(f"# FASE 1: FALLO FINAL PDFs")
    print(f"{'#'*60}")
    proj_by_url = get_projects_by_url_fallo()
    print(f"\nFalloFinal PDFs únicos: {len(proj_by_url)}")
    print(f"Proyectos a procesar: {sum(len(v) for v in proj_by_url.values())}")

    for url, db_projs in sorted(proj_by_url.items()):
        f, s = process_fallo_pdf(url, db_projs)
        total_fixed += f
        total_skipped += s

    # Phase 2: EPA individual RDs
    print(f"\n{'#'*60}")
    print(f"# FASE 2: EPA RDs INDIVIDUALES")
    print(f"{'#'*60}")
    epa_by_url = get_projects_by_url_epa()
    print(f"\nEPA RDs únicos: {len(epa_by_url)}")
    print(f"Proyectos EPA a procesar: {sum(len(v) for v in epa_by_url.values())}")

    for url, db_projs in sorted(epa_by_url.items()):
        f, s = process_epa_rd(url, db_projs)
        total_fixed += f
        total_skipped += s

    if not DRY_RUN:
        db.commit()

    print(f"\n{'='*60}")
    print(f"RESUMEN")
    print(f"  Fijados:   {total_fixed}")
    print(f"  Saltados:  {total_skipped}")
    if DRY_RUN:
        print(f"  🔶 DRY RUN — pasa --run para aplicar")
    else:
        print(f"  ✅ Cambios aplicados a la DB")
    print(f"{'='*60}")
    db.close()

if __name__ == '__main__':
    main()
