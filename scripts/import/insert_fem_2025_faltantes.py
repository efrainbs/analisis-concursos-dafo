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

RESOLUCION_ID = 2317
CA_ID = 8
MODALIDAD_ID = 16

# ---- Helper ----
def find_or_create_persona(tipo, nombres, apellidos, razon_social, ruc):
    if ruc:
        cur.execute("SELECT id FROM persona WHERE ruc = ?", (ruc,))
        row = cur.fetchone()
        if row:
            return row['id']
    if razon_social:
        cur.execute("SELECT id FROM persona WHERE razon_social = ? AND tipo = 'juridica'", (razon_social,))
        row = cur.fetchone()
        if row:
            if ruc:
                cur.execute("UPDATE persona SET ruc = ? WHERE id = ?", (ruc, row['id']))
            return row['id']
    if nombres and apellidos:
        cur.execute("SELECT id FROM persona WHERE nombres = ? AND apellidos = ? AND tipo = 'natural'", (nombres, apellidos))
        row = cur.fetchone()
        if row:
            return row['id']
    # Create
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM persona")
    nid = cur.fetchone()[0]
    if tipo == 'juridica':
        cur.execute("INSERT INTO persona (id, tipo, razon_social, ruc) VALUES (?, 'juridica', ?, ?)",
                    (nid, razon_social, ruc))
    else:
        cur.execute("INSERT INTO persona (id, tipo, nombres, apellidos) VALUES (?, 'natural', ?, ?)",
                    (nid, nombres, apellidos))
    conn.commit()
    return nid

def find_or_create_obra(titulo):
    cur.execute("SELECT id FROM obra WHERE titulo = ?", (titulo,))
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM obra")
    nid = cur.fetchone()[0]
    cur.execute("INSERT INTO obra (id, titulo) VALUES (?, ?)", (nid, titulo))
    conn.commit()
    return nid

# ---- Beneficiarios a insertar ----
beneficiarios = [
    {
        'empresa': 'DEPA 514 E.I.R.L.',
        'ruc': '20611047046',
        'region': 'LA LIBERTAD',
        'obra': 'FESTIVAL DE CINE DE TRUJILLO',
        'responsable_nombres': 'MARIAGRACIA',
        'responsable_apellidos': 'MEJIA GAVIDIA',
        'monto': 92600.00,
    },
    {
        'empresa': 'FRAME & RENDER E.I.R.L.',
        'ruc': '20609905086',
        'region': 'PIURA',
        'obra': 'CINE CON CHIFLES 2026',
        'responsable_nombres': 'GERARDO GABRIEL',
        'responsable_apellidos': 'ALZAMORA LOPEZ',
        'monto': 100000.00,
    },
    {
        'empresa': 'OBSERVATORIO DE GENERO Y CULTURA - OGECU',
        'ruc': '20612587940',
        'region': 'LIMA',
        'obra': '8VO Y 9NO FESTIVAL HECHO POR MUJERES Y DISIDENCIAS',
        'responsable_nombres': 'FABIOLA',
        'responsable_apellidos': 'REYNA GUTIERREZ',
        'monto': 100000.00,
    },
]

inserted = []
for b in beneficiarios:
    print(f"\n=== {b['empresa']} — {b['obra']} ===")
    juridica_id = find_or_create_persona('juridica', None, None, b['empresa'], b['ruc'])
    print(f"  Persona jurídica: {juridica_id} ({b['empresa']}, RUC: {b['ruc']})")
    if b['region']:
        if not dry_run:
            cur.execute("UPDATE persona SET region = ? WHERE id = ?", (b['region'], juridica_id))
    resp_id = find_or_create_persona('natural', b['responsable_nombres'], b['responsable_apellidos'], None, None)
    print(f"  Responsable: {resp_id} ({b['responsable_nombres']} {b['responsable_apellidos']})")
    obra_id = find_or_create_obra(b['obra'])
    print(f"  Obra: {obra_id} ({b['obra']})")

    if not dry_run:
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM proyecto")
        proy_id = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO proyecto (id, concurso_anual_id, modalidad_id, persona_beneficiaria_id, obra_id, monto_otorgado, estado)
            VALUES (?, ?, ?, ?, ?, ?, 'beneficiario')
        """, (proy_id, CA_ID, MODALIDAD_ID, juridica_id, obra_id, b['monto']))
        cur.execute("""
            INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol)
            VALUES (?, ?, 'responsable')
        """, (proy_id, resp_id))
        cur.execute("""
            INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id)
            VALUES (?, ?)
        """, (proy_id, RESOLUCION_ID))
        conn.commit()
        print(f"  Proyecto {proy_id} insertado, S/ {b['monto']:,.2f}")
        inserted.append(proy_id)
    else:
        print(f"  Se insertaría: proyecto, obra, integrante, resolución")

# ---- Fix P62014 y P62015: estado a lista_espera ----
print(f"\n=== Corregir estado de lista de espera ===")
for pid in (62014, 62015):
    cur.execute("SELECT id, estado FROM proyecto WHERE id = ?", (pid,))
    row = cur.fetchone()
    if row and row['estado'] == 'beneficiario':
        print(f"  P{pid}: actualmente '{row['estado']}' → 'lista_espera'")
        if not dry_run:
            cur.execute("UPDATE proyecto SET estado = 'lista_espera' WHERE id = ?", (pid,))
            conn.commit()
            print(f"  → Corregido")
    else:
        st = row['estado'] if row else 'NO EXISTE'
        print(f"  P{pid}: {st} (sin cambios)")

print(f"\n{'=== DRY RUN (ejecuta con --run para aplicar) ===' if dry_run else '=== FIX APLICADO ==='}")
if not dry_run and inserted:
    print(f"Proyectos insertados: {inserted}")

conn.close()
