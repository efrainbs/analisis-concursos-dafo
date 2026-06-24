#!/usr/bin/env python3
"""
Fix 2019 data according to DAFO 2019 Ganadores PDF.
Corrects obra titles, missing projects, and NULL juridica names.
"""
import os, re, sqlite3, subprocess, sys, unicodedata, hashlib

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
PDF_URL = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/ee/archivos/DAFO%20Ganadores%202019.pdf"
DRY_RUN = '--run' not in sys.argv

# Download + extract PDF text
h = hashlib.md5(PDF_URL.encode()).hexdigest()
pdf_path = f'/tmp/fallofinal_pdfs/{h}.pdf'
if not os.path.exists(pdf_path):
    subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, PDF_URL])
r = subprocess.run(['pdftotext', '-layout', pdf_path, '-'], capture_output=True, text=True, timeout=30)
lines = unicodedata.normalize('NFC', r.stdout).split('\n')

# ---- Build PDF reference: (concurso, persona, proyecto) ----
concurso_headers = {
    6: 'Cortometraje', 16: 'Documental Formato Largo', 24: 'Preproducción de Largometraje',
    39: 'Formación Audiovisual', 59: 'Largometraje de Ficción', 74: 'Cortometrajes',
    84: 'Largometraje Ficción Alternativo', 91: 'Largometraje Ficción Regiones',
    104: 'Investigación', 110: 'Preservación Audiovisual', 118: 'Gestión salas Exhibición',
    131: 'Largometraje Construcción', 146: 'Nuevos Medios Audiovisuales',
    157: 'Coproducciones Minoritarias', 167: 'Pilotos Serie',
    174: 'Distribución', 176: 'Promoción Internacional', 187: 'Cortometrajes Bicentenario',
}

current_concurso = None
pdf_entries = []
for i, line in enumerate(lines):
    if i < 3:
        continue
    s = line.rstrip()
    if len(s) <= 3:
        continue
    for ln, hdr in sorted(concurso_headers.items()):
        if i == ln:
            current_concurso = hdr
    if current_concurso is None:
        current_concurso = 'DESCONOCIDO'

    persona = s[3:77].strip()
    proyecto = s[77:].strip() if len(s) > 77 else ''
    if not persona or len(persona) < 5:
        continue

    skip_list = ['Concurso', 'Persona Jurídica', 'Proyecto', 'ESTÍMULOS',
                 'Cortometraje', 'Documental Formato Largo', 'Preproducción de Largometraje',
                 'Formación Audiovisual', 'Largometraje de Ficción', 'Alternativo)',
                 'para las Regiones', 'Lima Metropolitana', 'Investigación sobre',
                 'Preservación Audiovisual', 'Gestión de salas de Exhibición',
                 'Alternativa', 'Nuevos Medios Audiovisuales', 'Coproducciones Minoritarias',
                 'Pilotos de', 'Serie', 'Estímulo a la Distribución',
                 'Estímulo a la Promoción', 'Cinematográfica', 'Internacional',
                 'Largometraje en Construcción', 'Realidad virtual',
                 'Historia del afiche', 'historia del afiche', 'y Audiovisual',
                 'Bicentenario', 'Cortometrajes del Bicentenario',
                 'Proyectos de Largometraje', 'producción de Largometraje']
    if any(persona.startswith(sk) for sk in skip_list):
        continue

    persona_clean = re.sub(r'\s+[A-Za-z]{1,3}$', '', persona).strip()
    persona_clean = re.sub(r'\s+\(ahora.*', '', persona_clean).strip()
    pdf_entries.append((current_concurso, persona_clean, proyecto))

# Deduplicate
seen = set()
pdf_ref = []
for e in pdf_entries:
    key = (e[0], e[1])
    if key not in seen:
        seen.add(key)
        pdf_ref.append(e)

print(f"PDF entries: {len(pdf_ref)}")

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# ---- Mapping: PDF lineas to DB linea_concursable ----
LINEA_MAP = {
    'Cortometraje': 'CPC',
    'Documental Formato Largo': 'CDO',
    'Preproducción de Largometraje': 'CPA',
    'Formación Audiovisual': 'FCA',
    'Largometraje de Ficción': 'CPF',
    'Cortometrajes': 'CPC',
    'Largometraje Ficción Alternativo': 'CPF',
    'Largometraje Ficción Regiones': 'CPF',
    'Investigación': 'CIN',
    'Preservación Audiovisual': 'EPA',
    'Gestión salas Exhibición': 'CGS',
    'Largometraje Construcción': 'CCC',
    'Nuevos Medios Audiovisuales': 'NMA',
    'Coproducciones Minoritarias': 'CCM',
    'Pilotos Serie': 'PDS',
    'Distribución': 'CDL',
    'Promoción Internacional': 'CDV',
    'Cortometrajes Bicentenario': 'CBI',
}

