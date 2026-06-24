#!/usr/bin/env python3
"""
Corregir títulos de obra irrecuperables vía re-extracción PDF.

Estrategia: para cada obra con título corrupto:
1. Descargar PDF
2. Extraer layout text
3. Encontrar la tabla de beneficiarios
4. Para cada línea de datos, extraer texto de las columnas 'proyecto' y 'empresa'
5. Hacer matching por persona_beneficiaria (nombre en columna empresa)
6. Extraer título de columna proyecto

Solo procesa obras con URL de resolución.
Uso: python3 reextract_titles.py --run
"""
import sqlite3, sys, os, re, subprocess, urllib.parse, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH, TMP_DIR

RUN = "--run" in sys.argv

SHORT_WORDS = {'A','E','Y','O','LA','EL','LO','AL','DEL','EN','UN','SU',
               'DE','SE','NO','MI','TU','SUS','LOS','LAS','CON','POR',
               'QUE','FUE','ES','YA','HA','HI','VA','VE','DA','LE','ME',
               'TE','SI','NI','3D','2D','II','IV','VI','V','X','8M','S/.'}

def is_garbled(t):
    if not t: return True
    t = t.strip()
    if len(t) < 5: return True
    if re.search(r'S/[\s\d,]+', t): return True
    if re.search(r'(DNI|RUC)\s*N?°?\s*\d', t): return True
    if re.search(r'  {3,}', t): return True
    words = re.split(r'[\s,]+', t)
    short_bad = [w for w in words if len(w) <= 2 and w.upper() not in SHORT_WORDS]
    if len(words) >= 3 and len(short_bad) / len(words) > 0.5: return True
    return False

def looks_like_title(t):
    if not t: return False
    t = t.strip().rstrip(',;:')
    if len(t) < 4: return False
    if re.match(r'^\d+$', t): return False
    if re.match(r'^[A-ZÁÉÍÓÚÑÜ ]+,[ \t]*[A-ZÁÉÍÓÚÑÜ ]+', t): return False
    words = t.split()
    if len(words) >= 3:
        single = sum(1 for w in words if len(w) <= 1 and w.isalpha())
        if single > len(words) * 0.3: return False
    if not any(len(w) > 3 for w in words): return False
    # Reject if it looks like a person name (2-4 all-caps words, no accent)
    if 2 <= len(words) <= 4 and all(re.match(r'^[A-ZÁÉÍÓÚÑÜ]+$', w) for w in words):
        # Check if these are known person name patterns
        if len(words[0]) >= 4 and words[0][0].isupper() and not any(ord(c) > 127 for c in words[0]):
            # All uppercase Latin-only names are likely person names, not titles
            return False
    return True

def download_pdf(url):
    fname = urllib.parse.unquote(url.split('/')[-1])
    key = 'tfix_' + re.sub(r'[^a-zA-Z0-9]', '_', fname)[:70]
    pdf_path = os.path.join(TMP_DIR, key)
    txt_path = pdf_path + "_layout.txt"
    if not os.path.exists(txt_path):
        if not os.path.exists(pdf_path):
            try:
                subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url],
                             check=True, timeout=45, capture_output=True)
            except Exception as e:
                return None
        try:
            subprocess.run(['pdftotext', '-layout', pdf_path, txt_path],
                         check=True, timeout=30, capture_output=True)
        except:
            return None
    with open(txt_path) as f:
        text = f.read()
    return unicodedata.normalize('NFC', text)

def find_header_positions(lines):
    """Find keyword positions in header area."""
    keywords = ['PERSONA', 'JURÍDICA', 'NATURAL', 'REGIÓN', 'REGION',
                'TÍTULO', 'TITULO', 'DIRECTOR', 'MONTO', 'PROYECTO',
                'RESPONSABLE', 'INSTITUCIÓN', 'INSTITUCION', 'PROGRAMA',
                'EVENTO', 'OBRA', 'VINCULADA', 'ESTÍMULO', 'ESTIMULO',
                'FORMACIÓN', 'FORMACION', 'BENEFICIARIO', 'CÓDIGO', 'CODIGO',
                '(RUC)', '(DNI)']
    pos = {}
    for i, line in enumerate(lines[:50]):
        uline = line.upper()
        for kw in keywords:
            idx = uline.find(kw)
            if idx >= 0:
                if kw not in pos or idx < pos[kw]:
                    pos[kw] = idx
    return pos

