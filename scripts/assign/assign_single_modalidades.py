#!/usr/bin/env python3
"""
Assign a single generic modalidad to lines that have no subcategories.
These are lines where every project belongs to the same modality.

Single-modalidad lines: EPI, EDI, EPA, FCA, PDT, PDS, CCE, CIN, CCC, CGS,
FCP, NMA, CCM, CDV, CBI, CDC, CIC, PAL, DLO, CDL.
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH

RUN = "--run" in sys.argv
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Lines that have no subcategories — each is a single modality
SINGLE_MODALIDAD_CODES = [
    'EPI', 'EDI', 'EPA', 'FCA', 'PDT', 'PDS', 'CCE', 'CIN',
    'CCC', 'CGS', 'FCP', 'NMA', 'CCM', 'CDV', 'CBI', 'CDC',
    'CIC', 'PAL', 'DLO', 'CDL',
]

print(f"{'RUN MODE' if RUN else 'DRY RUN'} — DB: {DB_PATH}")
print("=" * 60)

total_assigned = 0
for codigo in SINGLE_MODALIDAD_CODES:
    # Find all concurso_anual for this line
    c.execute("""
        SELECT ca.id, c.anio, ca.nombre_usado
        FROM concurso_anual ca
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        WHERE lc.codigo = ?
        ORDER BY c.anio
    """, (codigo,))
    rows = c.fetchall()
    if not rows:
        print(f"  {codigo}: no concurso_anual found")
        continue

    for ca_id, anio, nombre_usado in rows:
        # Check if a modalidad already exists for this concurso_anual
        c.execute("""
            SELECT id, nombre FROM modalidad
            WHERE concurso_anual_id = ?
        """, (ca_id,))
        existing_mod = c.fetchone()

        if existing_mod:
            mod_id = existing_mod[0]
            mod_name = existing_mod[1]
        else:
            mod_name = nombre_usado
            if RUN:
                c.execute("""
                    INSERT INTO modalidad (concurso_anual_id, nombre)
                    VALUES (?, ?)
                """, (ca_id, mod_name))
                mod_id = c.lastrowid
            else:
                mod_id = None

        # Get projects without modalidad in this concurso_anual
        c.execute("""
            SELECT id, monto_otorgado
            FROM proyecto
            WHERE concurso_anual_id = ? AND modalidad_id IS NULL
        """, (ca_id,))
        projects = c.fetchall()

        if not projects:
            continue

        if RUN:
            for pid, monto in projects:
                c.execute("""
                    UPDATE proyecto SET modalidad_id = ? WHERE id = ?
                """, (mod_id, pid))

        total_assigned += len(projects)
        print(f"  {codigo} {anio}: {len(projects)} projects → modalidad '{mod_name}' (id={mod_id}){' [DRY]' if not RUN else ''}")

if RUN:
    conn.commit()
    print(f"\nTotal asignados: {total_assigned}")
else:
    print(f"\nUsa --run para aplicar. {total_assigned} proyectos listos para asignar.")

conn.close()
