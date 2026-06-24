#!/usr/bin/env python3
"""Extract missing 2019 data: CIN, CFO (fix), CFR, EDI, EPI."""
import subprocess, re, sys, os, tempfile, sqlite3, shutil, json

DB_PATH = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")
TMP_DIR = "/tmp/dafo_2019"
os.makedirs(TMP_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

def parse_amount(s):
    s = s.replace(' ', '')
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    return float(s)

def q(s):
    if s is None:
        return 'NULL'
    if s == '':
        return "''"
    return "'" + str(s).replace("'", "''") + "'"

def get_concurso_anual_id(anio, codigo):
    row = c.execute("""SELECT ca.id FROM concurso_anual ca
        JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
        JOIN convocatoria cv ON ca.convocatoria_id = cv.id
        WHERE lc.codigo = ? AND cv.anio = ?""", (codigo, anio)).fetchone()
    return row[0] if row else None

def ensure_concurso_anual(anio, codigo):
    ca_id = get_concurso_anual_id(anio, codigo)
    if ca_id: return ca_id
    lc = c.execute("SELECT id FROM linea_concursable WHERE codigo = ?", (codigo,)).fetchone()
    if not lc:
        return None
    cv = c.execute("SELECT id FROM convocatoria WHERE anio = ?", (anio,)).fetchone()
    if not cv:
        c.execute("INSERT INTO convocatoria (anio, nombre) VALUES (?, ?)", (anio, f"Estímulos Económicos {anio}"))
        cv = (c.lastrowid,)
    c.execute("INSERT INTO concurso_anual (linea_concursable_id, convocatoria_id) VALUES (?, ?)", (lc[0], cv[0]))
    return c.lastrowid

def dl_pdf(url, name):
    path = os.path.join(TMP_DIR, name)
    if not os.path.exists(path):
        subprocess.run(['curl', '-sLk', '-o', path, url], check=True, timeout=60)
    return path

def pdf_to_text(path):
    txt = path + '.txt'
    subprocess.run(['pdftotext', path, txt], check=True, timeout=30)
    with open(txt) as f: return f.read()

# ============================================================
# 1. CIN 2019 — text-based, personas naturales
# ============================================================
def extract_cin_2019():
    print("=== CIN 2019 ===")
    url = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2019-CIN-RD-N%C2%BA-D000442-2019-DGIAMC.pdf"
    path = dl_pdf(url, "cin_2019_rd.pdf")
    text = pdf_to_text(path)
    a1 = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|Artículo\s)', text, re.DOTALL)
    if not a1: return print("CIN: No Artículo Primero")
    a1 = a1.group(1)
    
    lines = [l for l in a1.split('\n') if l.strip()]
    # Table: nombre | domicilio | proyecto | institución | monto
    entries = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s: i+=1; continue
        if s.upper() in ['PERSONA NATURAL', '(DNI)', 'DOMICILIO', 'TÍTULO DEL PROYECTO', 'TITULO DEL PROYECTO',
                         'ORGANIZACIÓN O INSTITUCIÓN QUE AVALA O RECONOCE EL PROYECTO',
                         'ORGANIZACION O INSTITUCION QUE AVALA O RECONOCE EL PROYECTO',
                         'MONTO DEL PREMIO', 'TÍTULO', 'PROYECTO']:
            i+=1; continue
        if 'S/' in s or 's/' in s: i+=1; continue
        if re.match(r'^[\d.,\s]+$', s): i+=1; continue
        
        # Name block (multi-line)
        name_parts = [s]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt: i+=1; break
            if nxt.upper() in ['LIMA', 'CALLAO', 'AREQUIPA', 'CUSCO', 'LA LIBERTAD', 'PUNO', 'LAMBAYEQUE',
                               'PIURA', 'CAJAMARCA', 'JUNÍN', 'JUNIN', 'SAN MARTÍN', 'SAN MARTIN',
                               'LORETO', 'AYACUCHO', 'HUÁNUCO', 'HUANUCO', 'ANCASH', 'TACNA', 'ICA',
                               'MADRE DE DIOS', 'PASCO', 'AMAZONAS', 'MOQUEGUA', 'TUMBES', 'UCAYALI',
                               'APURÍMAC', 'APURIMAC', 'HUANCAVELICA', 'LIMA REGIÓN', 'LIMA PROVINCIAS']:
                name_parts.append(nxt)
                i+=1
                break
            if re.match(r'^S/', nxt): break
            # Check if next is a region
            name_parts.append(nxt)
            i+=1
        
        full_name = ' '.join(name_parts).strip()
        if not full_name or len(full_name) < 5: continue
        region = ''
        # Check if last line was a region
        if name_parts and name_parts[-1].upper() in [r.upper() for r in ['LIMA','CALLAO','AREQUIPA','CUSCO','LA LIBERTAD','PUNO','LAMBAYEQUE','PIURA','CAJAMARCA','JUNÍN','SAN MARTÍN','LORETO','AYACUCHO','HUÁNUCO','ANCASH','TACNA','ICA','MADRE DE DIOS','PASCO','AMAZONAS','MOQUEGUA','TUMBES','UCAYALI','APURÍMAC','HUANCAVELICA']]:
            region = name_parts.pop()
        
        full_name = ' '.join(name_parts).strip()
        # Project: next few lines until S/
        proj_parts = []
        while i < len(lines):
            nxt = lines[i].strip()
            i += 1
            if not nxt: continue
            if re.match(r'^S/', nxt):
                amt = nxt
                break
            proj_parts.append(nxt)
        project = ' '.join(proj_parts).strip()
        # Amount
        am_match = re.search(r'S/[\.\s]*([\d\s\n]+[.,]\d{2})', text if 'amt' not in dir() else amt)
        am_str = am_match.group(1).replace('\n','').replace(' ','') if am_match else '0'
        amount = parse_amount(am_str) if am_match else 0
        
        entries.append({'name': full_name, 'region': region, 'project': project, 'amount': amount})
    
    print(f"  Found {len(entries)} CIN winners")
    for e in entries:
        print(f"    {e['name']} | {e['project']} | S/ {e['amount']:.2f}")
    
    # Insert into DB
    ca_id = ensure_concurso_anual(2019, 'CIN')
    rd_num = 'D000442-2019-DGIA/MC'
    fecha = '2019-10-01'
    
    c.execute("""INSERT OR IGNORE INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf)
        VALUES (?, ?, ?, 'fallo_final', ?)""", (ca_id, rd_num, fecha, url))
    res_id = c.lastrowid
    
    for e in entries:
        parts = e['name'].split()
        nombres = ' '.join(parts[:-2]) if len(parts) >= 3 else (parts[0] if parts else '')
        apellidos = ' '.join(parts[-2:]) if len(parts) >= 3 else (' '.join(parts[1:]) if len(parts) >= 2 else '')
        
        c.execute("""INSERT OR IGNORE INTO persona (tipo, nombres, apellidos, region)
            VALUES ('natural', ?, ?, ?)""", (nombres, apellidos, e['region']))
        
        c.execute("""SELECT id FROM persona WHERE tipo='natural' AND nombres=? AND apellidos=?
            AND (dni IS NULL OR dni = '') LIMIT 1""", (nombres, apellidos))
        per = c.fetchone()
        if not per: continue
        
        c.execute("INSERT OR IGNORE INTO obra (titulo) VALUES (?)", (e['project'],))
        proj = c.execute("SELECT id FROM obra WHERE titulo=?", (e['project'],)).fetchone()
        
        c.execute("""INSERT OR IGNORE INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
            VALUES (?, ?, ?, ?)""", (ca_id, per[0], proj[0] if proj else None, e['amount']))
        
        po = c.execute("""SELECT id FROM proyecto WHERE concurso_anual_id=? AND persona_beneficiaria_id=?""",
                       (ca_id, per[0])).fetchone()
        if po:
            c.execute("INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                      (po[0], res_id if res_id else 0))
    
    conn.commit()
    print(f"  Inserted {len(entries)} CIN proyectos")

# ============================================================
# 2. FO (CFO) 2019 — fix: remove corrupted, insert correct
# ============================================================
def extract_cfo_2019():
    print("\n=== CFO 2019 (Formación Audiovisual) ===")
    url = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2019%20CFO%20-%20Fallo%20final%20jurado.pdf"
    path = dl_pdf(url, "cfo_2019_ff.pdf")
    text = pdf_to_text(path)
    
    rd_match = re.search(r'RESOLUCION DIRECTORAL N[°º]\s*([\d\-A-Z/]+)', text)
    rd_num = rd_match.group(1).strip() if rd_match else ''
    fecha = '2019-09-10'
    
    # Categories of winners
    entries = [
        # Formación corta (11)
        ('VICTOR AUGUSTO MENDIVIL GARAVITO', 'LIMA', 'DOCUMENTAL DE OBSERVACION: UNA MIRADA DE AUTOR', 9875.00, True),
        ('TANIA MEDINA CARO', 'LIMA', 'TALLER DE ALTOS ESTUDIOS: MARKETING CINEMATOGRAFICO, MERCADOS Y VENTAS INTERNACIONALES', 14980.00, True),
        ('GUSTAVO ENRIQUE RIOS RUIZ', 'CALLAO', 'EL DIRECTOR DE FOTOGRAFIA', 8398.20, True),
        ('CARLA GABRIELA SALINAS AVILA', 'LIMA', 'TALLER INTERNACIONAL DOCUMENTAL DE OBSERVACIÓN, UNA MIRADA DE AUTOR', 15000.00, True),
        ('MIRELLA ALEXANDRA BELLIDO CASTRILLON', 'LIMA', 'EXPERTO EN PRO TOOLS - POST', 13086.00, True),
        ('BERENICE ESTEFANIA ADRIANZEN ZEGARRA', 'LIMA', 'TALLER INTERNACIONAL ESCRIBIR Y FILMAR PARA NIÑAS Y NIÑOS / TALLER DE ALTOS ESTUDIOS DE LA INFANCIA Y LA ADOLESCENCIA EN LA CREACIÓN CINEMATOGRÁFICA', 15000.00, True),
        ('SAMUEL ALFONSO URBINA TUME', 'PIURA', 'FILMMAKING CERTIFICATE', 15000.00, True),
        ('ROBERT GINO MORENO PLASENCIA', 'LIMA', 'THE ART OF EDITING', 15000.00, True),
        ('CHRISTIAN FERNANDO ÑECO BORNAZ', 'LAMBAYEQUE', 'TALLER INTERNACIONAL SONIDO DIRECTO INMERSIVO', 14000.00, True),
        ('FRANK PATRICK ABUGATTAS GUTIERREZ', 'LIMA', 'TALLER DE ALTOS ESTUDIOS: DIRECCIÓN DE ARTE', 10891.60, True),
        ('MAJA TILLMANN SALAS', 'LIMA REGIÓN (CAÑETE)', 'FRAME ACCESS, "FUTURE FOR RESTORATION OF AUDIOVISUAL MEMORY IN EUROPE"', 14850.00, True),
        # Formación larga (4)
        ('MARLLORY LORENA QUIO VALDIVIA', 'UCAYALI', 'CÁTEDRA DE PRODUCCIÓN - CURSO REGULAR', 33060.00, True),
        ('JOSE CARLOS VALENCIA ZAPATA', 'CALLAO', 'SEGUNDO AÑO DEL CURSO REGULAR DE LA EICTV - ESPECIALIDAD SONIDO', 31840.00, True),
        ('ALEJANDRA IVONNE ORE LUYO', 'LIMA', 'MASTER EN MONTAJE CINEMATOGRAFICO', 35000.00, True),
        ('JORGE EFRAIN BEDOYA SCHWARTZ', 'LIMA', 'POSGRADO EN ARCHIVO', 35000.00, True),
    ]
    
    # Remove existing corrupt CFO 2019 entries
    ca_id = get_concurso_anual_id(2019, 'CFO')
    if ca_id:
        existing = c.execute("SELECT id FROM proyecto WHERE concurso_anual_id=?", (ca_id,)).fetchall()
        for e in existing:
            c.execute("DELETE FROM proyecto_resolucion WHERE proyecto_id=?", (e[0],))
        c.execute("DELETE FROM proyecto WHERE concurso_anual_id=?", (ca_id,))
        c.execute("DELETE FROM resolucion WHERE concurso_anual_id=? AND tipo='fallo_final'", (ca_id,))
        conn.commit()
        print(f"  Removed {len(existing)} corrupt CFO entries")
    
    ca_id = ensure_concurso_anual(2019, 'CFO')
    
    c.execute("""INSERT OR IGNORE INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf)
        VALUES (?, ?, ?, 'fallo_final', ?)""", (ca_id, rd_num, fecha, url))
    res = c.execute("SELECT id FROM resolucion WHERE url_pdf=?", (url,)).fetchone()
    res_id = res[0] if res else None
    
    for name, region, project, amount, is_natural in entries:
        parts = name.split()
        nombres = ' '.join(parts[:-2]) if len(parts) >= 3 else (parts[0] if parts else '')
        apellidos = ' '.join(parts[-2:]) if len(parts) >= 3 else (' '.join(parts[1:]) if len(parts) >= 2 else '')
        
        c.execute("INSERT OR IGNORE INTO persona (tipo, nombres, apellidos, region) VALUES ('natural', ?, ?, ?)",
                  (nombres, apellidos, region))
        p = c.execute("""SELECT id FROM persona WHERE tipo='natural' AND nombres=? AND apellidos=?
            AND (dni IS NULL OR dni = '') LIMIT 1""", (nombres, apellidos)).fetchone()
        if not p: continue
        
        c.execute("INSERT OR IGNORE INTO obra (titulo) VALUES (?)", (project,))
        pr = c.execute("SELECT id FROM obra WHERE titulo=?", (project,)).fetchone()
        
        c.execute("""INSERT OR IGNORE INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
            VALUES (?, ?, ?, ?)""", (ca_id, p[0], pr[0] if pr else None, amount))
        
        po = c.execute("SELECT id FROM proyecto WHERE concurso_anual_id=? AND persona_beneficiaria_id=?",
                       (ca_id, p[0])).fetchone()
        if po and res_id:
            c.execute("INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                      (po[0], res_id))
    
    conn.commit()
    print(f"  Inserted {len(entries)} CFO entries")

# ============================================================
# 3. CFR 2019 — Largometrajes Ficción Regiones
# ============================================================
def extract_cfr_2019():
    print("\n=== CFR 2019 (Largometrajes Ficción Regiones) ===")
    url = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2019%20CFR%20-%20Fallo%20final%20del%20jurado.pdf"
    path = dl_pdf(url, "cfr_2019_ff.pdf")
    text = pdf_to_text(path)
    
    rd_match = re.search(r'RESOLUCION DIRECTORAL N[°º]\s*([\d\-A-Z/]+)', text)
    rd_num = rd_match.group(1).strip() if rd_match else ''
    
    winners = [
        ('CURUWINSI CINE E.I.R.L.', 'SAN MARTÍN', 'CELESTE Y EL PEQUEÑO SAJINO', 'CLAUDIA GUADALUPE BENITES SANCHEZ', 500000.00),
        ('CAMAL ESTUDIO CREATIVO S.R.L.', 'CUSCO', 'CERO', 'JORGE ANIBAL FLORES NAJAR', 500000.00),
        ('CONTACTO PRODUCCIONES E.I.R.L.', 'PUNO', 'ADIÓS CHIBOLO', 'FLAVIANO QUISPE CHAIÑA', 500000.00),
        ('CATACRESIS CINE E.I.R.L.', 'JUNÍN', 'ÉRASE UNA VEZ EN LOS ANDES', 'RÓMULO SULCA RICRA', 500000.00),
    ]
    
    ca_id = ensure_concurso_anual(2019, 'CPF')
    c.execute("""INSERT OR IGNORE INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf)
        VALUES (?, ?, '2019-09-26', 'fallo_final', ?)""", (ca_id, rd_num, url))
    res = c.execute("SELECT id FROM resolucion WHERE url_pdf=?", (url,)).fetchone()
    res_id = res[0] if res else None
    
    for rs, region, project, director, amount in winners:
        c.execute("INSERT OR IGNORE INTO persona (tipo, razon_social, region) VALUES ('juridica', ?, ?)",
                  (rs, region))
        p = c.execute("SELECT id FROM persona WHERE tipo='juridica' AND razon_social=? AND (ruc IS NULL OR ruc='')",
                      (rs,)).fetchone()
        if not p: continue
        
        c.execute("INSERT OR IGNORE INTO obra (titulo) VALUES (?)", (project,))
        pr = c.execute("SELECT id FROM obra WHERE titulo=?", (project,)).fetchone()
        
        c.execute("""INSERT OR IGNORE INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
            VALUES (?, ?, ?, ?)""", (ca_id, p[0], pr[0] if pr else None, amount))
        
        po = c.execute("SELECT id FROM proyecto WHERE concurso_anual_id=? AND persona_beneficiaria_id=?",
                       (ca_id, p[0])).fetchone()
        if po and res_id:
            c.execute("INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                      (po[0], res_id))
    
    conn.commit()
    print(f"  Inserted {len(winners)} CFR winners under CPF line")

# ============================================================
# 4. EDI 2019 — scanned PDFs via OCR
# ============================================================
def ocr_pdf(path, lang='spa'):
    """Convert PDF to text via pdftoppm + tesseract OCR."""
    base = path.replace('.pdf', '')
    pages = subprocess.run(['pdftoppm', '-png', '-r', '300', path, base], capture_output=True, timeout=60)
    page_files = sorted([f for f in os.listdir(TMP_DIR) if f.startswith(os.path.basename(base)) and f.endswith('.png')])
    
    text = ''
    for pf in page_files:
        pf_path = os.path.join(TMP_DIR, pf)
        txt_out = pf_path + '_ocr'
        env = os.environ.copy()
        env['TESSDATA_PREFIX'] = os.path.expanduser('~/.local/share/tessdata/')
        subprocess.run(['tesseract', pf_path, txt_out, '-l', lang], env=env, capture_output=True, timeout=60)
        txt_file = txt_out + '.txt'
        if os.path.exists(txt_file):
            with open(txt_file) as f:
                text += f.read() + '\n'
            os.unlink(txt_file)
        os.unlink(pf_path)
    return text

def extract_edi_2019():
    print("\n=== EDI 2019 (Estímulo a la Distribución) ===")
    ca_id = ensure_concurso_anual(2019, 'EDI')
    
    edi_urls = [
        f"https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2019%20CDI%20-%20Resoluci%C3%B3n%20beneficiario%20{i}.pdf"
        for i in range(1, 17)
    ]
    
    count = 0
    for url in edi_urls:
        fname = url.split('%20')[-1].replace('.pdf', '') + '.pdf'
        try:
            path = dl_pdf(url, f"edi_{fname}")
            text = ocr_pdf(path)
            if not text.strip():
                print(f"  OCR empty: {fname}")
                continue
            
            # Find RD number
            rd_match = re.search(r'RESOLUCION DIRECTORAL N[°º]?\s*([\d\-A-Z/]+)', text)
            rd_num = rd_match.group(1).strip() if rd_match else ''
            
            fecha_match = re.search(r'(\d+)\s+de\s+(\w+)\s+del\s+(\d{4})', text)
            fecha = ''
            if fecha_match:
                meses = {'enero':'01','febrero':'02','marzo':'03','abril':'04','mayo':'05','junio':'06',
                         'julio':'07','agosto':'08','septiembre':'09','setiembre':'09','octubre':'10',
                         'noviembre':'11','diciembre':'12'}
                mes = meses.get(fecha_match.group(2).lower(), '01')
                fecha = f"{fecha_match.group(3)}-{mes}-{fecha_match.group(1).zfill(2)}"
            
            # Find Artículo Primero section
            a1 = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo|SE RESUELVE)', text, re.DOTALL)
            if not a1: a1 = re.search(r'SE RESUELVE[:\s]+(.*?)(?:Artículo)', text, re.DOTALL)
            a1_text = a1.group(1) if a1 else text
            
            # Extract juridica info
            rs = ''
            ruc = ''
            rs_match = re.search(r'RUC\s*(?:N[°º]?\s*)?(\d{11})', a1_text)
            if rs_match:
                ruc = rs_match.group(1)
                rs_parts = []
                for line in reversed(a1_text[:a1_text.find(rs_match.group(0))].split('\n')):
                    s = line.strip()
                    if not s: break
                    if s.upper() in ['PERSONA JURÍDICA', 'PERSONA JURIDICA', '(RUC)', 'RUC']: continue
                    if 'S/' in s: continue
                    rs_parts.insert(0, s)
                rs = ' '.join(rs_parts).strip()
            
            if not rs or not ruc: continue
            
            # Amount
            am_match = re.search(r'S/[\.\s]*([\d\s]+[.,]\d{2})', a1_text)
            amount = parse_amount(am_match.group(1).replace('\n','').replace(' ','')) if am_match else 0
            
            # Project
            project = ''
            proj_match = re.search(r'PROYECTO[:\s]+(.+)', a1_text)
            if proj_match:
                project = proj_match.group(1).strip()
            else:
                # Find text between RUC and S/
                ruc_pos = a1_text.find(ruc) if ruc else -1
                if ruc_pos > 0:
                    after_ruc = a1_text[ruc_pos + len(ruc):]
                    am_pos = after_ruc.find('S/')
                    if am_pos > 0:
                        project = after_ruc[:am_pos].strip()
            
            if not project:
                project = f"EDI Distribution #{count+1}"
            
            c.execute("INSERT OR IGNORE INTO persona (tipo, razon_social, ruc) VALUES ('juridica', ?, ?)", (rs, ruc))
            p = c.execute("SELECT id FROM persona WHERE tipo='juridica' AND ruc=?", (ruc,)).fetchone()
            if not p: continue
            
            c.execute("INSERT OR IGNORE INTO obra (titulo) VALUES (?)", (project,))
            pr = c.execute("SELECT id FROM obra WHERE titulo=?", (project,)).fetchone()
            
            c.execute("""INSERT OR IGNORE INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
                VALUES (?, ?, ?, ?)""", (ca_id, p[0], pr[0] if pr else None, amount))
            
            # Resolution
            c.execute("""INSERT OR IGNORE INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf)
                VALUES (?, ?, ?, 'resolucion_beneficiario', ?)""", (ca_id, rd_num, fecha, url))
            res = c.execute("SELECT id FROM resolucion WHERE url_pdf=?", (url,)).fetchone()
            
            po = c.execute("SELECT id FROM proyecto WHERE concurso_anual_id=? AND persona_beneficiaria_id=?",
                           (ca_id, p[0])).fetchone()
            if po and res:
                c.execute("INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                          (po[0], res[0]))
            
            count += 1
            print(f"  EDI: {rs} -> {project} S/ {amount:.2f}")
            
        except Exception as e:
            print(f"  EDI error {fname}: {e}")
    
    conn.commit()
    print(f"  Total: {count} EDI entries")

# ============================================================
# 5. EPI 2019 — scanned PDFs via OCR
# ============================================================
def extract_epi_2019():
    print("\n=== EPI 2019 (Estímulo a la Promoción Internacional) ===")
    ca_id = ensure_concurso_anual(2019, 'EPI')
    
    epi_pdfs = [
        {'num': 1, 'rd': 'D000070-2019-DGIA/MC'},
        {'num': 2, 'rd': 'D000071-2019-DGIA/MC'},
        {'num': 3, 'rd': 'D000072-2019-DGIA/MC'},
        {'num': 4, 'rd': 'D000075-2019-DGIA/MC'},
        {'num': 5, 'rd': 'D000076-2019-DGIA/MC'},
        {'num': 6, 'rd': 'D000081-2019-DGIA/MC'},
        {'num': 7, 'rd': 'D000082-2019-DGIA/MC'},
        {'num': 8, 'rd': 'D000120-2019-DGIA/MC'},
        {'num': 9, 'rd': 'D000125-2019-DGIA/MC'},
        {'num': 10, 'rd': 'D000127-2019-DGIA/MC'},
        {'num': 11, 'rd': 'D000128-2019-DGIA/MC'},
        {'num': 12, 'rd': 'D000129-2019-DGIA/MC'},
        {'num': 13, 'rd': 'D000130-2019-DGIA/MC'},
        {'num': 14, 'rd': 'D000131-2019-DGIA/MC'},
        {'num': 15, 'rd': 'D000132-2019-DGIA/MC'},
        {'num': 16, 'rd': 'D000133-2019-DGIA/MC'},
        {'num': 17, 'rd': 'D000136-2019-DGIA/MC'},
        {'num': 18, 'rd': 'D000139-2019-DGIA/MC'},
        {'num': 19, 'rd': 'D000140-2019-DGIA/MC'},
        {'num': 20, 'rd': 'D000147-2019-DGIA/MC'},
        {'num': 21, 'rd': 'D000148-2019-DGIA/MC'},
        {'num': 22, 'rd': 'D000149-2019-DGIA/MC'},
        {'num': 23, 'rd': 'D000150-2019-DGIA/MC'},
        {'num': 24, 'rd': 'D000151-2019-DGIA/MC'},
        {'num': 25, 'rd': 'D000155-2019-DGIA/MC'},
        {'num': 26, 'rd': 'D000156-2019-DGIA/MC'},
        {'num': 27, 'rd': 'D000157-2019-DGIA/MC'},
        {'num': 28, 'rd': 'D000158-2019-DGIA/MC'},
        {'num': 29, 'rd': 'D000159-2019-DGIA/MC'},
        {'num': 30, 'rd': 'D000164-2019-DGIA/MC'},
        {'num': 31, 'rd': 'D000419-2019-DGIA/MC'},
    ]
    
    count = 0
    for epi in epi_pdfs:
        num = epi['num']
        url = f"https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2019%20Promoci%C3%B3n%20Internacional%20-%20Resoluci%C3%B3n%20beneficiario%20{num}.pdf"
        fname = f"epi_benef_{num}.pdf"
        
        try:
            path = dl_pdf(url, fname)
            text = ocr_pdf(path)
            if not text.strip():
                print(f"  EPI {num}: OCR empty"); continue
            
            # Natural person EPI
            a1 = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo|SE RESUELVE)', text, re.DOTALL)
            a1_text = a1.group(1) if a1 else text
            
            # Find DNI
            dni = ''
            dn_match = re.search(r'(\d{8})', a1_text)
            if dn_match: dni = dn_match.group(1)
            
            # Name
            name = ''
            lines = a1_text.split('\n')
            for i, line in enumerate(lines):
                if 'DNI' in line.upper() or '(DNI)' in line:
                    for j in range(i-1, -1, -1):
                        s = lines[j].strip()
                        if not s or s.upper() in ['PERSONA NATURAL', 'NATURAL']: break
                        if re.match(r'^[\d\s,./()-]+$', s): continue
                        name_parts = [s]
                        for k in range(j+1, i):
                            s2 = lines[k].strip()
                            if s2 and not re.match(r'^[\d\s,./()-]+$', s2):
                                name_parts.append(s2)
                        name = ' '.join(name_parts).strip()
                        break
                    break
            
            if not name: continue
            
            # Amount
            am_match = re.search(r'S/[\.\s]*([\d\s]+[.,]\d{2})', a1_text)
            amount = parse_amount(am_match.group(1).replace('\n','').replace(' ','')) if am_match else 0
            
            # Region
            region = ''
            for r in ['LIMA','CALLAO','AREQUIPA','CUSCO','LA LIBERTAD','PUNO','LAMBAYEQUE',
                       'PIURA','CAJAMARCA','JUNÍN','SAN MARTÍN','LORETO','AYACUCHO','HUÁNUCO',
                       'ANCASH','TACNA','ICA','MADRE DE DIOS','PASCO','AMAZONAS','MOQUEGUA',
                       'TUMBES','UCAYALI','APURÍMAC','HUANCAVELICA']:
                if r in a1_text.upper():
                    region = r.capitalize()
                    break
            
            # Project
            project = f"Promoción Internacional #{num}"
            proj_match = re.search(r'EVENTO INTERNACIONAL[:\s]+(.+?)(?:MONTO|S/)', a1_text, re.DOTALL)
            if proj_match:
                project = proj_match.group(1).strip().replace('\n', ' ')
            else:
                event_match = re.search(r'Evento:\s*(.+?)(?:\.\s|$)', a1_text)
                if event_match: project = event_match.group(1).strip()
            
            parts = name.split()
            nombres = ' '.join(parts[:-2]) if len(parts) >= 3 else (parts[0] if parts else '')
            apellidos = ' '.join(parts[-2:]) if len(parts) >= 3 else (' '.join(parts[1:]) if len(parts) >= 2 else '')
            
            c.execute("INSERT OR IGNORE INTO persona (tipo, nombres, apellidos, dni, region) VALUES ('natural', ?, ?, ?, ?)",
                      (nombres, apellidos, dni, region))
            
            p = c.execute("SELECT id FROM persona WHERE tipo='natural' AND dni=?", (dni,)).fetchone()
            if not p: continue
            
            c.execute("INSERT OR IGNORE INTO obra (titulo) VALUES (?)", (project,))
            pr = c.execute("SELECT id FROM obra WHERE titulo=?", (project,)).fetchone()
            
            c.execute("""INSERT OR IGNORE INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
                VALUES (?, ?, ?, ?)""", (ca_id, p[0], pr[0] if pr else None, amount))
            
            c.execute("""INSERT OR IGNORE INTO resolucion (concurso_anual_id, numero, tipo, url_pdf)
                VALUES (?, ?, 'resolucion_beneficiario', ?)""", (ca_id, epi['rd'], url))
            res = c.execute("SELECT id FROM resolucion WHERE url_pdf=?", (url,)).fetchone()
            
            po = c.execute("SELECT id FROM proyecto WHERE concurso_anual_id=? AND persona_beneficiaria_id=?",
                           (ca_id, p[0])).fetchone()
            if po and res:
                c.execute("INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                          (po[0], res[0]))
            
            count += 1
            print(f"  EPI {num}: {name} (DNI {dni}) -> {project} S/ {amount:.2f}")
            
        except Exception as e:
            print(f"  EPI {num} error: {e}")
    
    conn.commit()
    print(f"  Total: {count} EPI entries")

# == Main ==
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', nargs='+', default=['cin','cfo','cfr','edi','epi'])
    args = parser.parse_args()
    
    if 'cin' in args.steps: extract_cin_2019()
    if 'cfo' in args.steps: extract_cfo_2019()
    if 'cfr' in args.steps: extract_cfr_2019()
    if 'edi' in args.steps: extract_edi_2019()
    if 'epi' in args.steps: extract_epi_2019()
    
    conn.close()
    print("\nDone.")
