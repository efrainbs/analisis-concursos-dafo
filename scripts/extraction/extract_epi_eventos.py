"""
Extraer eventos internacionales de EPI RDs individuales.
Cada RD individual tiene UN beneficiario con columna EVENTO INTERNACIONAL.
Uso: python3 extract_epi_eventos.py [--run]
"""
import os, re, sqlite3, subprocess, sys, unicodedata

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
TMP_DIR = "/tmp/dafo_pdfs"
DRY_RUN = '--run' not in sys.argv
os.makedirs(TMP_DIR, exist_ok=True)

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

EVENT_KW = r'(FESTIVAL|CONCURSO|MUESTRA|ENCUENTRO|LABORATORIO|LAB[O0]?[RG]?[UO]?[NI]?|PREMIOS|PREMIO|BIENAL|CERTAMEN|WORKSHOP|RESIDENCIA|FORO|CONGRESO|SEMINARIO|CICLO|EXPOSICI[ÓO]N|CONFERENCIA|TALLER|PREMIO NACIONAL|CONCURSO NACIONAL|MUESTRA DE CINE)'

event_kw_re = re.compile(EVENT_KW, re.IGNORECASE)

HEADER_KW = ['PERSONA NATURAL', 'PERSONA', 'NATURAL', 'REGIÓN', 'REGION',
             'REGIÓ', 'PROYECTO', 'OBRA', 'VINCULADA', 'VINCULADO',
             'EVENTO', 'MONTO', 'ESTÍMULO', 'POSTULACIÓN',
             'SOLICITUD', 'REPLANTEAMIENTO', 'PAÍS', 'PAIS', 'DNI',
             'PROYECTO U']


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
    # Case-insensitive: handles Artículo Primero, ARTÍCULO PRIMERO, artículo primero, etc.
    m = re.search(r'Art[íÍiI]culo Primero[.\s\-–—]+(.+?)(?=Art[íÍiI]culo Segundo)', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1)
    # Fallback: if regex fails due to unusual spacing, try finding positions directly
    for kw1, kw2 in [('ARTÍCULO PRIMERO', 'ARTÍCULO SEGUNDO'),
                     ('Artículo Primero', 'Artículo Segundo'),
                     ('Artículo Primero', 'ARTÍCULO SEGUNDO')]:
        i1 = text.upper().find(kw1.upper())
        i2 = text.upper().find(kw2.upper(), i1 + 10)
        if i1 >= 0 and i2 >= 0:
            return text[i1 + len(kw1):i2]
    return text


def clean_event_text(raw):
    raw = re.sub(r'\s+', ' ', raw).strip()
    # Remove leading non-alpha characters
    while raw and not raw[0].isalpha() and raw[0] not in '(ÁÉÍÓÚÑáéíóúñ':
        raw = raw[1:]
    raw = re.sub(r'[\s,;/]+$', '', raw)
    raw = re.sub(r'\s*[–\-—]\s*$', '', raw)
    raw = re.sub(r'^\s*[–\-—]\s*', '', raw)
    # Remove leading number artifacts (monto fragments like "00 ", "0.00 ")
    raw = re.sub(r'^[\d\s]+[.,]?\d*\s+', '', raw)
    return raw.strip()


def remove_monto(text):
    # Full monto: S/ 15 000,00, S/. 15 000.00, S/15000,00
    text = re.sub(r'S[/.]?\s*[\d\s]+[.,]\d{2}', '', text)
    # Monto fragments without S/: bare numbers like ",00", "0,00", "900,00"
    text = re.sub(r'(?<![A-Za-zÁÉÍÓÚÑ])\d+[.,]\d{2}', '', text)
    # Trailing S/ die
    text = re.sub(r'S[/.]?\s*$', '', text)
    # Header artifacts
    text = re.sub(r'\bMONTO\b.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bESTÍMULO\b.*$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\bDEL\s+ESTÍMULO\b.*$', '', text, flags=re.IGNORECASE)
    return text.strip()


def find_data_lines(lines):
    """Skip header lines and return data lines."""
    data_start = 0
    last_header = -1
    for i, line in enumerate(lines):
        u = line.upper()
        if any(kw in u for kw in HEADER_KW):
            last_header = i
            data_start = i + 1
        elif data_start > 0 and line.strip() and last_header >= 0:
            break

    if data_start == 0:
        data_start = last_header + 1

    data_lines = []
    for line in lines[data_start:]:
        s = line.strip()
        if not s:
            if data_lines:
                break
            continue
        data_lines.append(line)
    return data_lines


def extract_by_column(lines, data_lines, evento_pos):
    """Method 1: Extract from evento column position to end of line."""
    # Use evento_pos - 12 to handle column padding (header is right-aligned in column)
    col_start = max(0, evento_pos - 12)
    parts = []
    for line in data_lines:
        if len(line) > col_start:
            ev = line[col_start:].strip()
            if ev:
                parts.append(ev)
    if not parts:
        return None
    raw = ' '.join(parts)
    raw = remove_monto(raw)
    raw = clean_event_text(raw)
    if len(raw) >= 4 and re.search(r'[A-Za-zÁÉÍÓÚÑ]', raw):
        return raw
    return None


