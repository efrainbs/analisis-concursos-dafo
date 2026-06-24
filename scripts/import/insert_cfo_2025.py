import sqlite3, sys, os, re

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
dry_run = '--run' not in sys.argv

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

if dry_run:
    print("=== DRY RUN (pasa --run para ejecutar) ===\n")

CA_ID = 7  # CFO 2025
RESOLUCION_ID = None  # No resolution PDF available - linking skipped

# Raw OCR data: (nombre_apellidos, proyecto, region)
RAW_BENEFICIARIOS = [
    ("ARELLANO VILLEGAS, JUAN GABRIEL", "TALLER DE DIRECCION DE PRODUCCION: DISENO DE PRESUPUESTOS, CADENA DE DERECHOS Y GESTION EMPRESARIA", "LAMBAYEQUE"),
    ("AVELLANEDA HUAMAN, JUAN LEONARDO", "DIPLOMADO INTENSIVO DE FOTOGRAFIA CINEMATOGRAFICA", "JUNIN"),
    ("BRUNO MORALES, MAGALI BETSABE", "TALLER INTERNACIONAL: FINANCIACION DE CINE INDEPENDIENTE: DOSSIER, PITCH, MERCADOS Y COPRODUCCIONES", "LIMA"),
    ("CARDENAS FIGUEROA, FRIDA VICTORIA", "TALLER DE ALTOS ESTUDIOS: DISENO DE VESTUARIO PARA CINE Y AUDIOVISUAL", "PIURA"),
    ("CHOQUEHUAYTA VALDERRAMA, SAMUEL JOEL", "TALLER DE ALTOS ESTUDIOS DISENO DE VESTUARIO PARA CINE Y AUDIOVISUAL", "AREQUIPA"),
    ("CONDE RODRIGUEZ, VANESSA MARIVEL", "TALLER INTERNACIONAL DIRECCION DE PRODUCCION DISENO DE PRESUPUESTOS", "PIURA"),
    ("CUEVA YAIPEN, VIRNA VALERIA", "POSTGRADO DE DIRECCION DE FOTOGRAFIA", "JUNIN"),
    ("FERNANDEZ CANO, FERNAN GUILLERMO", "TALLER DE ALTA ESPECIALIZACION Y POST-GRADO: GUIONISTAS", "AREQUIPA"),
    ("FUENTES ARQQUE, MIGUEL ANGEL", "DIPLOMADO PRACTICO EN DIRECCION DE FOTOGRAFIA", "CUSCO"),
    ("GASTULO LADINES, NAYARITH LLASSIEL", "TALLER INTERNACIONAL DE REALIZACION DE DOCUMENTALES", "LAMBAYEQUE"),
    ("HUAMAN FLORES, CARMEN DE LOS ANGELES", "TALLER DE ALTA ESPECIALIZACION Y POST-GRADO: GUIONISTAS", "CUSCO"),
    ("HUAMAN MATEO, MIGUEL ANGEL", "TALLER INTERNACIONAL REALIZACION DOCUMENTAL", "LORETO"),
    ("HUAYTA PACSI, ELVIS", "POSTGRADO EN DIRECCION DE FOTOGRAFIA", "AREQUIPA"),
    ("LOPEZ ALCALDE, JAIR MAHOMET", "DIPLOMADO: 1ER ASISTENTE DE CAMARA", "LAMBAYEQUE"),
    ("MANRIQUE CERVANTES, WALTER FREDDY", "DIPLOMADO INTENSIVO DE PRODUCCION EJECUTIVA", "AREQUIPA"),
    ("MARADIEGUE MONTARO, WALTHER AUGUSTO", "TALLER INTERNACIONAL DE APRECIACION DEL LENGUAJE AUDIOVISUAL", "LAMBAYEQUE"),
    ("ORCADA VILLALVA, EDUARDO", "TALLER DE ALTA ESPECIALIZACION Y POST-GRADO: GUIONISTAS", "SIN DATO"),
    ("PUMALUNTO SOTO, DIANA KAROL", "DIPLOMADO EN STOP MOTION", "CUSCO"),
    ("RAMOS APAZA, LUIS JEAMPIERRE", "TALLER INTERNACIONAL ESCENAS EN ACCION: PRUEBA Y MEJORA", "AREQUIPA"),
    ("RICRA MIRANDA, RODRIGO FRANCO", "TALLER INTERNACIONAL: FINANCIACION DE CINE INDEPENDIENTE", "LIMA"),
    ("ROLANDO JARA, MARCIO ANDRE", "DIPLOMADO INTENSIVO DE FOTOGRAFIA CINEMATOGRAFICA", "JUNIN"),
    ("SALAS GUTIERREZ, ANA CLAUDIA", "TALLER INTERNACIONAL GUION DE LARGOMETRAJES", "PIURA"),
    ("TAPAYURI SALAZAR, ROLAN LUIS", "TALLER INTERNACIONAL REALIZACION DOCUMENTAL", "HUANUCO"),
    ("TERAN AYQUIPA, MERY LYCIA", "TALLER INTERNACIONAL DIRECCION DE PRODUCCION: DISENO DE PRESUPUESTOS", "LIMA"),
    ("VELA SAAVEDRA, ROGER REYNALDO", "TALLER INTERNACIONAL DE REALIZACION DOCUMENTAL", "LORETO"),
    ("AGREDA MEDRANO, ALEJANDRO MANUEL", "MASTER VFX Y COMPOSICION CON HOUDINI Y NUKE PARA CINE Y AUDIOVISUAL", "SIN DATO"),
    ("AGUILAR SAMANEZ, NICOLAS ALEXANDER", "MASTER DE DIRECCION Y PRODUCCION DE VIDEOCLIPS", "AREQUIPA"),
    ("ALTAMIRANO SALAZAR, STEPHANIE GERALDINE", "MASTER EN DIRECCION DE FOTOGRAFIA CINEMATOGRAFICA", "LIMA"),
    ("ARIAS RUIZ, SEBASTIAN ALEXIS", "MASTER UNIVERSITARIO EN ESTUDIOS AVANZADOS EN CINE", "PIURA"),
    ("BOLIVAR ESPINOZA, CARELLIA DALESKA", "MASTER DE CINE DOCUMENTAL", "LIMA"),
    ("GONAZ DEL AGUILA, CLAUDIA STEFANY", "MASTER DE DIRECCION DE ARTE", "LORETO"),
    ("HERRERA CLAPERS, SANTIAGO RAMON", "DIPLOMA EN ANIMACION", "CUSCO"),
    ("HIGUERAS CHICOT, MANUEL ALFONSO", "MASTER DE CINE DOCUMENTAL", "LIMA"),
    ("HUMPIRI PUMA, LEONILDA", "ESPECIALIDAD DE PRODUCCION-PRIMER ANO DEL CURSO REGULAR", "AREQUIPA"),
    ("LADRON DE GUEVARA COCA, JOSEPH SAMUEL", "MASTER EN CRITICA CINEMATOGRAFICA", "ICA"),
    ("LARA CAMERE, JAVIER WILFREDO", "MASTER EN DISTRIBUCION Y NEGOCIO EN LA INDUSTRIA AUDIOVISUAL", "LIMA"),
    ("LOZANO NUNEZ, NARDA KIARA", "MASTER UNIVERSITARIO EN ESTUDIOS DE CINE Y CULTURAS", "CAJAMARCA"),
    ("MELGAR CARI, MILAGROS GINA", "MAESTRIA: ESCRITURA CREATIVA DE GUION AUDIOVISUAL", "AREQUIPA"),
    ("MOLINA BERNALES, TANYA MARLY", "DIPLOMADO PRODUCCION CREATIVA Y SHOWRUNNER", "AREQUIPA"),
    ("SAN MIGUEL BERAUN, ROCIO LUCIA", "CURSO REGULAR - ESPECIALIZACION EN FOTOGRAFIA", "LIMA"),
    ("TALLEDO ROJAS, JORGE ALEXANDER", "FICCLAB (LAB-MASTER) - CATEDRA DE ALTOS ESTUDIOS DE FICCION", "SIN DATO"),
    ("TICERAN CABRERA, BETZABE MICOL", "MASTER EN COLOR Y ETALONAJE DIGITAL", "HUANUCO"),
    ("VALENTI ALATTA, RODRIGO ENRIQUE", "2DO ANO DIPLOMATURA DE DIRECCION DE CINE", "LIMA"),
]

