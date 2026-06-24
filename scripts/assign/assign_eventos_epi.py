#!/usr/bin/env python3
"""Re-extraer evento internacional de RDs EPI y poblar proyecto_evento.

Para cada proyecto EPI sin proyecto_evento:
1. Descarga el PDF de la resolución
2. Busca la tabla de beneficiarios en Artículo Primero
3. Extrae la columna EVENTO para el beneficiario que coincide
4. Inserta en evento_internacional + proyecto_evento

Uso: python3 assign_eventos_epi.py --run
"""
import sys, re, os, sqlite3, subprocess, urllib.parse, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH, TMP_DIR

RUN = "--run" in sys.argv

EVENTO_KWS = ['EVENTO', 'MONTO', 'OTORGADO', 'ESTÍMULO', 'ESTIMULO',
              'DIRECTOR', 'RESPONSABLE', 'PROYECTO', 'OBRA', 'VINCULADA']

def download_pdf(url):
    fname = urllib.parse.unquote(url.split('/')[-1])
    key = 'epi_' + re.sub(r'[^a-zA-Z0-9]', '_', fname)[:70]
    pdf_path = os.path.join(TMP_DIR, key)
    txt_path = pdf_path + '_layout.txt'
    if not os.path.exists(txt_path):
        if not os.path.exists(pdf_path):
            try:
                subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url],
                               check=True, timeout=45, capture_output=True)
            except:
                return None
        try:
            subprocess.run(['pdftotext', '-layout', pdf_path, txt_path],
                           check=True, timeout=30, capture_output=True)
        except:
            return None
    with open(txt_path) as f:
        text = f.read()
    return unicodedata.normalize('NFC', text)

