"""
Aplicar fixes manuales de integrante para jurídicas verificadas.
Uso: python3 apply_integrante_fixes.py [--run]
"""
import sqlite3, sys, os

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
DRY_RUN = '--run' not in sys.argv

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

fixes = [
    (60504, 'NORMA', 'VELASQUEZ CHAVEZ'),
    (61951, 'ALEX SANDER', 'ARAGON TRUJILLO'),
    (7308,  'RUBEN RENATO', 'MANRIQUE ESPINAR'),
    (7309,  'MARTY YANINTI', 'DEL CASTILLO'),
    (7310,  'DENNIOMAR', 'PERINANGO NUÑEZ'),
    (7311,  'FERNAN GUILLERMO', 'FERNANDEZ CANO'),
    (7312,  'ANA CARIDAD', 'SANCHEZ TEJADA'),
]

for proj_id, nombres, apellidos in fixes:
    cur = db.execute("""
        SELECT p.id, lc.codigo, c.anio, pe.razon_social
        FROM proyecto p
        JOIN persona pe ON p.persona_beneficiaria_id = pe.id
        JOIN concurso_anual ca ON ca.id = p.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        WHERE p.id = ?
    """, (proj_id,))
    proj = cur.fetchone()
    if not proj:
        print(f"P{proj_id}: no encontrado")
        continue

    cur = db.execute("""
        SELECT 1 FROM proyecto_integrante WHERE proyecto_id = ? AND rol = 'responsable'
    """, (proj_id,))
    if cur.fetchone():
        print(f"P{proj_id} ({proj['codigo']} {proj['anio']}): YA tiene integrante — skip")
        continue

    cur = db.execute("""
        SELECT id FROM persona WHERE tipo='natural' AND nombres=? AND apellidos=?
    """, (nombres, apellidos))
    existing = cur.fetchone()
    if existing:
        persona_id = existing['id']
    else:
        if DRY_RUN:
            persona_id = None
        else:
            db.execute("""
                INSERT INTO persona (tipo, nombres, apellidos) VALUES ('natural', ?, ?)
            """, (nombres, apellidos))
            persona_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    empresa = proj['razon_social'][:30]
    if DRY_RUN:
        print(f"  ✓ P{proj_id} ({proj['codigo']} {proj['anio']}): {empresa} → {nombres} {apellidos}")
    else:
        db.execute("""
            INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol)
            VALUES (?, ?, 'responsable')
        """, (proj_id, persona_id))
        print(f"  ✓ P{proj_id} ({proj['codigo']} {proj['anio']}): +integrante {nombres} {apellidos}")

if not DRY_RUN:
    db.commit()

print(f"\n{'DRY RUN' if DRY_RUN else 'APLICADO'} — {'pasa --run para aplicar' if DRY_RUN else ''}")
db.close()