def classify_monto(titulo):
    upper = titulo.upper()
    larga_keywords = ['MASTER', 'MAESTRIA', 'POSTGRADO', 'ESPECIALIDAD', 'DIPLOMATURA',
                      'DIPLOMA', 'CURSO REGULAR', 'CATEDRA']
    for kw in larga_keywords:
        if kw in upper:
            return 45000.0, 'Formación larga'
    return 25000.0, 'Formación corta'

def find_or_create_persona(apellidos, nombres):
    cur.execute("SELECT id FROM persona WHERE nombres = ? AND apellidos = ? AND tipo = 'natural'", (nombres, apellidos))
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM persona")
    nid = cur.fetchone()[0]
    cur.execute("INSERT INTO persona (id, tipo, nombres, apellidos) VALUES (?, 'natural', ?, ?)", (nid, nombres, apellidos))
    conn.commit()
    return nid

def find_or_create_obra(titulo):
    cur.execute("SELECT id FROM obra WHERE titulo = ?", (titulo,))
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM obra")
    nid = cur.fetchone()[0]
    cur.execute("INSERT INTO obra (id, titulo) VALUES (?, ?)", (nid, titulo))
    conn.commit()
    return nid

def ensure_modalidad(nombre):
    """Find or create modalidad for CFO 2025 (CA_ID=7)."""
    cur.execute("SELECT id FROM modalidad WHERE concurso_anual_id = ? AND nombre = ?", (CA_ID, nombre))
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM modalidad")
    nid = cur.fetchone()[0]
    # Estimate budget from similar modalidades in previous years
    budget = 45000.0 if 'larga' in nombre else 25000.0
    cur.execute("INSERT INTO modalidad (id, concurso_anual_id, nombre, presupuesto_asignado) VALUES (?, ?, ?, ?)",
                (nid, CA_ID, nombre, budget))
    conn.commit()
    return nid

