import sqlite3
import sys

DB = "/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

print("=== Current PDT state ===")
rows = cur.execute("""
    SELECT p.id, o.titulo, p.persona_beneficiaria_id,
           COALESCE(per.nombres||' '||per.apellidos, per.razon_social) AS persona
    FROM proyecto p
    JOIN obra o ON p.obra_id = o.id
    JOIN persona per ON p.persona_beneficiaria_id = per.id
    JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
    JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
    WHERE lc.codigo = 'PDT'
    ORDER BY p.id
""").fetchall()
for r in rows:
    print(f"  {r[0]}: titulo='{r[1]}' beneficiary={r[2]} ({r[3]})")

print()

# 1) Create BELARMINA SOLAR BECERRA (natural)
cur.execute("INSERT INTO persona (tipo, nombres, apellidos) VALUES ('natural', 'BELARMINA', 'SOLAR BECERRA')")
belarmina_id = cur.lastrowid
print(f"Created BELARMINA SOLAR BECERRA → id {belarmina_id}")

# 2) Create VICTOR EDGAR RUIZ BOHORQUEZ (natural)
cur.execute("INSERT INTO persona (tipo, nombres, apellidos) VALUES ('natural', 'VICTOR EDGAR', 'RUIZ BOHORQUEZ')")
victor_id = cur.lastrowid
print(f"Created VICTOR EDGAR RUIZ BOHORQUEZ → id {victor_id}")

# 3) Update persona 9855: DELIA ACKERMAN → DELIA ACKERMAN KRIKLER
cur.execute("UPDATE persona SET apellidos = 'ACKERMAN KRIKLER' WHERE id = 9855")
print("Updated persona 9855: DELIA ACKERMAN → DELIA ACKERMAN KRIKLER")

# 4) Update all PDT beneficiary to CANDIDATO
updates = {
    60688: 10302,  # JULIO CESAR GONZALES OVIEDO
    60689: belarmina_id,  # BELARMINA SOLAR BECERRA
    61139: 8778,   # CHASKI, COMUNICACION AUDIOVISUAL
    61140: 9854,   # CESAR AUGUSTO VIVANCO LUNA
    61141: 9855,   # DELIA ACKERMAN KRIKLER
    62147: victor_id,  # VICTOR EDGAR RUIZ BOHORQUEZ
}
for pid, new_per_id in updates.items():
    cur.execute("UPDATE proyecto SET persona_beneficiaria_id = ? WHERE id = ?", (new_per_id, pid))
    print(f"Updated proyecto {pid}: persona_beneficiaria_id → {new_per_id}")

conn.commit()

print()
print("=== Final PDT state ===")
rows = cur.execute("""
    SELECT p.id, o.titulo, p.persona_beneficiaria_id,
           COALESCE(per.nombres||' '||per.apellidos, per.razon_social) AS persona
    FROM proyecto p
    JOIN obra o ON p.obra_id = o.id
    JOIN persona per ON p.persona_beneficiaria_id = per.id
    JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
    JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
    WHERE lc.codigo = 'PDT'
    ORDER BY p.id
""").fetchall()
for r in rows:
    print(f"  {r[0]}: titulo='{r[1]}' beneficiary={r[2]} ({r[3]})")

conn.close()
