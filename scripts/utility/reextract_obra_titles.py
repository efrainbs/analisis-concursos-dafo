#!/usr/bin/env python3
"""
Corregir títulos de obra irrecuperables vía re-extracción PDF + matching mixto.

Estrategia:
  - Para FCA/CFO (sin columna TÍTULO): extraer PROGRAMA/INSTITUCIÓN como título
  - Para CPF/CPC/CDO/CPA/etc (con TÍTULO): extraer columna proyecto con límites amplios
  - Matching: monto + persona (razon_social/nombres) para identificar la fila correcta
  - Fallback: persona_name fuzzy search en bloque de texto

Uso:
  python3 reextract_obra_titles.py --run
"""
import sqlite3, sys, os, re, subprocess, urllib.parse, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH, TMP_DIR

RUN = "--run" in sys.argv

SHORT_WORDS = {'A','E','Y','O','LA','EL','LO','AL','DEL','EN','UN','SU',
               'DE','SE','NO','MI','TU','SUS','LOS','LAS','CON','POR',
               'QUE','FUE','ES','YA','HA','HI','VA','VE','DA','LE','ME',
               'TE','SI','NI','3D','2D','II','IV','VI','V','X','8M','S/.'}

def _is_garbled(t):
    t = t.strip()
    if len(t) < 3: return True
    if re.search(r'S/[\s\d,]+', t): return True
    if re.search(r'(DNI|RUC)\s*N?°?\s*\d', t): return True
    if re.search(r'  {3,}', t): return True
    words = re.split(r'[\s,]+', t)
    short_bad = [w for w in words if len(w) <= 2 and w.upper() not in SHORT_WORDS]
    if len(words) >= 3 and len(short_bad) / len(words) > 0.5: return True
    return False

def clean_title(t):
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'^[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9"\'«]+', '', t)
    t = re.sub(r'[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9\s"\'«»,;:\-!¡?¿/]+$', '', t)
    # Remove trailing single uppercase letter (bleed from director column)
    t = re.sub(r'\s+[A-ZÁÉÍÓÚÑ]{1,2}$', '', t)
    # Remove leading numbers/symbols
    t = re.sub(r'^[\d\s\-/]+', '', t)
    t = t.strip()
    return t

def looks_like_title(t):
    t = t.strip().rstrip(',;:')
    if len(t) < 4: return False
    if re.match(r'^\d+$', t): return False
    if re.match(r'^[A-ZÁÉÍÓÚÑÜ ]+,[ \t]*[A-ZÁÉÍÓÚÑÜ ]+', t): return False
    words = t.split()
    if len(words) >= 3:
        single = sum(1 for w in words if len(w) <= 1 and w.isalpha())
        if single > len(words) * 0.3: return False
    if not any(len(w) > 3 for w in words): return False
    if not any(w[0].isupper() for w in words if len(w) > 1): return False
    return True

def extract_amounts(text):
    amounts = []
    for m in re.finditer(r'(?:S/?\.?\s*)?([\d\s,]+[.,]\d{2})', text):
        try:
            amt_str = re.sub(r'\s', '', m.group(1))
            amt_str = amt_str.replace('.', '').replace(',', '.')
            amounts.append(float(amt_str))
        except:
            pass
    return amounts

def download_pdf(url):
    fname = urllib.parse.unquote(url.split('/')[-1])
    cache_key = 'fix2_' + re.sub(r'[^a-zA-Z0-9]', '_', fname)[:75]
    pdf_path = os.path.join(TMP_DIR, cache_key)
    txt_path = pdf_path + "_layout.txt"
    if not os.path.exists(txt_path):
        if not os.path.exists(pdf_path):
            try:
                subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url],
                             check=True, timeout=45, capture_output=True)
            except Exception as e:
                return None, f"download: {e}"
        try:
            subprocess.run(['pdftotext', '-layout', pdf_path, txt_path],
                         check=True, timeout=30, capture_output=True)
        except Exception as e:
            return None, f"pdftotext: {e}"
    with open(txt_path) as f:
        text = f.read()
    text = unicodedata.normalize('NFC', text)
    return text, None

def find_table_lines(text):
    """Find the table section and return non-noise lines."""
    idx = text.find('Artículo Primero')
    if idx < 0: idx = text.find('ARTÍCULO PRIMERO')
    if idx < 0: idx = text.find('RESUELVE:')
    if idx < 0: idx = 0
    
    end = text.find('Artículo Segundo', idx)
    if end < 0: end = text.find('ARTÍCULO SEGUNDO', idx)
    if end < 0: end = len(text)
    
    section = text[idx:end]
    lines = section.split('\n')
    
    noise = ['DESPACHO', 'DIRECCIÓN GENERAL', 'PATRIMONIO CULTURAL',
             'INDUSTRIAS CULTURALES', 'Decenio', 'Año del', 'copia auténtica',
             'Art. 25', 'clave:', 'Regístrese', 'Comuníquese',
             'Suyuna', "t'aqwaqtawi", 'contrastadas', 'validadorDocumental',
             'Igualdad de Oportunidades', 'Bicentenario del Perú']
    
    clean = []
    for line in lines:
        s = line.strip()
        if not s: continue
        if any(kw in s for kw in noise): continue
        # Skip preamble lines (Artículo, Declárese)
        if re.match(r'Art[íi]culo|ART[ÍI]CULO|Decl[áa]rese|DECL[ÁA]RESE|Cons[íi]gnese', s):
            continue
        clean.append(line)
    return clean

