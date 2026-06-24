import sqlite3, sys, os

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
dry_run = '--run' not in sys.argv

conn = sqlite3.connect(DB)
cur = conn.cursor()

if dry_run:
    print("=== DRY RUN (pasa --run para ejecutar) ===\n")

CA_ID = 30  # CCC 2025 concurso_anual
RES_ID = 2320  # 001047-2025-DGIA-VMPCIC/MC
MOD_ID = 108  # Concurso de Cine en Construcción

# 1. Fix obra title for P7358
cur.execute("UPDATE obra SET titulo = 'EL COLOQUIO DE LOS PÁJAROS' WHERE id = (SELECT obra_id FROM proyecto WHERE id = 7358)")
if dry_run:
    print("Obra P7358: 'COLOQUIO DE LOS ÁJAROS' → 'EL COLOQUIO DE LOS PÁJAROS'")
else:
    conn.commit()
    print("✅ Obra P7358 corregida")

# 2. OCEANO FILMS E.I.R.L. — VAMOS A PERDER LA CABEZA
def find_or_create_persona_juridica(razon_social, ruc, region=None):
    cur.execute("SELECT id FROM persona WHERE ruc = ?", (ruc,))
    row = cur.fetchone()
    if row: return row[0]
    cur.execute("SELECT id FROM persona WHERE razon_social = ? AND tipo = 'juridica'", (razon_social,))
    row = cur.fetchone()
    if row: 
        cur.execute("UPDATE persona SET ruc = ? WHERE id = ?", (ruc, row[0]))
        return row[0]
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM persona")
    nid = cur.fetchone()[0]
    cur.execute("INSERT INTO persona (id, tipo, razon_social, ruc, region) VALUES (?, 'juridica', ?, ?, ?)",
                (nid, razon_social, ruc, region or 'SIN DATO'))
    conn.commit()
    return nid

def find_or_create_persona_natural(nombres, apellidos, region=None):
    cur.execute("SELECT id FROM persona WHERE nombres = ? AND apellidos = ? AND tipo = 'natural'",
                (nombres, apellidos))
    row = cur.fetchone()
    if row: return row[0]
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM persona")
    nid = cur.fetchone()[0]
    cur.execute("INSERT INTO persona (id, tipo, nombres, apellidos, region) VALUES (?, 'natural', ?, ?, ?)",
                (nid, nombres, apellidos, region or 'SIN DATO'))
    conn.commit()
    return nid

def find_or_create_obra(titulo):
    cur.execute("SELECT id FROM obra WHERE titulo = ?", (titulo,))
    row = cur.fetchone()
    if row: return row[0]
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM obra")
    nid = cur.fetchone()[0]
    cur.execute("INSERT INTO obra (id, titulo) VALUES (?, ?)", (nid, titulo))
    conn.commit()
    return nid

def insert_proyecto(ca_id, mod_id, persona_id, obra_id, monto, res_id, responsables):
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM proyecto")
    proy_id = cur.fetchone()[0]
    cur.execute("""INSERT INTO proyecto (id, concurso_anual_id, modalidad_id, persona_beneficiaria_id, obra_id, monto_otorgado, estado)
                   VALUES (?, ?, ?, ?, ?, ?, 'beneficiario')""",
                (proy_id, ca_id, mod_id, persona_id, obra_id, monto))
    cur.execute("INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)", (proy_id, res_id))
    for r in responsables:
        cur.execute("INSERT INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, 'director')",
                    (proy_id, r))
    conn.commit()
    return proy_id

# Project 2: OCEANO FILMS
oceano_id = find_or_create_persona_juridica("OCEANO FILMS E.I.R.L.", "20606211423", "LIMA")
jorge_id = find_or_create_persona_natural("JORGE PABLO", "QUIROZ SALEM", "LIMA")
nicolas_id = find_or_create_persona_natural("NICOLAS", "SABA SALEM", "LIMA")
obra_vamos = find_or_create_obra("VAMOS A PERDER LA CABEZA")

if dry_run:
    print(f"OCEANO FILMS: persona={oceano_id}, obra={obra_vamos}, directores=({jorge_id}, {nicolas_id}), monto=S/155,702")
else:
    pid = insert_proyecto(CA_ID, MOD_ID, oceano_id, obra_vamos, 155702.0, RES_ID, [jorge_id, nicolas_id])
    print(f"✅ P{pid} — OCEANO FILMS — VAMOS A PERDER LA CABEZA — S/155,702")

# Project 3: VIA EXPRESA S.R.L.
# Use existing ID 8895 (VIA EXPRESA CINE Y VIDEO - SOCIEDAD DE RESPONSABILIDAD LIMITADA - VIA EXPRESA S.R.L)
cur.execute("SELECT id FROM persona WHERE id = 8895")
if cur.fetchone():
    via_id = 8895
    if not dry_run:
        cur.execute("UPDATE persona SET ruc = ?, region = 'AREQUIPA' WHERE id = ?", ("20539398483", via_id))
else:
    via_id = find_or_create_persona_juridica(
        "VIA EXPRESA CINE Y VIDEO - SOCIEDAD DE RESPONSABILIDAD LIMITADA - VIA EXPRESA S.R.L",
        "20539398483", "AREQUIPA")

leandro_id = find_or_create_persona_natural("LEANDRO SEBASTIAN", "PINTO LE ROUX", "AREQUIPA")
obra_duelo = find_or_create_obra("DUELO")

if dry_run:
    print(f"VIA EXPRESA: persona={via_id}, obra={obra_duelo}, director={leandro_id}, monto=S/144,000")
else:
    pid = insert_proyecto(CA_ID, MOD_ID, via_id, obra_duelo, 144000.0, RES_ID, [leandro_id])
    print(f"✅ P{pid} — VIA EXPRESA — DUELO — S/144,000")

print(f"\n{'=== DRY RUN ===' if dry_run else '=== HECHO ==='}")
conn.close()