def extract_by_right_side(lines, data_lines):
    """Method 2: Extract from right 40% of each data line."""
    parts = []
    for line in data_lines:
        col = int(len(line) * 0.6)
        right = line[col:].strip()
        if right and not any(kw.upper() in right.upper() for kw in HEADER_KW):
            parts.append(right)
    if not parts:
        return None
    raw = ' '.join(parts)
    raw = remove_monto(raw)
    raw = clean_event_text(raw)
    if len(raw) >= 4 and re.search(r'[A-Za-zÁÉÍÓÚÑ]', raw):
        return raw
    return None


def extract_by_event_keyword(lines, data_lines):
    """Method 3: Find event keyword in data lines and extract from there."""
    full_text = ' '.join(line.strip() for line in data_lines if line.strip())
    full_text = remove_monto(full_text)

    m = re.search(rf'{EVENT_KW}[^;]*?(?:\([A-Za-zÁÉÍÓÚÑ\s]+\))?', full_text, re.IGNORECASE)
    if m:
        raw = clean_event_text(m.group(0))
        if len(raw) >= 4:
            return raw

    # Try broader match across full A1
    full_a1 = ' '.join(line.strip() for line in lines if line.strip())
    full_a1 = remove_monto(full_a1)
    m = re.search(rf'{EVENT_KW}[^;]*?(?:\([A-Za-zÁÉÍÓÚÑ\s]+\))?', full_a1, re.IGNORECASE)
    if m:
        raw = clean_event_text(m.group(0))
        if len(raw) >= 4:
            return raw

    return None


def find_evento_column(lines):
    """Find EVENTO column position in header.
    Returns the character position where 'EVENTO' starts."""
    evento_pos = None
    for line in lines:
        u = line.upper()
        idx = u.find('EVENTO')
        if idx >= 50:
            if 'INTERNACIONAL' in u:
                evento_pos = idx
                break
            if evento_pos is None:
                evento_pos = idx
    return evento_pos


def has_event_column(lines):
    """Check if the A1 section has an EVENTO INTERNACIONAL column."""
    for line in lines:
        u = line.upper()
        if 'EVENTO' in u and 'INTERNACIONAL' in u:
            return True
    return False


def extract_evento_from_a1(a1_text):
    """Find EVENTO INTERNACIONAL using multiple methods."""
    lines = a1_text.split('\n')
    data_lines = find_data_lines(lines)

    if not data_lines:
        return None, 'no_data_lines'

    evento_pos = find_evento_column(lines)
    has_col = evento_pos is not None

    # Try methods in order
    if has_col:
        evento = extract_by_column(lines, data_lines, evento_pos)
        if evento:
            return evento, 'column'

    evento = extract_by_right_side(lines, data_lines)
    if evento:
        return evento, 'right_side'

    evento = extract_by_event_keyword(lines, data_lines)
    if evento:
        return evento, 'keyword'

    if has_col:
        return None, 'no_match_col'
    return None, 'no_evento_header'


def parse_country(evento):
    nombre = evento
    pais = ''

    artifacts = [
        r'^[VE]?ULADO\s+A\s+LA\s+[EPT]+\s*ULACI[ÓO]N\s*',
        r'^[VE]?ULADA\s+A\s+LA\s+[EPT]+\s*ULACI[ÓO]N\s*',
        r'^[AEO]+\s*ULACI[ÓO]N\s*',
        r'^[AEO]+\s*TULACI[ÓO]N\s*',
        r'^POSTULACI[ÓO]N\s*',
        r'^LA\s+POSTULACI[ÓO]N\s*',
        r'^EVENTO\s+INTERNACIONAL\s+',
        r'^VINCULADO\s+A\s+LA\s+POSTULACI[ÓO]N\s+',
        r'^INTERNACIONAL\s+',
        r'^VINCULAD[OA]\s+A\s+LA\s+',
        r'^VINCULAD[OA]\s+',
    ]
    for pat in artifacts:
        nombre = re.sub(pat, '', nombre, flags=re.IGNORECASE)

    nombre = re.sub(r'^[^A-Za-zÁÉÍÓÚÑ0-9\(]+', '', nombre)
    nombre = re.sub(r'[\s,;]+$', '', nombre)
    nombre = re.sub(r'\s*[–\-—]\s*$', '', nombre)
    nombre = re.sub(r'^\s*[–\-—]\s*', '', nombre)

    m = re.search(r'\(([^)]+)\)\s*$', nombre)
    if m:
        pais = m.group(1).strip()
        nombre = nombre[:m.start()].strip()

    fake_paises = ['ESPACIO FORMATIVO', 'ESPACIO RMATIVO', 'Espacio formativo',
                   'Espacio ormativo', 'ESPACIO S MATIVO', 'ESPACIO S FORMATIVO',
                   'ESPACIO FORMATIVO)', 'ESPACIO RMATIVO)']
    if pais.upper().strip() in [fp.upper() for fp in fake_paises]:
        pais = ''

    m = re.search(EVENT_KW, nombre, re.IGNORECASE)
    if m:
        # Only strip prefix if it looks like column-bleed artifact
        prefix = nombre[:m.start()].strip()
        if not prefix or re.search(r'(POSTULACIÓN|VINCULAD[OA]|EVENTO|INTERNACIONAL|MONTO|ESTÍMULO|REGI[ÓO]N)', prefix, re.IGNORECASE):
            nombre = nombre[m.start():]
    
    nombre = re.sub(r'\s+', ' ', nombre).strip()
    
    # Don't discard short names if they have event keywords
    has_kw = bool(re.search(EVENT_KW, nombre, re.IGNORECASE))
    if not has_kw and (len(nombre) < 5 or re.match(r'^[^A-Za-zÁÉÍÓÚÑ]+$', nombre)):
        return '', ''
    if has_kw and len(nombre) < 3:
        return '', ''

    return nombre, pais.strip()