def extract_evento(text, persona_name, monto_val):
    """Find beneficiary table in Artículo Primero and extract EVENTO column."""
    a1 = re.search(r'Artículo Primero[.\s\-–—]+(.+?)(?=Artículo Segundo|Artículo\s)', text, re.DOTALL)
    if not a1:
        a1 = re.search(r'ART[ÍI]CULO PRIMERO[.\s\-–—]+(.+?)(?=ART[ÍI]CULO SEGUNDO)', text, re.DOTALL)
    if not a1:
        return None

    section = a1.group(1)
    lines = section.split('\n')
    clean = []
    for line in lines:
        s = line.strip()
        if not s:
            clean.append('')
            continue
        noise = ['DESPACHO', 'DIRECCIÓN GENERAL', 'PATRIMONIO CULTURAL',
                 'INDUSTRIAS CULTURALES', 'Decenio', 'Año del', 'copia auténtica',
                 'Art. 25', 'clave:', 'Regístrese', 'Comuníquese',
                 'Suyuna', "t'aqwaqtawi"]
        if any(kw in s for kw in noise):
            clean.append('')
        else:
            clean.append(line)

    # Find header keywords
    kw_pos = {}
    for i, line in enumerate(clean[:50]):
        if not line.strip():
            continue
        uline = line.upper()
        for kw in EVENTO_KWS:
            idx = uline.find(kw)
            if idx >= 0 and (kw not in kw_pos or idx < kw_pos[kw]):
                kw_pos[kw] = idx

    # Determine column ranges
    # OBRA VINCULADA column ends where EVENTO starts
    obra_start = None
    for k in ('OBRA', 'PROYECTO'):
        if k in kw_pos:
            obra_start = kw_pos[k]
            break
    evento_start = None
    for k in ('EVENTO',):
        if k in kw_pos:
            evento_start = kw_pos[k]
            break
    monto_start = None
    for k in ('MONTO', 'OTORGADO', 'ESTÍMULO', 'ESTIMULO'):
        if k in kw_pos:
            monto_start = kw_pos[k]
            break

    if not evento_start or not monto_start:
        return None

    evento_end = monto_start
    if obra_start and obra_start < evento_start:
        empresa_end = obra_start
    else:
        empresa_end = evento_start - 5

    # Find data start (skip header lines)
    data_start = 0
    header_count = 0
    for i, line in enumerate(clean):
        s = line.strip()
        if not s:
            continue
        kc = sum(1 for kw in kw_pos if kw in line.upper())
        if kc >= 2:
            header_count += 1
            data_start = i + 1
        elif data_start > 0 and len(s) >= 3:
            data_start = i
            break

    # Group into blocks by blank lines
    rows = clean[data_start:]
    blocks = []
    cur = []
    for line in rows:
        s = line.strip()
        if not s:
            if cur:
                blocks.append(cur)
                cur = []
            continue
        cur.append(line)
    if cur:
        blocks.append(cur)

    # Prepare persona name matching
    pname_up = persona_name.upper().strip() if persona_name else ''
    pname_words = [w for w in pname_up.split() if len(w) > 3] if pname_up else []
    monto_str = f"{monto_val:.0f}" if monto_val else ''

    best_evento = None
    best_score = 0

    for block in blocks:
        score = 0
        # Check persona name in empresa area of any line in block
        for line in block:
            emp_text = line[:empresa_end].strip().upper() if len(line) > empresa_end else ''
            for w in pname_words:
                if w in emp_text:
                    score += 2
        if score < 2 and pname_words:
            continue

        # Check monto
        has_monto = False
        for line in block:
            if re.search(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', line.upper()):
                has_monto = True
                break
        if has_monto:
            score += 3

        if score > best_score:
            best_score = score
            # Extract evento: merge texto de columna EVENTO a través del bloque
            parts = []
            for line in block:
                if len(line) > evento_start:
                    ev_text = line[evento_start:evento_end].strip()
                    if ev_text:
                        parts.append(ev_text)
            if parts:
                best_evento = ' '.join(parts)

    if best_evento and best_score >= 3:
        return re.sub(r'\s+', ' ', best_evento).strip()
    return None

def parse_evento_country(evento_text):
    """Parse 'Event Name (Country)' or similar pattern."""
    pais = ''
    nombre = evento_text

    # Remove common column-bleed prefixes
    nombre = re.sub(r'^EVENTO\s+INTERNACIONAL\s+', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'^VINCULADO\s+A\s+LA\s+POSTULACI[ÓO]N\s+', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'^RNACIONAL\s+ULADO\s+A\s+(LA\s+)?E?\s*TULACI[ÓO]N\s+', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'^ULADA\s+A\s+LA\s+TULACION\s+', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'^NACIONAL\s+(CULADO\s+A\s+LA\s+)?ULACI[ÓO]N\s+', '', nombre, flags=re.IGNORECASE)
    nombre = re.sub(r'^ULADO\s+A\s+LA\s+TULACI[ÓO]N\s+', '', nombre, flags=re.IGNORECASE)

    # Parse (Country)
    m = re.search(r'\(([^)]+)\)\s*$', nombre)
    if m:
        pais = m.group(1).strip()
        nombre = nombre[:m.start()].strip()

    # Clean pais artifacts
    fake_paises = ['ESPACIO FORMATIVO', 'ESPACIO RMATIVO', 'ESPACIO ORMATIVO',
                   'Espacio ormativo', 'Espacio de formación', 'Espacio formativo',
                   'ESPACIO S MATIVO', 'ESPACIO MATIVO']
    if pais.upper().strip() in [fp.upper() for fp in fake_paises]:
        pais = ''

    nombre = re.sub(r'\s*[–\-—]\s*$', '', nombre).strip()
    nombre = re.sub(r'\s+acio\s+formativo\)?\s*$', '', nombre, flags=re.IGNORECASE).strip()
    nombre = re.sub(r'[\s,;]+$', '', nombre).strip()

    return nombre, pais

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Find EPI projects without proyecto_evento
    c.execute("""
        SELECT p.id, COALESCE(pers.razon_social, pers.nombres || ' ' || pers.apellidos) as pname,
               p.monto_otorgado, r.url_pdf, lc.codigo, cv.anio
        FROM proyecto p
        JOIN concurso_anual ca ON ca.id = p.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN persona pers ON pers.id = p.persona_beneficiaria_id
        JOIN proyecto_resolucion pr ON pr.proyecto_id = p.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        JOIN convocatoria cv ON cv.id = ca.convocatoria_id
        LEFT JOIN proyecto_evento pe ON pe.proyecto_id = p.id
        WHERE lc.codigo = 'EPI' AND pe.proyecto_id IS NULL
    """)
    rows = c.fetchall()
    print(f"EPI sin evento: {len(rows)}", file=sys.stderr)

    results = []
    for pid, pname, monto, url, codigo, anio in rows:
        if not url:
            results.append((pid, None, 'no_url'))
            continue

        print(f"  PID={pid} [{anio}]...", file=sys.stderr, end=' ')
        text = download_pdf(url)
        if not text:
            print("ERROR descarga", file=sys.stderr)
            results.append((pid, None, 'download_error'))
            continue

        evento_text = extract_evento(text, pname, monto)
        if evento_text:
            nombre, pais = parse_evento_country(evento_text)
            if nombre:
                print(f"→ '{nombre}' (pais='{pais}')", file=sys.stderr)
                results.append((pid, nombre, pais))
            else:
                print("nombre vacío", file=sys.stderr)
                results.append((pid, None, 'empty_name'))
        else:
            print("NO MATCH", file=sys.stderr)
            results.append((pid, None, 'no_match'))

    success = sum(1 for r in results if r[1])
    print(f"\nRecuperados: {success}/{len(results)}", file=sys.stderr)

    for pid, nombre, pais in results:
        if nombre:
            print(f"  PID {pid}: '{nombre}' (pais={pais})")
        else:
            print(f"  PID {pid}: {pais}")

    if RUN:
        updated = 0
        for pid, nombre, pais in results:
            if not nombre:
                continue
            if not pais:
                pais = 'No especificado'
            # Insert evento_internacional
            c.execute("""INSERT OR IGNORE INTO evento_internacional (nombre, pais, modalidad, tipo_evento) VALUES (?, ?, 'presencial', 'festival')""", (nombre, pais))
            # Get its ID
            c.execute("SELECT id FROM evento_internacional WHERE nombre=? AND pais=?", (nombre, pais))
            row = c.fetchone()
            if row:
                eid = row[0]
                c.execute("INSERT OR IGNORE INTO proyecto_evento (proyecto_id, evento_internacional_id) VALUES (?, ?)", (pid, eid))
                updated += 1
        conn.commit()
        print(f"\n✅ {updated} eventos asignados.", file=sys.stderr)
    else:
        print(f"\nUsa --run para aplicar {success} correcciones.", file=sys.stderr)

    conn.close()

if __name__ == '__main__':
    main()
