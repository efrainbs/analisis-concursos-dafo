#!/usr/bin/env python3
"""
Extract responsables from 2019 CGC FalloFinal PDF and create integrante records.
"""
import os, re, sqlite3, subprocess, sys

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
PDF_URL = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2019%20CGC%20-%20Fallo%20final.pdf"

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Download and extract text
pdf = "/tmp/cgc_2019.pdf"
if not os.path.exists(pdf):
    subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf, PDF_URL])
text = subprocess.run(['pdftotext', '-layout', pdf, '-'], capture_output=True, text=True).stdout

# Mapping: project_id -> list of (nombres, apellidos) for responsables
# Extracted manually from the PDF table
RESPONSABLES = {
    61930: [('DAVID', 'GARCIA CAPACYACHI')],
    61931: [('EDWARD AROLDO', 'DE YBARRA MURGUIA')],
    61932: [('JOSE ENRIQUE', 'BALADO DIAZ'),
            ('GABRIELA SABINA', 'URCO CANALES')],
    61933: [('JORGE GABRIEL', 'TEJADA SALAZAR'),
            ('JOSE ALBERTO', 'OSORIO VILLANUEVA')],
    61934: [('FABIOLA REYNA', 'GUTIERREZ')],
    61935: [('JEFFERSON MANUEL', 'TALLEDO CORDOVA')],
    61936: [('RENZO ALONSO', 'ALVA HURTADO')],
    # NOTE: CUYAY WASI (61937?) not in our list - might have integrante already
    61938: [('ZOSIMO JOSE', 'CARDENAS GUTIERREZ'),
            ('IVONNE STEPHANIE', 'SHEEN MOGOLLON'),
            ('MARICE FRANCIS YDELSA', 'CASTAÑEDA GUTIERREZ')],
    61939: [('IVONNE STEPHANIE', 'SHEEN MOGOLLON'),
            ('MARICE FRANCIS YDELSA', 'CASTAÑEDA GUTIERREZ')],
    61940: [('JULIO CESAR', 'GONZALES OVIEDO')],
    61941: [('FIORELLA MISKI', 'MAZZINI URIBE')],
    61942: [('MARCO PAUL', 'VALDIVIA PACHECO')],
    61943: [('BEATRIZ CAROLINA', 'CISNEROS CONTRERAS')],
    61944: [('HENRY', 'TICONA HUAQUISTO')],
    61945: [('ANDREE ALBREHT', 'FRAY ZUÑIGA GUEVARA')],
    61946: [('EFRAIN', 'AGUERO AGUERO SOLORZANO')],
    61947: [('JOHN ALBERTO', 'CAMPOS GOMEZ')],
}

assert len(RESPONSABLES) == 17

DRY_RUN = '--run' not in sys.argv

for pid, responsables in sorted(RESPONSABLES.items()):
    po = db.execute("SELECT id, monto_otorgado FROM proyecto WHERE id=?", (pid,)).fetchone()
    if not po:
        print(f"Project {pid}: NOT FOUND")
        continue
    
    # Check existing integrantes for this project
    existing = db.execute(
        "SELECT persona_id FROM proyecto_integrante WHERE proyecto_id=?", (pid,)
    ).fetchall()
    existing_ids = {r['persona_id'] for r in existing}
    
    for nombres, apellidos in responsables:
        # Check if this persona already exists
        per = db.execute(
            "SELECT id FROM persona WHERE nombres=? AND apellidos=? AND tipo='natural'",
            (nombres, apellidos)
        ).fetchone()
        
        if per:
            per_id = per['id']
        else:
            if DRY_RUN:
                print(f"  Would create: {nombres} {apellidos}")
                continue
            cur = db.execute(
                "INSERT INTO persona (nombres, apellidos, tipo) VALUES (?, ?, 'natural')",
                (nombres, apellidos)
            )
            per_id = cur.lastrowid
            print(f"  Created persona {per_id}: {nombres} {apellidos}")
        
        if per_id in existing_ids:
            print(f"  Project {pid}: {nombres} {apellidos} (ID {per_id}) — already linked")
            continue
        
        if not DRY_RUN:
            db.execute(
                "INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, 'responsable')",
                (pid, per_id)
            )
            print(f"  Project {pid}: linked {nombres} {apellidos} (ID {per_id}) as responsable")

if not DRY_RUN:
    db.commit()
    print("\nCommitted!")
else:
    print("\nUse --run to apply")

db.close()
