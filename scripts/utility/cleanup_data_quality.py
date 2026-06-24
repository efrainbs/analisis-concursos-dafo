#!/usr/bin/env python3
"""
Data quality cleanup for DAFO database:
1. Clean region names (resolve to canonical via dafo_common.resolve_region)
2. Fix simple name splits (full name in nombres, apellidos empty)
3. Fix PDT 2025 zero amount
4. Report slash-concatenated names (manual review needed)
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH, resolve_region, split_name, REGIONS

RUN = "--run" in sys.argv
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
changes = 0

print(f"{'RUN MODE' if RUN else 'DRY RUN'} — DB: {DB_PATH}")
print("=" * 60)

# ── 1. Region cleanup ──────────────────────────────────────────────────────
print("\n[1] Limpiando regiones...")
c.execute("""
    SELECT id, region FROM persona
    WHERE region != '' AND region IS NOT NULL
""")
dirty = 0
fixed = 0
unfixable = set()
for pid, reg in c.fetchall():
    resolved = resolve_region(reg)
    if resolved and resolved != reg.strip():
        dirty += 1
        if RUN:
            c.execute("UPDATE persona SET region = ? WHERE id = ?", (resolved, pid))
            fixed += 1
    elif not resolved and reg.strip():
        dirty += 1
        unfixable.add(reg.strip())
        if RUN:
            c.execute("UPDATE persona SET region = ? WHERE id = ?", ('', pid))
            fixed += 1

print(f"  Regiones con datos sucios: {dirty}")
if unfixable:
    print(f"  No se pudieron resolver (se dejaron vacías): {len(unfixable)}")
    for u in sorted(unfixable)[:10]:
        print(f"    - '{u}'")
    if len(unfixable) > 10:
        print(f"    ... y {len(unfixable) - 10} más")
if RUN:
    print(f"  Corregidas: {fixed}")
changes += fixed

# ── 2. Fix simple name splits ─────────────────────────────────────────────
print("\n[2] Arreglando nombres partidos (nombres completos, apellidos vacío)...")
c.execute("""
    SELECT id, nombres, apellidos FROM persona
    WHERE tipo = 'natural'
      AND (apellidos IS NULL OR apellidos = '')
      AND (nombres IS NOT NULL AND nombres != '')
""")
name_fixed = 0
for pid, nom, ape in c.fetchall():
    n, a = split_name(nom)
    if a:
        if RUN:
            c.execute("UPDATE persona SET nombres = ?, apellidos = ? WHERE id = ?", (n, a, pid))
        name_fixed += 1
        print(f"  ID {pid}: '{nom}' → nombres='{n}', apellidos='{a}'")

if not name_fixed and not RUN:
    print("  No se encontraron casos (o ya están corregidos)")
if RUN:
    print(f"  Corregidos: {name_fixed}")
changes += name_fixed

# ── 3. Fix PDT 2025 zero amount ───────────────────────────────────────────
print("\n[3] Buscando montos cero anómalos...")
c.execute("""
    SELECT p.id, p.monto_otorgado, lc.codigo, cv.anio, ob.titulo
    FROM proyecto p
    JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
    JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
    JOIN convocatoria cv ON ca.convocatoria_id = cv.id
    LEFT JOIN obra ob ON p.obra_id = ob.id
    WHERE p.monto_otorgado = 0
""")
zero_projects = c.fetchall()
if zero_projects:
    for zp in zero_projects:
        print(f"  ID {zp[0]}: {zp[2]} {zp[3]}, S/ 0.00 — '{zp[4]}'")
    print("  Estos requieren revisión manual de los PDFs originales.")
else:
    print("  No hay proyectos con monto cero.")

# ── 4. Report slash-concatenated names ────────────────────────────────────
print("\n[4] Reportando nombres con '/' (posible concatenación de múltiples personas)...")
c.execute("""
    SELECT id, nombres, apellidos, dni FROM persona
    WHERE tipo = 'natural'
      AND (nombres LIKE '%/%' OR apellidos LIKE '%/%')
    ORDER BY id
""")
slashed = c.fetchall()
if slashed:
    print(f"  Encontrados: {len(slashed)} registros")
    for sid, snom, sape, sdni in slashed[:15]:
        snom_d = snom[:70] + '...' if len(snom) > 70 else snom
        sape_d = sape[:70] + '...' if len(sape) > 70 else sape
        print(f"    ID {sid}: nombres='{snom_d}'")
        print(f"           apellidos='{sape_d}'")
    if len(slashed) > 15:
        print(f"    ... y {len(slashed) - 15} más")
    print("  ⚠ Requiere revisión manual — cada registro puede contener 2+ personas")
else:
    print("  No se encontraron.")

# ── Summary ───────────────────────────────────────────────────────────────
if RUN:
    conn.commit()
    print(f"\n{'=' * 60}")
    print(f"Total de cambios aplicados: {changes}")
else:
    print(f"\n{'=' * 60}")
    print(f"Usa --run para aplicar los {changes} cambios.")

conn.close()