# Create modalidades
mod_larga_id = ensure_modalidad('Formación larga')
mod_corta_id = ensure_modalidad('Formación corta')
print(f"Modalidades: larga={mod_larga_id}, corta={mod_corta_id}")

total = 0
inserted_ids = []
for i, (nombre_completo, proyecto, region) in enumerate(RAW_BENEFICIARIOS, 1):
    # Parse name
    parts = nombre_completo.split(',', 1)
    if len(parts) == 2:
        apellidos = parts[0].strip()
        nombres = parts[1].strip()
    else:
        apellidos = nombre_completo
        nombres = ''

    monto, tipo = classify_monto(proyecto)
    mod_id = mod_larga_id if tipo == 'Formación larga' else mod_corta_id

    if dry_run:
        print(f"  {i}. {nombres} {apellidos} — {proyecto[:60]} — {region} — S/{monto:.0f} ({tipo})")
        total += 1
        continue

    # Create records
    persona_id = find_or_create_persona(apellidos, nombres)
    if region != 'SIN DATO':
        cur.execute("UPDATE persona SET region = ? WHERE id = ?", (region, persona_id))

    obra_id = find_or_create_obra(proyecto)

    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM proyecto")
    proy_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO proyecto (id, concurso_anual_id, modalidad_id, persona_beneficiaria_id, obra_id, monto_otorgado, estado)
        VALUES (?, ?, ?, ?, ?, ?, 'beneficiario')
    """, (proy_id, CA_ID, mod_id, persona_id, obra_id, monto))

    if RESOLUCION_ID:
        cur.execute("INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                    (proy_id, RESOLUCION_ID))

    conn.commit()
    inserted_ids.append(proy_id)
    total += 1
    if total % 10 == 0:
        conn.commit()

if dry_run:
    print(f"\n=== DRY RUN: {total} beneficiarios listos ===")
else:
    print(f"\n=== Insertados: {total} proyectos ===")
    print(f"IDs: {inserted_ids}")

conn.close()
