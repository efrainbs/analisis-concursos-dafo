import sqlite3, sys, os

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
dry_run = '--run' not in sys.argv

conn = sqlite3.connect(DB)
cur = conn.cursor()

if dry_run:
    print("=== DRY RUN (pasa --run para ejecutar) ===\n")

# PDT 2025 data
CA_ID = 18  # PDT 2025
MODALIDAD_ID = None  # Single award, no modalidad needed
CANDIDATO = "VICTOR EDGAR RUIZ BOHORQUEZ"
PRESENTADOR_NOMBRES = "ANDRÉS PAUL"
PRESENTADOR_APELLIDOS = "MAGALLANES MAGALLANES"
REGION = "LIMA"
MONTO = 20000.0
RESOLUCION_NUMERO = "000903-2025-DGIA-VMPCIC/MC"
RESOLUCION_FECHA = "2025-10-17"
RESOLUCION_URL = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-PDT-RD000903-2025-DGIA-VMPCIC.pdf"

def get_or_create_resolucion():
    cur.execute("SELECT id FROM resolucion WHERE numero = ?", (RESOLUCION_NUMERO,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM resolucion")
    rid = cur.fetchone()[0]
    cur.execute("""INSERT INTO resolucion (id, concurso_anual_id, numero, fecha_contenido, tipo, url_pdf)
                   VALUES (?, ?, ?, ?, 'resolucion_beneficiario', ?)""",
                (rid, CA_ID, RESOLUCION_NUMERO, RESOLUCION_FECHA, RESOLUCION_URL))
    conn.commit()
    return rid

# Find or create presentador (beneficiary)
cur.execute("""SELECT id FROM persona
               WHERE nombres = ? AND apellidos = ? AND tipo = 'natural'""",
            (PRESENTADOR_NOMBRES, PRESENTADOR_APELLIDOS))
row = cur.fetchone()
if row:
    presentador_id = row[0]
else:
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM persona")
    presentador_id = cur.fetchone()[0]
    cur.execute("INSERT INTO persona (id, tipo, nombres, apellidos, region) VALUES (?, 'natural', ?, ?, ?)",
                (presentador_id, PRESENTADOR_NOMBRES, PRESENTADOR_APELLIDOS, REGION))
    conn.commit()

# Find or create obra (candidate's name)
cur.execute("SELECT id FROM obra WHERE titulo = ?", (CANDIDATO,))
row = cur.fetchone()
if row:
    obra_id = row[0]
else:
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM obra")
    obra_id = cur.fetchone()[0]
    cur.execute("INSERT INTO obra (id, titulo) VALUES (?, ?)", (obra_id, CANDIDATO))
    conn.commit()

# Get resolution
resolucion_id = get_or_create_resolucion()

if dry_run:
    print(f"Candidato: {CANDIDATO}")
    print(f"Presentador ID: {presentador_id} ({PRESENTADOR_NOMBRES} {PRESENTADOR_APELLIDOS})")
    print(f"Obra ID: {obra_id} ({CANDIDATO})")
    print(f"Resolución ID: {resolucion_id} ({RESOLUCION_NUMERO})")
    print(f"Monto: S/ {MONTO:,.2f}")
    print(f"---")
else:
    # Create project
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM proyecto")
    proy_id = cur.fetchone()[0]
    cur.execute("""INSERT INTO proyecto (id, concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado, estado)
                   VALUES (?, ?, ?, ?, ?, 'beneficiario')""",
                (proy_id, CA_ID, presentador_id, obra_id, MONTO))
    cur.execute("INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                (proy_id, resolucion_id))
    conn.commit()
    print(f"Proyecto {proy_id} insertado — {CANDIDATO} — S/{MONTO:,.2f}")

print(f"\n{'=== DRY RUN ===' if dry_run else '=== HECHO ==='}")
conn.close()