def extract_title_from_block(block, kw_positions, monto_val):
    """Given a block of lines for one beneficiary, extract the best title."""
    block_text = ' '.join(block)

    # Try to find title by column positions
    p_start = 60  # default
    p_end = 95    # default

    if 'TÍTULO' in kw_positions:
        p_start = max(0, kw_positions['TÍTULO'] - 3)
        # Director or monto as end boundary
        for k in ('DIRECTOR', 'RESPONSABLE', 'MONTO'):
            if k in kw_positions:
                p_end = kw_positions[k] - 2
                break
    elif 'TITULO' in kw_positions:
        p_start = max(0, kw_positions['TITULO'] - 3)
    elif 'PROYECTO' in kw_positions:
        p_start = max(0, kw_positions['PROYECTO'] - 3)
    
    if 'PROGRAMA' in kw_positions and 'TÍTULO' not in kw_positions and 'TITULO' not in kw_positions:
        # FCA/CFO style: use PROGRAMA column
        p_start = max(0, kw_positions['PROGRAMA'] - 3)
        for k in ('INSTITUCIÓN', 'INSTITUCION', 'DIRECTOR', 'MONTO'):
            if k in kw_positions and kw_positions[k] > p_start:
                p_end = kw_positions[k] - 2
                break
    
    if 'OBRA' in kw_positions:
        # EPI style: OBRA VINCULADA -> 'proyecto'
        p_start = max(0, kw_positions['OBRA'] - 3)
        for k in ('EVENTO', 'MONTO'):
            if k in kw_positions:
                p_end = kw_positions[k] - 2
                break
    
    if 'EVENTO' in kw_positions:
        e_start = max(0, kw_positions['EVENTO'] - 3)
        e_end = 113
        for k in ('MONTO',):
            if k in kw_positions:
                e_end = kw_positions[k] - 2
                break
        # For EPI: evento is separate from proyecto (obra)
    
    # Extract from proyecto column
    title_parts = []
    for line in block:
        if len(line) > p_start:
            val = line[p_start:p_end].strip()
            if val:
                title_parts.append(val)
    title = ' '.join(title_parts)
    title = clean_title(title)
    
    if looks_like_title(title):
        return title
    
    # Try EVENTO column for EPI
    if 'EVENTO' in kw_positions:
        e_start = max(0, kw_positions['EVENTO'] - 3)
        e_end = 113
        for k in ('MONTO',):
            if k in kw_positions:
                e_end = kw_positions[k] - 2
                break
        ev_parts = []
        for line in block:
            if len(line) > e_start:
                val = line[e_start:e_end].strip()
                if val:
                    ev_parts.append(val)
        ev_title = ' '.join(ev_parts)
        ev_title = clean_title(ev_title)
        if looks_like_title(ev_title):
            # Check it's not just a description of something
            if not re.match(r'^(Actividades|EVENTO|INTERNACIONAL|VINCULADO|a la|de la)', ev_title, re.I):
                return ev_title
    
    # Fallback: try wider range
    title_parts2 = []
    for line in block:
        val = line[40:100].strip()
        if val:
            title_parts2.append(val)
    title2 = ' '.join(title_parts2)
    title2 = clean_title(title2)
    
    # Look for the first proper fragment
    fragments = re.split(r'  +', title2)
    for f in fragments:
        f = f.strip().rstrip(',;:')
        if looks_like_title(f) and len(f) >= 5:
            return f
    
    if looks_like_title(title2):
        return title2
    
    return None