def get_person_name(proj):
    if proj['nombres'] and proj['apellidos']:
        return f"{proj['nombres']} {proj['apellidos']}".strip()
    return proj['razon_social'] or ''


def fetch_event_from_body_text(text):
    """Fallback: search entire PDF text for event mentions."""
    lines = text.split('\n')
    candidates = []
    for line in lines:
        s = line.strip()
        m = event_kw_re.search(s)
        if m:
            start = max(0, m.start() - 3)
            candidate = s[start:].strip()
            candidate = re.sub(r'\s+', ' ', candidate).strip()
            if len(candidate) >= 6:
                candidates.append(candidate)
    return candidates[0] if candidates else None


def main():
    rows = db.execute("""
        SELECT DISTINCT p.id, per.nombres, per.apellidos, per.razon_social,
               p.monto_otorgado, r.url_pdf, c.anio
        FROM proyecto p
        JOIN persona per ON per.id = p.persona_beneficiaria_id
        JOIN proyecto_resolucion pr ON pr.proyecto_id = p.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        JOIN concurso_anual ca ON ca.id = p.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        LEFT JOIN proyecto_evento pe ON pe.proyecto_id = p.id
        WHERE lc.codigo = 'EPI' AND pe.proyecto_id IS NULL
          AND r.url_pdf IS NOT NULL
        ORDER BY c.anio, p.id
    """).fetchall()

    print(f"EPI sin evento: {len(rows)}")
    print(f"{'DRY RUN' if DRY_RUN else 'APLICANDO'}\n")

    results = []
    seen_pids = set()
    for r in rows:
        pid = r['id']
        pname = get_person_name(r)
        url = r['url_pdf']
        anio = r['anio']

        print(f"P{pid} ({anio}): {pname[:50]}", end=' ')
        sys.stdout.flush()

        text = get_layout_text(url)
        if text is None:
            print(f"— ERROR descarga")
            results.append((pid, None, 'download_error'))
            continue

        a1 = extract_article_1(text)
        evento, metodo = extract_evento_from_a1(a1)

        if evento:
            nombre, pais = parse_country(evento)
            if nombre:
                print(f"[{metodo}] → {nombre[:70]} (país={pais})")
                results.append((pid, nombre, pais))
            else:
                print(f"[{metodo}] — parseó vacío de '{evento[:60]}'")
                results.append((pid, None, 'empty_name'))
        else:
            evento_body = fetch_event_from_body_text(text)
            if evento_body:
                print(f"[body_text] → {evento_body[:70]}")
                results.append((pid, evento_body, ''))
            else:
                print(f"— {metodo}")
                results.append((pid, None, metodo))

    success = sum(1 for r in results if r[1])
    print(f"\nRecuperados: {success}/{len(results)}")

    if DRY_RUN:
        print(f"Usa --run para aplicar")
    else:
        updated = 0
        skipped = 0
        for pid, nombre, pais in results:
            if not nombre:
                skipped += 1
                continue
            if not pais:
                pais = 'No especificado'
            db.execute("""INSERT OR IGNORE INTO evento_internacional (nombre, pais, modalidad, tipo_evento) VALUES (?, ?, 'presencial', 'festival')""", (nombre, pais))
            cur = db.execute("SELECT id FROM evento_internacional WHERE nombre=? AND pais=?", (nombre, pais))
            row = cur.fetchone()
            if row:
                eid = row[0]
                db.execute("INSERT OR IGNORE INTO proyecto_evento (proyecto_id, evento_internacional_id) VALUES (?, ?)", (pid, eid))
                updated += 1
        db.commit()
        print(f"Aplicados: {updated}, Saltados: {skipped}")

    db.close()


if __name__ == '__main__':
    main()
