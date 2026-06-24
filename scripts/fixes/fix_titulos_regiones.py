#!/usr/bin/env python3
"""
Fix project titles that were incorrectly set to region names (or garbled strings)
instead of the actual project title.

Problema: En la extracción del PDF 2022-CDO-FalloFinal.pdf, la columna
DEPARTAMENTO (región) se asignó como título del proyecto en vez de la columna
PROYECTO. Adicionalmente, 3 proyectos EPI 2025 heredaron el título garbled
"PRODUCCIONES MEMORIA SIN CUSCO GUTIERREZ" por compartir obra_id.

Correct titles determined from PDF layout text and individual resolutions.
"""

import sqlite3
import os

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')

# Mapping: (proyecto_id, correct_title)
# Correct titles from 2022-CDO-FalloFinal.pdf layout text
FIXES = [
    (60902, 'A MI MANERA'),
    (60903, 'AUSANGATE'),
    (60904, 'CARNAVAL'),       # already exists as obra_id=173
    (60905, 'CARTA A UNA MEMORIA SIN CORRESPONDER'),
    (60906, 'KUMBIERA'),
    (60907, 'LA VIOLENCIA QUE NO VES'),
    (60908, 'RAZÓN DE VER'),   # already exists as obra_id=202
    (60909, 'TURBIOS TRÓPICOS'),
    # EPI 2025 - correct titles from individual resolutions
    (61590, 'Pan y Mortadela'),
    (61649, 'EL ATRAPANIEBLAS'),
    (61774, 'Festival Internacional de Cine Documental de Ámsterdam (Espacio de Formación)'),
]

def main():
    dry_run = '--run' not in sys.argv

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    if dry_run:
        print("=== DRY RUN (pasa --run para ejecutar) ===\n")

    # Get current max obra id
    cur.execute("SELECT COALESCE(MAX(id), 0) FROM obra")
    next_obra_id = cur.fetchone()[0] + 1

    for proy_id, correct_title in FIXES:
        # Check if proyecto exists
        cur.execute("SELECT id, obra_id FROM proyecto WHERE id = ?", (proy_id,))
        row = cur.fetchone()
        if not row:
            print(f"⚠  Proyecto {proy_id} no encontrado, saltando")
            continue

        _, old_obra_id = row

        # Get old title for reference
        cur.execute("SELECT titulo FROM obra WHERE id = ?", (old_obra_id,))
        old_titulo = cur.fetchone()
        old_titulo = old_titulo[0] if old_titulo else '(sin obra)'

        # Check if obra with correct title already exists
        cur.execute("SELECT id FROM obra WHERE titulo = ?", (correct_title,))
        existing = cur.fetchone()

        if existing:
            new_obra_id = existing[0]
            action = "REUSAR"
        else:
            new_obra_id = next_obra_id
            next_obra_id += 1
            action = "CREAR"

        # Get beneficiary name for display
        cur.execute("""
            SELECT COALESCE(per.razon_social, per.nombres || ' ' || per.apellidos)
            FROM proyecto p
            JOIN persona per ON p.persona_beneficiaria_id = per.id
            WHERE p.id = ?
        """, (proy_id,))
        row_ben = cur.fetchone()
        benef = row_ben[0] if row_ben else '?'

        if dry_run:
            print(f"[{action}] Proyecto {proy_id}:")
            print(f"       Beneficiario: {benef}")
            print(f"       Título: '{old_titulo}' → '{correct_title}'")
            print(f"       Obra: {old_obra_id} → {new_obra_id}")
            if action == "CREAR":
                print(f"       (se insertará obra id={new_obra_id})")
            print()
        else:
            if action == "CREAR":
                cur.execute("INSERT INTO obra (id, titulo) VALUES (?, ?)",
                           (new_obra_id, correct_title))
            cur.execute("UPDATE proyecto SET obra_id = ? WHERE id = ?",
                       (new_obra_id, proy_id))
            print(f"✓ Proyecto {proy_id}: '{old_titulo}' → '{correct_title}' (obra {new_obra_id})")

    if not dry_run:
        conn.commit()
        print("\n✔  Todos los cambios aplicados.")

    conn.close()

if __name__ == '__main__':
    import sys
    main()
