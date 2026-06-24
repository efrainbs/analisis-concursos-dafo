import sqlite3
import sys

DB = "/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

print("=== Current PDT state ===")
rows = cur.execute("""
    SELECT p.id, cv.anio,
           o.id as oid, o.titulo as otit, o.tipo as otipo,
           p.persona_beneficiaria_id,
           COALESCE(per.nombres||' '||per.apellidos, per.razon_social) as beneficiary,
           per.dni
    FROM proyecto p
    LEFT JOIN obra o ON p.obra_id = o.id
    JOIN persona per ON p.persona_beneficiaria_id = per.id
    JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
    JOIN convocatoria cv ON ca.convocatoria_id = cv.id
    JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
    WHERE lc.codigo = 'PDT'
    ORDER BY cv.anio, p.id
""").fetchall()

for r in rows:
    oid = r[2] or 'NULL'
    otit = r[3] or '—'
    print(f"  {r[0]} ({r[1]}): obra_id={oid} titulo='{otit}' ben_id={r[4]} ({r[5]}) dni={r[6] or '—'}")

print()

# ─── FIX 1: Project 60688 (2024) ───
# Candidate is CESAR ROBERTO PEREZ HURTADO (dni 08429812, persona #9693)
# Current: titulo='JULIO CESAR GONZALES OVIEDO', ben=10302
# Fix: titulo → CESAR ROBERTO PEREZ HURTADO, ben → 9693

cur.execute("UPDATE obra SET titulo = 'CESAR ROBERTO PEREZ HURTADO' WHERE id = 687")
cur.execute("UPDATE proyecto SET persona_beneficiaria_id = 9693 WHERE id = 60688")
print("✅ Fixed 60688: titulo='CESAR ROBERTO PEREZ HURTADO' ben=9693")

# ─── FIX 2: Project 60689 (2024) ───
# Per pattern: candidate is LADISLAO PARRA BELLO (persona #9694)
# Current: titulo='BELARMINA SOLAR BECERRA', ben=10658
# Fix: titulo → LADISLAO PARRA BELLO, ben → 9694

cur.execute("UPDATE obra SET titulo = 'LADISLAO PARRA BELLO' WHERE id = 688")
cur.execute("UPDATE proyecto SET persona_beneficiaria_id = 9694 WHERE id = 60689")
print("✅ Fixed 60689: titulo='LADISLAO PARRA BELLO' ben=9694")

# ─── FIX 3: Projects 62006, 62007 (2022) and 62053, 62054 (2023) ───
# These have obra_id=NULL. Create obra records.
# obra.titulo = beneficiary name, obra.tipo = 'trayectoria'

missing_obra = [
    (62006, 'NORA ANGELICA DE IZCUE FUCHS'),
    (62007, 'ENRIQUE SANTIAGO REYES MESTAS'),
    (62053, 'JOSE ANTONIO PORTUGAL SPEEDIE'),
    (62054, 'ALVARO VELARDE LA ROSA'),
]

for pid, titulo in missing_obra:
    cur.execute("INSERT INTO obra (titulo, tipo) VALUES (?, 'trayectoria')", (titulo,))
    oid = cur.lastrowid
    cur.execute("UPDATE proyecto SET obra_id = ? WHERE id = ?", (oid, pid))
    print(f"✅ Fixed {pid}: created obra #{oid} titulo='{titulo}' trayectoria")

conn.commit()

print()
print("=== Final PDT state ===")
rows = cur.execute("""
    SELECT p.id, cv.anio,
           o.id as oid, o.titulo as otit, o.tipo as otipo,
           p.persona_beneficiaria_id,
           COALESCE(per.nombres||' '||per.apellidos, per.razon_social) as beneficiary,
           per.dni
    FROM proyecto p
    LEFT JOIN obra o ON p.obra_id = o.id
    JOIN persona per ON p.persona_beneficiaria_id = per.id
    JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
    JOIN convocatoria cv ON ca.convocatoria_id = cv.id
    JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
    WHERE lc.codigo = 'PDT'
    ORDER BY cv.anio, p.id
""").fetchall()

for r in rows:
    oid = r[2] or 'NULL'
    otit = r[3] or '—'
    print(f"  {r[0]} ({r[1]}): obra_id={oid} titulo='{otit}' ben_id={r[4]} ({r[5]}) dni={r[6] or '—'}")

conn.close()
