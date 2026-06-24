#!/usr/bin/env python3
"""Insert missing EPA 2021 RDs (603-611) into the database."""

import sqlite3, os

DB_PATH = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Get concurso_anual_id for EPA 2021
ca_id = c.execute("""
    SELECT ca.id FROM concurso_anual ca
    JOIN convocatoria c ON c.id = ca.convocatoria_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    WHERE c.anio = 2021 AND lc.codigo = 'EPA'
""").fetchone()[0]

entries = [
    (603, '000603-2021-DGIA/MC', 'PONTIFICIA UNIVERSIDAD CATÓLICA DEL PERÚ',
     'DIGITALIZACIÓN Y RESTAURACIÓN DIGITAL DE LOS CORTOMETRAJES \'Y DESPUÉS QUE?\', \'YAWAR MAYO RÍO DE SANGRE\', \'HUANDO\' E \'IQUITOS CAPITAL AMAZÓNICA DEL\'',
     63000.00),
    (604, '000604-2021-DGIA/MC', '1405 COMUNICACIONES SAC',
     'COLECCIÓN \'VICUS\', NOTICIERO CULTURAL CINEMATOGRÁFICO, SEGUNDA PARTE',
     70000.00),
    (605, '000605-2021-DGIA/MC', 'SONTRAC S.A.C.',
     'HISTORIA DEL MOVIMIENTO OBRERO EN EL PERÚ',
     66500.00),
    (606, '000606-2021-DGIA/MC', 'ASOCIACIÓN PATRIMONIO FÍLMICO PERUANO',
     'DIGITALIZACIÓN CORTOMETRAJES DE LA LEY 19327',
     65100.00),
    (607, '000607-2021-DGIA/MC', 'PONTIFICIA UNIVERSIDAD CATÓLICA DEL PERÚ',
     '200 NOTICIEROS PERUANOS DE LOS AÑOS 50 Y 60, QUE SOLO SE EXHIBIERON EN LOS CINES DEL PAÍS',
     66500.00),
    (608, '000608-2021-DGIA/MC', 'CARA CARA PRODUCCIONES S.A.C.',
     'RECUPERACIÓN DE 07 CORTOMETRAJES DE ROBERTO BONILLA Y MÓNICA BROWN',
     63000.00),
    (609, '000609-2021-DGIA/MC', 'ORGANISMO NO GUBERNAMENTAL CANCINO FILMS',
     'LOS FOTOGRAMAS DE LA TRAGEDIA',
     66500.00),
    (610, '000610-2021-DGIA/MC', 'PRO CINE S.A.',
     'ÁNGEL DE LA NOCHE Y OTROS CORTOS DE LA LEY 19327',
     66500.00),
    (611, '000611-2021-DGIA/MC', 'ARCHIVO PERUANO DE IMAGEN Y SONIDO',
     'RECONSTRUCCIÓN DE \'BAJO EL SOL DE LORETO\' (ANTONIO WONG RENGIFO, IQUITOS, 1936)',
     70000.00),
]

inserted = 0
for rd_num, res_num, beneficiary, project, amount in entries:
    # Check if resolution already exists
    existing = c.execute("SELECT id FROM resolucion WHERE numero = ?", (res_num,)).fetchone()
    if existing:
        print(f"RD{rd_num}: already exists (res ID {existing[0]})")
        continue

    # Find or create persona
    per = c.execute(
        "SELECT id FROM persona WHERE razon_social = ? AND tipo = 'juridica'",
        (beneficiary,)
    ).fetchone()
    if per:
        per_id = per[0]
    else:
        c.execute("INSERT INTO persona (tipo, razon_social, ruc) VALUES ('juridica', ?, 'PENDIENTE')",
                  (beneficiary,))
        per_id = c.lastrowid

    # Create project
    c.execute("INSERT INTO obra (titulo) VALUES (?)", (project,))
    proj_id = c.lastrowid

    # Create postulación
    c.execute("""
        INSERT INTO proyecto (concurso_anual_id, obra_id, persona_beneficiaria_id, monto_otorgado)
        VALUES (?, ?, ?, ?)
    """, (ca_id, proj_id, per_id, amount))
    post_id = c.lastrowid

    # Create resolución
    url = f"https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2021-EPA-RD{rd_num}-2021-DGIA_MC.pdf"
    c.execute("""
        INSERT INTO resolucion (concurso_anual_id, numero, tipo, url_pdf)
        VALUES (?, ?, 'resolucion_beneficiario', ?)
    """, (ca_id, res_num, url))
    res_id = c.lastrowid

    # Link
    c.execute("INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
              (post_id, res_id))

    print(f"RD{rd_num}: post={post_id} proj={proj_id} per={per_id} res={res_id}")
    inserted += 1

conn.commit()
conn.close()
print(f"\nInserted {inserted} new EPA 2021 entries")
print(f"Total EPA 2021: {inserted + 11} (11 existing + 9 new + 1 rectification)")