def extract_title_from_pdf(text, persona_name, monto_val, codigo):
    """Main extraction logic."""
    # Find table section
    a1 = re.search(r'Artículo Primero[\.\s\-–—]+(.+?)(?=Artículo Segundo|Artículo\s)', text, re.DOTALL)
    if not a1:
        a1 = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-–—]+(.+?)(?=ART[ÍI]CULO SEGUNDO)', text, re.DOTALL)
    if not a1:
        return None

    section = a1.group(1)
    lines = section.split('\n')

    # Clean lines
    noise = ['DESPACHO', 'DIRECCIÓN GENERAL', 'PATRIMONIO CULTURAL',
             'INDUSTRIAS CULTURALES', 'Decenio', 'Año del', 'copia auténtica',
             'Art. 25', 'clave:', 'Regístrese', 'Comuníquese',
             'Suyuna', "t'aqwaqtawi"]
    clean_lines = []
    for line in lines:
        s = line.strip()
        if not s: continue
        if any(kw in s for kw in noise): continue
        clean_lines.append(line)

    if not clean_lines:
        return None

    # Find header and data boundary
    kw_pos = find_header_positions(clean_lines)

    # Determine column ranges
    empresa_end = 40
    for kw in ('JURÍDICA', 'NATURAL', 'PERSONA', 'BENEFICIARIO', '(RUC)', '(DNI)'):
        if kw in kw_pos:
            empresa_end = max(empresa_end, kw_pos[kw] + 15)
            break

    # Find TÍTULO/PROYECTO column
    p_start, p_end = 55, 100  # defaults
    if 'TÍTULO' in kw_pos:
        p_start = max(0, kw_pos['TÍTULO'] - 2)
    elif 'TITULO' in kw_pos:
        p_start = max(0, kw_pos['TITULO'] - 2)
    elif 'PROYECTO' in kw_pos:
        p_start = max(0, kw_pos['PROYECTO'] - 2)
    elif 'PROGRAMA' in kw_pos:
        p_start = max(0, kw_pos['PROGRAMA'] - 2)
    elif 'OBRA' in kw_pos:
        p_start = max(0, kw_pos['OBRA'] - 2)
    
    for k in ('DIRECTOR', 'RESPONSABLE', 'MONTO', 'ESTÍMULO', 'ESTIMULO', 'OTORGADO'):
        if k in kw_pos and kw_pos[k] > p_start:
            p_end = kw_pos[k] - 2
            break

    # Find monto column
    m_start = None
    for k in ('MONTO', 'ESTÍMULO', 'ESTIMULO', 'OTORGADO'):
        if k in kw_pos:
            m_start = max(0, kw_pos[k] - 2)
            break
    if m_start is None:
        m_start = 110

    # Header count: skip header lines (2+ keyword matches)
    header_kw_count = sum(1 for kw in kw_pos)
    data_start = 0
    for i, line in enumerate(clean_lines):
        s = line.strip()
        kc = sum(1 for kw in kw_pos if kw in line.upper())
        if kc >= 2:
            data_start = i + 1
        elif data_start > 0 and len(s) >= 5:
            data_start = i
            break

    # Scan data lines: group into blocks (separated by blank lines),
    # then match blocks by persona name + monto
    pname_up = persona_name.upper().strip() if persona_name else ''
    pname_words = [w for w in pname_up.split() if len(w) > 3] if pname_up else []
    pname_all_words = pname_up.split() if pname_up else []

    # Group consecutive data lines into blocks
    data_lines = clean_lines[data_start:]
    blocks = []
    current = []
    for line in data_lines:
        s = line.strip()
        if not s:
            if current:
                blocks.append(current)
                current = []
            continue
        if re.search(r'^\s*["\']?\s*$', s):
            continue
        current.append(line)
    if current:
        blocks.append(current)

    best_title = None
    best_score = 0

    for block in blocks:
        block_text = ' '.join(l.strip() for l in block)
        if len(block_text) < 15:
            continue

        # Score block by persona name match
        score = 0
        for w in pname_words:
            for line in block:
                emp_text = line[:empresa_end].strip().upper()
                if w in emp_text:
                    score += 2
                    break

        # Penalize if it looks like a different persona name (comma-separated)
        for line in block:
            emp_text = line[:empresa_end].strip().upper()
            comma_names = re.findall(r'[A-ZÁÉÍÓÚÑ]+\s*,\s*[A-ZÁÉÍÓÚÑ]+', emp_text)
            if comma_names:
                for cn in comma_names:
                    if not any(w in cn for w in pname_words):
                        score -= 2
                break

        # Check monto presence anywhere in block
        has_monto = False
        for line in block:
            if m_start and len(line) > m_start:
                if re.search(r'S/?\.?\s*[\d\s,]+', line[m_start:]):
                    has_monto = True
                    break
            if re.search(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', line):
                has_monto = True
                break
        if has_monto:
            score += 3

        if score < 2 and pname_words:
            continue

        # Extract title from block: collect proyecto-column text across all lines
        # and merge multi-word fragments
        title_parts = []
        all_parts = []
        for line in block:
            if len(line) > p_start:
                p_text = line[p_start:p_end].strip() if p_end else line[p_start:].strip()
                all_parts.append(p_text)
                if p_text:
                    title_parts.append(p_text)
        merged = ' '.join(title_parts)
        merged = re.sub(r'\s+', ' ', merged).strip()

        alt_merged = ' '.join(all_parts)
        alt_merged = re.sub(r'\s+', ' ', alt_merged).strip()
        if len(alt_merged) > len(merged):
            merged = alt_merged

        # Also try extracting text from p_start to monto start
        if m_start:
            m_parts = []
            for line in block:
                if len(line) > p_start:
                    m_text = line[p_start:min(m_start, len(line))].strip() if len(line) > m_start else line[p_start:].strip()
                    if m_text:
                        m_parts.append(m_text)
            m_merged = ' '.join(m_parts)
            m_merged = re.sub(r'\s+', ' ', m_merged).strip()
            if len(m_merged) > len(merged):
                merged = m_merged

        if not merged:
            continue

        if score > best_score:
            best_score = score
            best_title = merged

    if best_title:
        # Clean
        best_title = re.sub(r'\s+', ' ', best_title).strip()
        best_title = re.sub(r'^[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9"\'«]+', '', best_title)
        best_title = re.sub(r'[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s"\'«»,;:\-!¡?¿/]+$', '', best_title)
        best_title = best_title.strip()
        best_title = re.sub(r'\s+[A-ZÁÉÍÓÚÑ]{2,3}$', '', best_title).strip()

        if looks_like_title(best_title) and not is_garbled(best_title):
            return best_title

        # Try first meaningful fragment (split by 3+ spaces or common separators)
        fragments = re.split(r'\s{3,}|(?<=[.!?])\s+', best_title)
        for f in fragments:
            f = f.strip().rstrip(',;:')
            if looks_like_title(f) and not is_garbled(f):
                return f

    return None

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get all obras with corrupt titles that have resolution URLs
    c.execute("""
        SELECT o.id, o.titulo, lc.codigo, c.anio, r.url_pdf, po.monto_otorgado,
               COALESCE(p.razon_social, p.nombres || ' ' || p.apellidos) as pname
        FROM obra o
        JOIN proyecto po ON po.obra_id = o.id
        JOIN persona p ON p.id = po.persona_beneficiaria_id
        JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        ORDER BY o.id
    """)
    rows = c.fetchall()

    # Find garbled ones
    seen = set()
    target = []
    for r in rows:
        oid, titulo = r[0], r[1]
        if oid in seen: continue
        seen.add(oid)
        if is_garbled(titulo):
            target.append(r)

    print(f"Obras con título corrupto y URL: {len(target)}", file=sys.stderr)
    
    results = []
    for oid, old_t, codigo, anio, url, monto, pname in target:
        print(f"  ID={oid:4d} [{codigo} {anio}] buscando...", file=sys.stderr, end=' ')
        
        text = download_pdf(url)
        if not text:
            print(f"ERROR descarga", file=sys.stderr)
            results.append((oid, None))
            continue

        new_t = extract_title_from_pdf(text, pname, monto, codigo)
        if new_t:
            print(f"→ \"{new_t[:60]}\"", file=sys.stderr)
            results.append((oid, new_t))
        else:
            print(f"NO MATCH", file=sys.stderr)
            results.append((oid, None))

    success = sum(1 for r in results if r[1])
    print(f"\nRecuperados: {success}/{len(target)}", file=sys.stderr)
    print(file=sys.stderr)

    for oid, new_t in results:
        if new_t:
            print(f"  ID {oid:4d} → '{new_t}'")
        else:
            print(f"  ID {oid:4d} → NO FIX")

    if RUN:
        updated = 0
        for oid, new_t in results:
            if new_t:
                # Check uniqueness
                cur = c.execute("SELECT id FROM obra WHERE titulo=? AND id!=?", (new_t, oid))
                if cur.fetchone():
                    new_t = f"{new_t} [{oid}]"
                c.execute("UPDATE obra SET titulo=? WHERE id=?", (new_t, oid))
                updated += 1
        conn.commit()
        print(f"\n✅ {updated} títulos actualizados.", file=sys.stderr)
    else:
        print(f"\nUsa --run para aplicar {success} correcciones.", file=sys.stderr)

    conn.close()

if __name__ == '__main__':
    main()
