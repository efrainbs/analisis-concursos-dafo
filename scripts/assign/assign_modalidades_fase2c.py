#!/usr/bin/env python3
"""
Asigna modalidad única a CPC/CDO/CPA pre-2024 (Fase 2c).

Estas líneas eran de categoría única antes de 2024:
  - CPC: Concurso de Proyectos de Cortometrajes
  - CDO: Concurso de Proyectos de Documental
  - CPA: Concurso de Proyectos de Animación

En 2024+ se dividieron en subcategorías (CPC: Ópera prima/Segunda obra;
CDO: Desarrollo/Producción; CPA: Cortometrajes/Desarrollo+Preproducción+Series),
pero pre-2024 eran concursos sin subcategorías explícitas.
Se asigna modalidad genérica = nombre_usado del concurso_anual.

Uso:
  python3 assign_modalidades_fase2c.py            # dry-run
  python3 assign_modalidades_fase2c.py --run
"""
import sqlite3, sys
from dafo_common import DB_PATH

LINEAS_FASE2C = ['CPC', 'CDO', 'CPA']

def main():
    do_run = '--run' in sys.argv
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    total = 0
    assignments = []

    for codigo in LINEAS_FASE2C:
        cur.execute("""
            SELECT po.id, ca.id, ca.nombre_usado, cv.anio
            FROM proyecto po
            JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
            JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
            JOIN convocatoria cv ON cv.id = ca.convocatoria_id
            WHERE lc.codigo = ?
              AND cv.anio < 2024
              AND po.modalidad_id IS NULL
            ORDER BY cv.anio, po.id
        """, (codigo,))
        rows = cur.fetchall()
        n = len(rows)
        if n == 0:
            print(f"{codigo} pre-2024: 0 proyectos sin modalidad", file=sys.stderr)
            continue
        print(f"{codigo} pre-2024: {n} proyectos sin modalidad", file=sys.stderr)
        total += n

        for po_id, ca_id, nombre_usado, anio in rows:
            mod_name = nombre_usado
            assignments.append((po_id, ca_id, mod_name, f"{anio} {codigo}"))

    print(f"\nTotal: {total} proyectos en {len(assignments)} asignaciones", file=sys.stderr)

    # Group by modalidad name for reporting
    from collections import Counter
    mod_counts = Counter(m[2] for m in assignments)
    print("\nModalidades a crear:", file=sys.stderr)
    for mod_name, cnt in sorted(mod_counts.items()):
        print(f"  {cnt:3} × \"{mod_name}\"", file=sys.stderr)

    if not do_run:
        print("\n[DRY-RUN] Sin cambios. Usar --run para aplicar.", file=sys.stderr)
        conn.close()
        return

    print("\n[RUN] Aplicando UPDATEs...", file=sys.stderr)
    updated = 0
    created_mods = []

    for po_id, ca_id, mod_name, label in assignments:
        # Ensure modalidad exists
        cur.execute("SELECT id FROM modalidad WHERE concurso_anual_id=? AND nombre=?",
                    (ca_id, mod_name))
        row = cur.fetchone()
        if row:
            mod_id = row[0]
            created = False
        else:
            cur.execute("INSERT INTO modalidad (concurso_anual_id, nombre) VALUES (?, ?)",
                        (ca_id, mod_name))
            mod_id = cur.lastrowid
            created = True
            created_mods.append((ca_id, mod_name, mod_id))

        cur.execute("UPDATE proyecto SET modalidad_id=? WHERE id=? AND modalidad_id IS NULL",
                    (mod_id, po_id))
        if cur.rowcount:
            updated += 1

    conn.commit()

    print(f"[RUN] Proyectos actualizadas: {updated}", file=sys.stderr)
    if created_mods:
        print(f"[RUN] Modalidades creadas: {len(created_mods)}", file=sys.stderr)
        for ca_id, nombre, mid in created_mods:
            cur.execute("SELECT lc.codigo, cv.anio FROM concurso_anual ca "
                        "JOIN linea_concursable lc ON lc.id=ca.linea_concursable_id "
                        "JOIN convocatoria cv ON cv.id=ca.convocatoria_id "
                        "WHERE ca.id=?", (ca_id,))
            lc, anio = cur.fetchone()
            print(f"  {anio} {lc}: \"{nombre}\" id={mid}", file=sys.stderr)

    conn.close()


if __name__ == '__main__':
    main()