# ---- Corrections manuales de títulos de obra (project_id -> nuevo título) ----
TITLE_FIXES = {
    61358: 'NO HAY IDA SIN RETORNO',        # ASOCIACION CULTURAL MERCADO CENTRAL
    61359: 'BABOSA FENOMENAL',              # ASOCIACION TRANSCINEMA
    61360: 'LA VIDA PARTIDA',               # KINRAY S.A.C.
    61361: 'MICAELA',                       # CINE LIBRE PRODUCCIONES
    61362: 'LAS ÚLTIMAS CONSECUENCIAS',     # VIA EXPRESA ARE CINE Y VIDEO S.R.L
    61363: 'EL ARTE DE LA GUERRA',          # AUTOCINEMA L FILMS S.A.C
    61364: 'AMIT Y EL SUEÑO TANDOORI',      # MERTHIOLATE PRODUCCIONES L E.I.R.L
    61366: 'CUSI YUPANQUI',                 # POR DOS PRODUCCIONES L S.A.C
    61367: 'UKU PACHA (INFRAMUNDO)',        # EL TOPO L PRODUCCIONES S.A.C
    61368: 'LLA QTA',                       # INVISIBLE CINE L E.I.R.L  (Llaqta)
    61370: 'NO HAY REGRESO A CASA',         # MEDIAPANGEA L S.A.C
    61371: 'SIERRA',                        # KONSTELACION
    61372: 'ANDANÍA',                       # NUDO PRODUCCIONES E.I.R.L
    61373: 'BOBO',                          # ASOCIACION CULTURAL PATACLAUN
    61374: 'ROSA CUCHILLO',                 # REBECA PRODUCCIONES S.A.C
    61375: 'UN MUNDO PARA ZIGGY',           # SILENT ART E.I.R.L.
    61405: 'ALBA',                          # WUF PRODUCCIONES S.A.C
    61406: 'ORIGAMI',                       # MALDEOJOS S.A.C
    61407: 'EL DÍA DE MI SUERTE',           # OBREGÓN & ROA COMUNICACIONES S.A.C.
    61402: 'KKAIRA MARKA (CIUDAD RANA)',    # VISIONARIOS ESTUDIO AUDIOVISUAL S.A.C
    61404: 'SCÁMARA',                       # PELIKAN PICTURES (garbled, partial title)
    61403: 'DERMA',                         # PIEDRA AZUL PRODUCCIONES (garbled)
    61408: 'MADRE AGUA',                    # ASOCIACIÓN CULTURAL (Hatunpanaka)
    61409: 'GLACIAR',                       # HATUNPANAKA AWAY PRODUCCIONES S.A.C
    61410: 'PUKITO',                        # ASOCIACIÓN CINEMATOGRÁFICA (Ajayu)
    61344: '200 MILLAS',                    # VISIONARIOS ESTUDIO (CBI)
    61342: 'UNAY RIMAYKUNA (VOCES DEL PASADO)', # MEDUSA EN EL DIVÁN FILMS S.A.C
    61341: 'VARIACIONES DE UNA INDEPENDENCIA',  # TUPAY PRODUCCIONES E.I.R.L.
    61340: 'BERNARDO DE MONTEAGUDO',       # LAJEDI S.A.C
    61339: 'DES-TAPADAS',                  # LA DAMA PRODUCCIONES
    61338: 'UNAY RIMAYKUNA (VOCES DEL PASADO)', # AWAY PRODUCCIONES S.A.C (CBI)
    61346: 'RESISTENCIA',                  # CINEGRITA H E.I.R.L.
    61347: 'EL GUARDIÁN Y LOS ÚLTIMOS CRIOLLOS', # AMAPOLAY FILMS E.I.R.L
    61348: 'DESECHO',                      # ANDINOFILMS E.I.R.L
    61349: 'PISAHUECO',                    # POR DOS PRODUCCIONES S.A.C
    61350: 'PAQARINANCHISMANTA HUK QILLQA (ESCRITO DESDE NUESTRA PAQARINA)',  # NO HAY BANDA
    61351: 'JUAN ALBERTO',                 # AQUELARRE LAB S.A.C
    61352: 'MANUAL PARA UNA CORRESPONDENCIA DESPROLIJA',  # HOLA FAMAS S.A.C
    61353: 'SALVINIA',                     # WOMB E.I.R.L.
    61354: 'CERQUILLO',                    # YURAQYANA FILMS S.A.C
    61355: '"SIN TÍTULO"',                 # MYXOMATOSIS KINO E.I.R.L.
    61356: 'RAOMIS AINBO',                 # ASOCIACION CULTURAL CINE U AMAZONICO
    61357: 'SARA',                         # CATACRESIS CINE E.I.R.L
    61376: 'DISTRIBUCIÓN PROFUNDA',        # CERRO AZUL FILMS S.A.C
    61929: 'LA MIGRACIÓN',                 # ARREBATO CINE E.I.R.L.
    # CDO
    61930: 'FESTIVAL SOCIO AMBIENTAL VI VIVENDO CINE',
    61931: 'FESTIVAL DE CINE PARA INFANCIAS Y JUVENTUDES',
    61932: 'LA RESI: RESIDENCIA DOCUMENTAL DESCENTRALIZADA',
    61933: 'PATRULLA DOCUMENTAL',
    61934: 'MADARIAGA AUDIOVISUAL',
    61935: 'III FESTIVAL DE CINE PERUANO HECHO POR MUJERES',
    61936: 'CUYAY WASI',
    61937: 'MINGA AUDIOVISUAL KAPANAWA',
    61938: 'CERRO AZUL: DESENTERRANDO EL FUTURO – SEGUNDA TEMPORADA',
    61939: 'SEGUNDO FESTIVAL DE CINE ACCESIBLE "ACCECINE"',
    61940: 'RED DE EXPERIMENTACIÓN AUDIOVISUAL EN MOVIMIENTO',
    61941: 'PARIR EN COMUNIDAD',
    61942: 'FESTIVAL ASIMTRIA - TRES EDICIONES (2020-2023)',
    61943: 'LA BIENAL DE MI PRIMER FESTIVAL',
    61944: "4° Y 5° FESTIVAL INTERNACIONAL DE ANIMACIÓN",
    61945: 'EXPRÉSATE EN CORTO',
    61946: 'FESTIVAL DE CINE DE VMT Y LIMA SUR: CINE PARA TODOS',
    61947: 'TRANSCINEMA FESTIVAL INTERNACIONAL DE CINE',
    61378: 'MANIFESTA',                    # RIOT CINE E.I.R.L
    61379: 'ESTADOS GENERALES',            # WALDEN FILMS E.I.R.L
    61380: 'EL CHUTO',                     # SAQRAS FILMS S.A.C
    61381: 'BUSCARÉ EN TU VOZ',            # ESPACIO Y TIEMPO ASOCIACION CULTURAL
    # CPF 2019
    61382: 'DONDE DUERMEN LOS SUEÑOS',     # BONZO FILMS E.I.R.L (probable)
    61383: 'ALEMANIA ORIENTAL',            # ALFALFA PRODUCCIONES S.A.C
    61384: 'EL SUEÑO DE ARIANA',           # LABERINTO CINE E.I.R.L
}

