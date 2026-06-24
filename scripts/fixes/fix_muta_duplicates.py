import sqlite3
import sys
import os

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
dry_run = '--run' not in sys.argv

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

if dry_run:
    print("=== DRY RUN (pasa --run para ejecutar) ===\n")

# =====================================================
# 1. ELIMINAR DUPLICADO P61099
# =====================================================
print("--- P61099: VI MUTA (duplicado corrupto) ---")
# Check current state
cur.execute("SELECT id, titulo FROM obra WHERE id = 408")
obra = cur.fetchone()
if obra:
    print(f"  Obra 408: '{obra['titulo']}' (solo usada por P61099)")

cur.execute("SELECT COUNT(*) as cnt FROM proyecto_integrante WHERE proyecto_id = 61099")
print(f"  Integrantes: {cur.fetchone()['cnt']}")

cur.execute("SELECT COUNT(*) as cnt FROM proyecto_resolucion WHERE proyecto_id = 61099")
print(f"  Resoluciones: {cur.fetchone()['cnt']}")

if not dry_run:
    # Delete integrante
    cur.execute("DELETE FROM proyecto_integrante WHERE proyecto_id = 61099")
    print(f"  → Integrante eliminado")
    # Delete resolucion link
    cur.execute("DELETE FROM proyecto_resolucion WHERE proyecto_id = 61099")
    print(f"  → Resolucion desvinculada")
    # Delete obra (only used by P61099)
    cur.execute("DELETE FROM obra WHERE id = 408")
    print(f"  → Obra 408 eliminada")
    # Delete proyecto
    cur.execute("DELETE FROM proyecto WHERE id = 61099")
    print(f"  → Proyecto 61099 eliminado")
    conn.commit()
else:
    print("  → Se eliminaria: integrante, resolucion, obra 408, proyecto 61099")

# =====================================================
# 2. FIX P61307 (V MUTA 2020 con datos corruptos)
# =====================================================
print("\n--- P61307: V MUTA 2020 (corrupto) ---")

# 2a. Fix obra title
if not dry_run:
    cur.execute("""
        UPDATE obra SET titulo = 'V MUTA FESTIVAL INTERNACIONAL DE APROPIACIÓN AUDIOVISUAL'
        WHERE id = 586
    """)
    print(f"  → Obra 586: titulo corregido")
else:
    print(f"  → Obra 586: 'INTERSTICIO E.I.R.L. LIMA' → 'V MUTA FESTIVAL INTERNACIONAL DE APROPIACIÓN AUDIOVISUAL'")

# 2b. Note: persona 9849 (INTERSTICIO E.I.R.L) se queda como natural
# (no tenemos RUC para convertirla a jurídica según CHECK constraint)
print(f"  → Persona 9849: se queda como natural (sin RUC para conversión a jurídica)")

# 2c. Replace integrante
if not dry_run:
    # Delete old integrante (company as director)
    cur.execute("DELETE FROM proyecto_integrante WHERE proyecto_id = 61307")
    print(f"  → Integrante antiguo eliminado")

    # Create or find Milagros Tavara Estela
    cur.execute("SELECT id FROM persona WHERE nombres = 'MILAGROS' AND apellidos = 'TAVARA ESTELA' AND tipo = 'natural'")
    row = cur.fetchone()
    if row:
        p1_id = row['id']
    else:
        cur.execute("INSERT INTO persona (tipo, nombres, apellidos) VALUES ('natural', 'MILAGROS', 'TAVARA ESTELA')")
        p1_id = cur.lastrowid
    print(f"  → Persona {p1_id}: MILAGROS TAVARA ESTELA")

    # Create or find Natalia Rey de Castro Luna
    cur.execute("SELECT id FROM persona WHERE nombres = 'NATALIA' AND apellidos = 'REY DE CASTRO LUNA' AND tipo = 'natural'")
    row = cur.fetchone()
    if row:
        p2_id = row['id']
    else:
        cur.execute("INSERT INTO persona (tipo, nombres, apellidos) VALUES ('natural', 'NATALIA', 'REY DE CASTRO LUNA')")
        p2_id = cur.lastrowid
    print(f"  → Persona {p2_id}: NATALIA REY DE CASTRO LUNA")

    # Insert both as responsables
    cur.execute("INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (61307, ?, 'responsable')", (p1_id,))
    cur.execute("INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (61307, ?, 'responsable')", (p2_id,))
    print(f"  → 2 responsables insertados")
    conn.commit()
else:
    print(f"  → Se reemplazaria integrante con: MILAGROS TAVARA ESTELA + NATALIA REY DE CASTRO LUNA")

# =====================================================
# FINAL: Verify P62087 is still correct
# =====================================================
print("\n--- P62087: VI MUTA 2021 (ya correcto) ---")
cur.execute("""
    SELECT o.titulo, pb.razon_social, pi.rol, pe.nombres, pe.apellidos
    FROM proyecto p
    JOIN obra o ON o.id = p.obra_id
    JOIN persona pb ON pb.id = p.persona_beneficiaria_id
    LEFT JOIN proyecto_integrante pi ON pi.proyecto_id = p.id
    LEFT JOIN persona pe ON pe.id = pi.persona_id
    WHERE p.id = 62087
""")
for r in cur.fetchall():
    print(f"  Obra: {r['titulo']}")
    print(f"  Beneficiario: {r['razon_social']}")
    print(f"  Integrante: {r['nombres']} {r['apellidos']} ({r['rol']})")

print(f"\n{'=== DRY RUN (ejecuta con --run para aplicar) ===' if dry_run else '=== FIX APLICADO ==='}")
conn.close()
