import sqlite3
import sys
import os

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
dry_run = '--run' not in sys.argv

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

if dry_run:
    print("=== DRY RUN (pasa --run para ejecutar) ===")

# Raise max IDs to avoid conflicts
cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM proyecto")
next_proy = cur.fetchone()[0]
cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM obra")
next_obra = cur.fetchone()[0]
cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM documento")
next_doc = cur.fetchone()[0]

print(f"Next IDs: proyecto={next_proy}, obra={next_obra}, documento={next_doc}")

# Data from PDF
PDF_URL = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-CGC-FEM-Beneficiarios.pdf"
CONCURSO_ANUAL_ID = 8   # CGC 2025
MODALIDAD_ID = 16        # Festivales, encuentros y muestras
RESOLUCION_ID = 2317     # 000988-2025-DGIA-VMPCIC/MC

OBRA_TITULO = "X MUTA - FESTIVAL INTERNACIONAL DE APROPIACIÓN AUDIOVISUAL (10MA EDICIÓN)"
PERSONA_JURIDICA_ID = 10480   # INTERSTICIO E.I.R.L.
RESPONSABLE_ID = 10590        # MILAGROS TAVARA ESTELA (creada antes)
MONTO = 100000.00

# 1. Update RUC for INTERSTICIO
print(f"\n1. Actualizar RUC persona 10480 → 20602117333")
if not dry_run:
    cur.execute("UPDATE persona SET ruc = '20602117333' WHERE id = 10480")
    print(f"   RUC actualizado")

# 2. Insert obra
print(f"\n2. Insertar obra {next_obra}: '{OBRA_TITULO}'")
if not dry_run:
    cur.execute("INSERT INTO obra (id, titulo) VALUES (?, ?)", (next_obra, OBRA_TITULO))
    print(f"   Obra insertada")
    conn.commit()

# 3. Insert proyecto
print(f"\n3. Insertar proyecto {next_proy}: INTERSTICIO E.I.R.L., S/ {MONTO}")
if not dry_run:
    cur.execute("""
        INSERT INTO proyecto (id, concurso_anual_id, modalidad_id, persona_beneficiaria_id, obra_id, monto_otorgado, estado)
        VALUES (?, ?, ?, ?, ?, ?, 'beneficiario')
    """, (next_proy, CONCURSO_ANUAL_ID, MODALIDAD_ID, PERSONA_JURIDICA_ID, next_obra, MONTO))
    print(f"   Proyecto insertado")
    conn.commit()

# 4. Insert integrante
print(f"\n4. Insertar integrante: MILAGROS TAVARA ESTELA (responsable)")
if not dry_run:
    cur.execute("""
        INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol)
        VALUES (?, ?, 'responsable')
    """, (next_proy, RESPONSABLE_ID))
    print(f"   Integrante insertado")
    conn.commit()

# 5. Link proyecto to resolution
print(f"\n5. Vincular proyecto a resolución 2317")
if not dry_run:
    cur.execute("""
        INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id)
        VALUES (?, ?)
    """, (next_proy, RESOLUCION_ID))
    print(f"   Vinculado")
    conn.commit()

# 6. Insert documento (if not already present)
cur.execute("SELECT id FROM documento WHERE url = ?", (PDF_URL,))
if not cur.fetchone():
    print(f"\n6. Insertar documento {next_doc}: FEM Beneficiarios PDF")
    if not dry_run:
        cur.execute("""
            INSERT INTO documento (id, concurso_anual_id, tipo_doc, url, titulo)
            VALUES (?, ?, 'resultado', ?, 'Resultados — Concurso De Proyectos De Gestion Para El Audiovisual (2025)')
        """, (next_doc, CONCURSO_ANUAL_ID, PDF_URL))
        print(f"   Documento insertado")
        conn.commit()
else:
    print(f"\n6. Documento ya existe")

print(f"\n{'=== DRY RUN (ejecuta con --run para aplicar) ===' if dry_run else '=== FIX APLICADO ==='}")

# Verify
if not dry_run:
    print("\n=== VERIFICACIÓN ===")
    cur.execute("""
        SELECT p.id, o.titulo, pb.razon_social, pb.ruc, p.monto_otorgado,
               pi.rol, pe.nombres, pe.apellidos, r.numero
        FROM proyecto p
        JOIN obra o ON o.id = p.obra_id
        JOIN persona pb ON pb.id = p.persona_beneficiaria_id
        JOIN proyecto_integrante pi ON pi.proyecto_id = p.id
        JOIN persona pe ON pe.id = pi.persona_id
        JOIN proyecto_resolucion pr ON pr.proyecto_id = p.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        WHERE p.id = ?
    """, (next_proy,))
    row = cur.fetchone()
    if row:
        print(f"  Proyecto: {row['id']}")
        print(f"  Obra: {row['titulo']}")
        print(f"  Beneficiario: {row['razon_social']} (RUC: {row['ruc']})")
        print(f"  Monto: S/ {row['monto_otorgado']:,.2f}")
        print(f"  Responsable: {row['nombres']} {row['apellidos']}")
        print(f"  Resolución: {row['numero']}")

conn.close()