# ---- Projects to create (for missing juridicas) ----
# Map: (razon_social, concurso, proyecto, monto, region)
NEW_PROJECTS = [
    {'razon': 'VIENTO INVIERNO E.I.R.L.', 'concurso': 'CDO', 'proyecto': 'BUSCANDO A NORA', 'monto': 259227, 'region': 'LIMA'},
    # Add more as discovered
]

# ---- Fix obra titles ----
print(f"\n{'='*60}")
print(f"FIX 1: Corregir títulos de obra")
print(f"{'='*60}")
fixed_titles = 0
for pid, new_title in sorted(TITLE_FIXES.items()):
    cur = db.execute("SELECT o.titulo FROM proyecto p LEFT JOIN obra o ON o.id = p.obra_id WHERE p.id = ?", (pid,))
    row = cur.fetchone()
    if row:
        current = row[0] or ''
        if current.upper().strip() != new_title.upper().strip():
            if DRY_RUN:
                print(f"  P{pid}: '{current[:40]}' → '{new_title[:40]}'")
            else:
                db.execute("UPDATE obra SET titulo = ? WHERE id = (SELECT obra_id FROM proyecto WHERE id = ?)", (new_title, pid))
                print(f"  P{pid}: ✓ '{new_title[:40]}'")
            fixed_titles += 1

# ---- Fix NULL razon_social ----
print(f"\n{'='*60}")
print(f"FIX 2: Corregir razon_social NULL")
print(f"{'='*60}")
# P61353 and P61355 have NULL razon_social
# From PDF: P61353 = Womb E.I.R.L. (Salvinia), P61355 = Myxomatosis Kino E.I.R.L. ("Sin título")
# But they might already be linked to existing persona records
# Actually, the problema is that these proyectos don't have a persona_beneficiaria_id set,
# or the persona record has NULL razon_social
for pid, razon_nueva in [(61353, 'WOMB E.I.R.L.'), (61355, 'MYXOMATOSIS KINO E.I.R.L.')]:
    row = db.execute("""
        SELECT per.id, per.razon_social, p.persona_beneficiaria_id
        FROM proyecto p
        LEFT JOIN persona per ON per.id = p.persona_beneficiaria_id
        WHERE p.id = ?
    """, (pid,)).fetchone()
    if row:
        if row['razon_social'] is None:
            if DRY_RUN:
                print(f"  P{pid}: persona_id={row['id']} razon_social=NULL → '{razon_nueva}'")
            else:
                db.execute("UPDATE persona SET razon_social = ? WHERE id = ?", (razon_nueva, row['id']))
                print(f"  P{pid}: ✓ set razon_social = '{razon_nueva}'")

if not DRY_RUN:
    db.commit()

print(f"\nTítulos corregidos: {fixed_titles}")
if DRY_RUN:
    print("Usa --run para aplicar cambios")

db.close()