def find_best_block(all_lines, kw_positions, monto_val, persona_name):
    """Find which line block contains the target monto + persona."""
    # Strategy: split at lines containing amounts
    blocks = []
    current = []
    for line in all_lines:
        amts = extract_amounts(line)
        has_amt = any(abs(a - monto_val) < 100 for a in amts)
        if has_amt and current:
            blocks.append(current)
            current = [line]
        elif has_amt:
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    
    scored = []
    for block in blocks:
        block_text = ' '.join(block)
        # Score: monto match + persona match
        score = 0
        amts = extract_amounts(block_text)
        score += sum(5 for a in amts if abs(a - monto_val) < 50)
        
        if persona_name:
            name_parts = persona_name.upper().split()[:3]
            matches = sum(1 for p in name_parts if len(p) > 3 and p in block_text.upper())
            score += matches * 3
        
        scored.append((score, block))
    
    scored.sort(key=lambda x: -x[0])
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return None

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT o.id, o.titulo, lc.codigo, c.anio, r.url_pdf, po.monto_otorgado,
               po.persona_beneficiaria_id, 
               COALESCE(p.razon_social, p.nombres || ' ' || p.apellidos) as persona_name
        FROM obra o
        JOIN proyecto po ON po.obra_id = o.id
        JOIN persona p ON p.id = po.persona_beneficiaria_id
        JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        LEFT JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
        LEFT JOIN resolucion r ON r.id = pr.resolucion_id
        ORDER BY o.id
    """)
    rows = c.fetchall()

    seen = set()
    target = []
    for r in rows:
        oid = r[0]
        if oid in seen:
            continue
        seen.add(oid)
        titulo = r[1]
        if not _is_garbled(titulo):
            continue
        # Already recovered by heuristic
        fragments = re.split(r'  +', titulo.strip())
        recovered = False
        for f in fragments:
            f = f.strip().rstrip(',;:')
            f = re.sub(r'^[\s\.,\-\/\)\]\[\(]+', '', f)
            f = re.sub(r'[\s\.,\-\/\(\)\[\]"]+$', '', f)
            if looks_like_title(f):
                recovered = True
                break
        if recovered:
            continue
        target.append(r)

    print(f"Obras a re-extraer: {len(target)}", file=sys.stderr)

    results = []
    for oid, old_title, codigo, anio, url, monto, pbid, pname in target:
        if not url:
            print(f"  ID={oid:4d} [{codigo} {anio}] SIN URL", file=sys.stderr)
            results.append((oid, None, 'sin URL'))
            continue

        print(f"  ID={oid:4d} [{codigo} {anio}] monto={monto} persona={pname[:30]}...", file=sys.stderr, end=' ')

        text, err = download_pdf(url)
        if err:
            print(f"ERROR: {err}", file=sys.stderr)
            results.append((oid, None, err))
            continue

        all_lines = find_table_lines(text)
        if not all_lines:
            print(f"no table found", file=sys.stderr)
            results.append((oid, None, 'no table'))
            continue

        # Detect keyword positions
        keywords = ['PERSONA', 'JURÍDICA', '(RUC)', 'NATURAL', 'REGIÓN', 'REGION',
                    'TÍTULO', 'TITULO', 'DIRECTOR', 'MONTO', 'OTORGADO',
                    'PROYECTO', 'RESPONSABLE', 'INSTITUCIÓN', 'INSTITUCION', 'PROGRAMA',
                    'EVENTO', 'CATEGORÍA', 'OBRA', 'VINCULADA', 'FORMACIÓN',
                    'ESTÍMULO', 'ESTIMULO', 'BENEFICIARIO', 'CÓDIGO', 'CODIGO']
        
        kw_positions = {}
        for line in all_lines[:30]:
            uline = line.upper()
            for kw in keywords:
                idx = uline.find(kw)
                if idx >= 0:
                    if kw not in kw_positions or idx < kw_positions[kw]:
                        kw_positions[kw] = idx

        block = find_best_block(all_lines, kw_positions, monto, pname)
        if not block:
            print(f"NO MATCH", file=sys.stderr)
            results.append((oid, None, f'no match'))
            continue

        new_title = extract_title_from_block(block, kw_positions, monto)
        if new_title and looks_like_title(new_title):
            print(f"→ \"{new_title}\"", file=sys.stderr)
            results.append((oid, new_title, old_title))
        elif new_title and _is_garbled(new_title):
            # Try wider extraction
            block_text = ' '.join(block)
            fragments = re.split(r'  +', block_text)
            for f in fragments:
                f = f.strip().rstrip(',;:')
                if looks_like_title(f) and len(f) >= 5 and not _is_garbled(f):
                    new_title = f
                    break
            if new_title and looks_like_title(new_title):
                print(f"→ \"{new_title}\" (fragment)", file=sys.stderr)
                results.append((oid, new_title, old_title))
            else:
                print(f"GARBLED: \"{new_title[:60]}\"", file=sys.stderr)
                results.append((oid, None, f'garbled: {new_title[:40]}'))
        else:
            print(f"NO TITLE FOUND", file=sys.stderr)
            results.append((oid, None, 'no title'))

    print(f"\n--- Resultados ---", file=sys.stderr)
    success = sum(1 for r in results if r[1])
    fail = sum(1 for r in results if not r[1])
    print(f"Recuperados: {success}", file=sys.stderr)
    print(f"Fallaron: {fail}", file=sys.stderr)
    print(file=sys.stderr)

    for oid, new_t, old_t in results:
        if new_t:
            print(f"  ID {oid:4d} '{old_t[:55]}' → '{new_t}'")
        else:
            print(f"  ID {oid:4d} FAILED: {old_t}")

    if RUN:
        updated = 0
        for oid, new_t, _ in results:
            if new_t:
                cur = c.execute("SELECT id FROM obra WHERE titulo=? AND id!=?", (new_t, oid))
                if cur.fetchone():
                    new_t = f"{new_t} [fix]"
                c.execute("UPDATE obra SET titulo=? WHERE id=?", (new_t, oid))
                updated += 1
        conn.commit()
        print(f"\n✅ {updated} títulos actualizados.", file=sys.stderr)
    else:
        print(f"\nUsa --run para aplicar {success} correcciones.", file=sys.stderr)

    conn.close()

if __name__ == '__main__':
    main()
