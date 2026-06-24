#!/usr/bin/env python3
"""Fix orphaned integrantes, add missing integrantes, mark unknown regions."""
import sqlite3, sys
from pathlib import Path

DB = Path.home() / "Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
DRY_RUN = "--run" not in sys.argv

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

if DRY_RUN:
    print("DRY RUN (pass --run to execute)\n")

# ── 0. Clean orphaned integrantes ─────────────────────────────────────
orphans = cur.execute("""
    SELECT pi.id FROM proyecto_integrante pi
    LEFT JOIN proyecto p ON pi.proyecto_id = p.id
    WHERE p.id IS NULL
""").fetchall()
print(f"Integrantes huérfanos a eliminar: {len(orphans)}")
if not DRY_RUN:
    cur.execute("""
        DELETE FROM proyecto_integrante WHERE id IN (
            SELECT pi.id FROM proyecto_integrante pi
            LEFT JOIN proyecto p ON pi.proyecto_id = p.id
            WHERE p.id IS NULL
        )
    """)

# ── 1. Add missing integrantes ────────────────────────────────────────
sin_int = cur.execute("""
    SELECT p.id, p.persona_beneficiaria_id, pe.tipo
    FROM proyecto p
    JOIN persona pe ON p.persona_beneficiaria_id = pe.id
    LEFT JOIN proyecto_integrante pi ON p.id = pi.proyecto_id
    WHERE pi.id IS NULL
""").fetchall()

print(f"Proyectos sin integrantes: {len(sin_int)}")
inserted = 0
for pid, peid, tipo in sin_int:
    rol = "director" if tipo == "natural" else "responsable"
    if not DRY_RUN:
        cur.execute(
            "INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, ?)",
            (pid, peid, rol),
        )
    inserted += 1
print(f"  Integrantes insertados: {inserted}")

# ── 2. Mark unknown regions ───────────────────────────────────────────
sin_reg = cur.execute("SELECT COUNT(*) FROM persona WHERE region IS NULL OR region = ''").fetchone()[0]
print(f"\nPersonas sin región a marcar 'SIN DATO': {sin_reg}")
if not DRY_RUN:
    cur.execute("UPDATE persona SET region = 'SIN DATO' WHERE region IS NULL OR region = ''")
    conn.commit()

# ── 3. Summary ────────────────────────────────────────────────────────
total_proy = cur.execute("SELECT COUNT(*) FROM proyecto").fetchone()[0]
total_int = cur.execute("SELECT COUNT(*) FROM proyecto_integrante").fetchone()[0]
con_int = cur.execute("SELECT COUNT(DISTINCT proyecto_id) FROM proyecto_integrante").fetchone()[0]
sin_reg_final = cur.execute("SELECT COUNT(*) FROM persona WHERE region IS NULL OR region = ''").fetchone()[0]

print(f"\n── Resumen ──")
print(f"Proyectos total: {total_proy}")
print(f"Integrantes total: {total_int}")
print(f"Proyectos con ≥1 integrante: {con_int}")
print(f"Proyectos sin integrantes: {total_proy - con_int}")
print(f"Personas sin región: {sin_reg_final}")
print(f"\nEstado: {'DRY RUN - sin cambios' if DRY_RUN else 'EJECUTADO'}")

conn.close()
