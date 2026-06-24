import sqlite3
import sys
import os

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
dry_run = '--run' not in sys.argv

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

total = 0

# Fix 1: CGC Anual -> 'anual', Multianual -> 'multianual'
fixes = [
    ('Anual', 'anual'),
    ('Multianual', 'multianual'),
]

for modalidad_nombre, categoria_val in fixes:
    cur.execute("""
        SELECT p.id, p.categoria, m.nombre AS modalidad, c.anio, p.monto_otorgado
        FROM proyecto p
        JOIN concurso_anual ca ON ca.id = p.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN modalidad m ON m.id = p.modalidad_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        WHERE lc.codigo = 'CGC'
          AND m.nombre = ?
          AND (p.categoria IS NULL OR p.categoria = '')
        ORDER BY c.anio, p.id
    """, (modalidad_nombre,))
    rows = cur.fetchall()
    if not rows:
        print(f"CGC {modalidad_nombre}: 0 pendientes")
        continue
    print(f"CGC {modalidad_nombre}: {len(rows)} pendientes → categoria '{categoria_val}'")
    for r in rows:
        print(f"  P{r['id']:>6} ({r['anio']})  {r['modalidad']:30}  S/{r['monto_otorgado']:>8,.0f}")
    total += len(rows)

    if not dry_run:
        cur.execute("""
            UPDATE proyecto
            SET categoria = ?
            WHERE id IN ({})
        """.format(','.join(str(r['id']) for r in rows)), (categoria_val,))
        conn.commit()
        print(f"  → {len(rows)} actualizados")

# Fix 2: Corrupt CPF Desarrollo categorias -> 'ÓPERA PRIMA'
cur.execute("""
    SELECT p.id, p.categoria, c.anio, p.monto_otorgado
    FROM proyecto p
    JOIN concurso_anual ca ON ca.id = p.concurso_anual_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    JOIN modalidad m ON m.id = p.modalidad_id
    JOIN convocatoria c ON c.id = ca.convocatoria_id
    WHERE lc.codigo = 'CPF'
      AND m.nombre = 'Desarrollo'
      AND p.categoria IN ('PRIMA', 'PRIMA ÓPERA', 'ÓPERA PRIMA ÓPERA')
    ORDER BY p.id
""")
corrupt = cur.fetchall()
if corrupt:
    print(f"\nCPF Desarrollo corruptos: {len(corrupt)} → categoria 'ÓPERA PRIMA'")
    for r in corrupt:
        print(f"  P{r['id']:>6} ({r['anio']})  '{r['categoria']:20}' → 'ÓPERA PRIMA'  S/{r['monto_otorgado']:>8,.0f}")
    total += len(corrupt)
    if not dry_run:
        cur.execute("""
            UPDATE proyecto
            SET categoria = 'ÓPERA PRIMA'
            WHERE id IN ({})
        """.format(','.join(str(r['id']) for r in corrupt)))
        conn.commit()
        print(f"  → {len(corrupt)} actualizados")

print(f"\nTotal: {total} proyectos para {'actualizar' if not dry_run else 'DRY RUN (pasa --run para ejecutar)'}")
conn.close()
