#!/usr/bin/env python3
"""
Fix PDT 2025 anomaly (project 61952).

Problem:
- Project 61952 (2025 PDT) has monto=0.00, two people concatenated as "juridica",
  and is linked to resolution 000525-2022-DGIA/MC (a 2022 resolution).
- 2022 PDT projects 62006/62007 have no names, no DNI, no resolution link.

Fix:
1. Move resolution 000525-2022-DGIA/MC from 2025→2022 PDT concurso_anual
2. Update project 62006 → NORA ANGELICA DE IZCUE FUCHS, natural, S/ 10,000
3. Update project 62007 → ENRIQUE SANTIAGO REYES MESTAS, natural, S/ 10,000
4. Link 62006/62007 to resolution 000525-2022
5. Delete project 61952 (incorrect duplicate)
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH

RUN = "--run" in sys.argv
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

PDT_2022_CA_ID = 134    # concurso_anual for PDT 2022
PDT_2025_CA_ID = 18     # concurso_anual for PDT 2025
RESOLUCION_ID = 6679    # id for 000525-2022-DGIA/MC
BAD_PROJECT_ID = 61952  # The malformed 2025 project
PROJ_A_ID = 62006       # First 2022 PDT project (no name)
PROJ_B_ID = 62007       # Second 2022 PDT project (no name)

print(f"{'RUN MODE' if RUN else 'DRY RUN'} — DB: {DB_PATH}")
print("=" * 60)

# Step 1: Move resolution to 2022 concurso_anual
print(f"\n[1] Moviendo resolución 000525-2022-DGIA/MC (id={RESOLUCION_ID}) de 2025→2022...")
c.execute("SELECT concurso_anual_id FROM resolucion WHERE id = ?", (RESOLUCION_ID,))
current_ca = c.fetchone()[0]
print(f"  Actual: concurso_anual_id={current_ca} → nuevo: {PDT_2022_CA_ID}")
if RUN:
    c.execute("UPDATE resolucion SET concurso_anual_id = ? WHERE id = ?",
              (PDT_2022_CA_ID, RESOLUCION_ID))
    print("  ✓ Resolución movida")

# Steps 2-3: Update 2022 PDT projects with correct data
# Person A: NORA ANGELICA DE IZCUE FUCHS (natural)
print(f"\n[2] Actualizando proyecto {PROJ_A_ID} → NORA ANGELICA DE IZCUE FUCHS, S/ 10,000...")
if RUN:
    c.execute("""
        UPDATE persona SET tipo='natural', nombres='NORA ANGELICA', apellidos='DE IZCUE FUCHS',
                           razon_social=NULL, ruc=NULL
        WHERE id = (SELECT persona_beneficiaria_id FROM proyecto WHERE id = ?)
    """, (PROJ_A_ID,))
    c.execute("UPDATE proyecto SET monto_otorgado = 10000 WHERE id = ?", (PROJ_A_ID,))
    print("  ✓ Proyecto A actualizado")

# Person B: ENRIQUE SANTIAGO REYES MESTAS (natural)
print(f"\n[3] Actualizando proyecto {PROJ_B_ID} → ENRIQUE SANTIAGO REYES MESTAS, S/ 10,000...")
if RUN:
    c.execute("""
        UPDATE persona SET tipo='natural', nombres='ENRIQUE SANTIAGO', apellidos='REYES MESTAS',
                           razon_social=NULL, ruc=NULL
        WHERE id = (SELECT persona_beneficiaria_id FROM proyecto WHERE id = ?)
    """, (PROJ_B_ID,))
    c.execute("UPDATE proyecto SET monto_otorgado = 10000 WHERE id = ?", (PROJ_B_ID,))
    print("  ✓ Proyecto B actualizado")

# Step 4: Link 2022 projects to resolution
print(f"\n[4] Vinculando proyectos 2022 a resolución...")
for pid in [PROJ_A_ID, PROJ_B_ID]:
    c.execute("SELECT 1 FROM proyecto_resolucion WHERE proyecto_id = ? AND resolucion_id = ?",
              (pid, RESOLUCION_ID))
    if not c.fetchone():
        if RUN:
            c.execute("INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                      (pid, RESOLUCION_ID))
        print(f"  Proyecto {pid} → resolución {RESOLUCION_ID}")
    else:
        print(f"  Proyecto {pid} ya vinculado, saltando.")

# Step 5: Delete bad project 61952 and its resolution link
print(f"\n[5] Eliminando proyecto duplicado {BAD_PROJECT_ID}...")
if RUN:
    c.execute("DELETE FROM proyecto_resolucion WHERE proyecto_id = ?", (BAD_PROJECT_ID,))
    # Get persona_beneficiaria_id before deleting
    c.execute("SELECT persona_beneficiaria_id FROM proyecto WHERE id = ?", (BAD_PROJECT_ID,))
    pers_id = c.fetchone()
    c.execute("DELETE FROM proyecto WHERE id = ?", (BAD_PROJECT_ID,))
    if pers_id:
        c.execute("DELETE FROM persona WHERE id = ?", (pers_id[0],))
        print(f"  Persona {pers_id[0]} también eliminada")
    print("  ✓ Proyecto 61952 eliminado")
else:
    print("  (dry-run — no se elimina)")

if RUN:
    conn.commit()
    print(f"\n{'=' * 60}")
    print("✅ Fix aplicado correctamente.")
else:
    print(f"\n{'=' * 60}")
    print("Usa --run para aplicar el fix.")

conn.close()
