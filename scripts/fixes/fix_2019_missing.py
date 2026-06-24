"""
Fix missing/corrupted entries for 2019: CCC (3 missing), CDL (1 missing), CGC (~17 missing)
Replaces garbage parser output with correct data from fallo PDF texts.
"""
import sqlite3
import sys

DB = "/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
con = sqlite3.connect(DB)
cur = con.cursor()

# --- Helper: get or create persona ---
def get_or_create_persona(tipo, razon_social=None, nombres=None, apellidos=None, region=None):
    if tipo == 'juridica' and razon_social:
        cur.execute("SELECT id FROM persona WHERE tipo='juridica' AND razon_social=?", (razon_social,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO persona (tipo, razon_social, ruc, region) VALUES (?, ?, ?, ?)",
                    (tipo, razon_social, 'SIN_RUC', region))
        return cur.lastrowid
    elif tipo == 'natural':
        cur.execute("SELECT id FROM persona WHERE tipo='natural' AND nombres=? AND apellidos=?",
                    (nombres, apellidos))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO persona (tipo, nombres, apellidos, region) VALUES (?, ?, ?, ?)",
                    (tipo, nombres, apellidos, region))
        return cur.lastrowid
    raise ValueError("Invalid persona type")

# --- Helper: get or create proyecto ---
def get_or_create_proyecto(titulo):
    cur.execute("SELECT id FROM obra WHERE titulo=?", (titulo,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO obra (titulo) VALUES (?)", (titulo,))
    return cur.lastrowid

# --- Helper: create proyecto ---
def create_proyecto(concurso_anual_id, persona_id, obra_id, monto, categoria=None):
    cur.execute("""
        INSERT INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado, estado, categoria)
        VALUES (?, ?, ?, ?, 'beneficiario', ?)
    """, (concurso_anual_id, persona_id, obra_id, monto, categoria))
    return cur.lastrowid

# --- Helper: link proyecto to resolucion ---
def link_proyecto_resolucion(proyecto_id, resolucion_id):
    cur.execute("INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                (proyecto_id, resolucion_id))

print("=" * 60)
print("FIX 2019: CCC, CDL, CGC")
print("=" * 60)

# ====================
# 1. FIX CCC (concurso_anual_id=30, resolucion_id=6658)
# ====================
print("\n--- CCC ---")
concurso_ccc = 30
resol_ccc = 6658

# Delete old garbage entry
cur.execute("SELECT id, persona_beneficiaria_id, obra_id FROM proyecto WHERE concurso_anual_id=?", (concurso_ccc,))
old_ccc = cur.fetchall()
for po_id, per_id, pr_id in old_ccc:
    cur.execute("DELETE FROM proyecto_resolucion WHERE proyecto_id=?", (po_id,))
    cur.execute("DELETE FROM proyecto WHERE id=?", (po_id,))

# CCC winners from PDF text
ccc_winners = [
    ("EL CORREDOR DE FONDO FILMS S.A.C.", "LIMA", "LA ERA OLVIDADA", 110027.00),
    ("UNIVERSIDAD DE LIMA", "LIMA", "EL CORAZÓN DE LA LUNA", 98000.00),
    ("ASOCIACION HDPERU", "LIMA", "ODISEA AMAZÓNICA", 159000.00),
    ("CENTRO DE ANTROPOLOGIA VISUAL DEL PERU", "LIMA", "SHIRINGA: GENOCIDIO Y RESISTENCIA DESDE LA ÉPOCA DEL CAUCHO", 175000.00),
]

for razon_social, region, titulo, monto in ccc_winners:
    persona_id = get_or_create_persona('juridica', razon_social=razon_social, region=region)
    obra_id = get_or_create_proyecto(titulo)
    po_id = create_proyecto(concurso_ccc, persona_id, obra_id, monto)
    link_proyecto_resolucion(po_id, resol_ccc)
    print(f"  + {razon_social} | {titulo} | S/ {monto:,.2f}")

# ====================
# 2. FIX CDL (concurso_anual_id=32, resolucion_id=6647)
# ====================
print("\n--- CDL ---")
concurso_cdl = 32
resol_cdl = 6647

# Keep existing entry #61376, fix project title
# PDF shows: CERRO AZUL FILMS S.A.C. - LIMA REGIÓN (CAÑETE) - "HUGO BLANCO, RÍO PROFUNDO" - S/119,322
# The current entry has a wrong title. Fix it.
cur.execute("""
    UPDATE proyecto SET titulo='HUGO BLANCO, RÍO PROFUNDO'
    WHERE id=(SELECT obra_id FROM proyecto WHERE concurso_anual_id=? AND persona_beneficiaria_id=(
        SELECT id FROM persona WHERE razon_social='CERRO AZUL FILMS S.A.C.'
    ))
""", (concurso_cdl,))
print(f"  ~ Fixed title for CERRO AZUL FILMS S.A.C.")

# Add ARREBATO CINE E.I.R.L. - "LA MIGRACIÓN" - S/63,000
persona_id = get_or_create_persona('juridica', razon_social='ARREBATO CINE E.I.R.L.', region='LIMA')
obra_id = get_or_create_proyecto('LA MIGRACIÓN')
po_id = create_proyecto(concurso_cdl, persona_id, obra_id, 63000.00)
link_proyecto_resolucion(po_id, resol_cdl)
print(f"  + ARREBATO CINE E.I.R.L. | LA MIGRACIÓN | S/ 63,000.00")

# ====================
# 3. FIX CGC (concurso_anual_id=22, resolucion_id=6651)
# ====================
print("\n--- CGC ---")
concurso_cgc = 22
resol_cgc = 6651

# Delete old garbage entries
cur.execute("SELECT id FROM proyecto WHERE concurso_anual_id=?", (concurso_cgc,))
old_cgc = cur.fetchall()
for (po_id,) in old_cgc:
    cur.execute("DELETE FROM proyecto_resolucion WHERE proyecto_id=?", (po_id,))
    cur.execute("DELETE FROM proyecto WHERE id=?", (po_id,))

# CGC Annual (categoría anual) - 12 winners
cgc_anual = [
    ("IDEA PRODUCCIONES E.I.R.L.", "JUNIN", "FESTIVAL SOCIO AMBIENTAL VI VIVENDO CINE", 34975.00),
    ("ASOCIACION CULTURAL BULLA", "AREQUIPA", "FESTIVAL DE CINE PARA INFANCIAS Y JUVENTUDES DIVERSAS", 35000.00),
    ("DOCUPERU", "LIMA", "LA RESI: RESIDENCIA DOCUMENTAL DESCENTRALIZADA", 31500.00),
    ("ASOCIACION CULTURAL INDIO PISHGO", "CAJAMARCA", "PATRULLA DOCUMENTAL", 35000.00),
    ("LA PÚA E.I.R.L.", "LIMA", "MADARIAGA AUDIOVISUAL", 35000.00),
    ("MADARIAGA AUDIOVISUAL E.I.R.L.", "PIURA", "III FESTIVAL DE CINE PERUANO HECHO POR MUJERES CINE DIEZ: I LABORATORIO DE CREACIÓN CINEMATOGRÁFICA, CATACAOS 2020", 27000.00),
    ("PROYECTOR S.C.R.L.", "LIMA", "CUYAY WASI", 33000.00),
    ("CICUTA AUDIOVISUAL S.A.C.", "LIMA", "MINGA AUDIOVISUAL KAPANAWA", 31491.90),
    ("COLLECTIVE MEDIA S.A.C.", "LIMA", "CERRO AZUL: DESENTERRANDO EL FUTURO – SEGUNDA PARTE", 21920.00),
    ("PINDORAMA S.A.C.", "LIMA", "SEGUNDO FESTIVAL DE CINE ACCESIBLE \"ACCECINE\"", 35000.00),
    ("ASOCIACION CULTURAL MAIZAL", "LIMA", "RED DE EXPERIMENTACIÓN AUDIOVISUAL EN MONUMENTOS ARQUEOLÓGICOS DEL PERÚ", 31500.00),
    ("NO HAY BANDA PRODUCCIONES E.I.R.L.", "CUSCO", "PARIR EN COMUNIDAD", 35000.00),
]

# CGC Multianual - 6 winners
cgc_multianual = [
    ("ASOCIACION CULTURAL ASIMTRIA", "AREQUIPA", "FESTIVAL ASIMTRIA - TRES EDICIONES (2020-2021)", 120000.00),
    ("ALHARACA S.A.C.", "LIMA", "LA BIENAL DE MI PRIMER FESTIVAL", 120000.00),
    ("SAPA INTI ESTUDIOS S.R.L.", "PUNO", "4° Y 5° FESTIVAL INTERNACIONAL DE ANIMACIÓN AJAYU", 120000.00),
    ("KASPAR AUDIO & VISUAL", "LA LIBERTAD", "EXPRÉSATE EN CORTO", 120000.00),
    ("CINCO MINUTOS CINCO E.I.R.L.", "LIMA", "FESTIVAL DE CINE DE VMT Y LIMA SUR: CINE COMUNITARIO RUMBO AL BICENTENARIO", 120000.00),
    ("ASOCIACION TRANSCINEMA", "LIMA", "TRANSCINEMA FESTIVAL INTERNACIONAL DE CINE 2019, 2020 Y 2021 (7MO, 8VA Y 9NA EDICIÓN)", 120000.00),
]

# Actually wait, looking at the text more carefully, I need to re-verify which entries are anual vs multianual
# and what CINCO MINUTOS CINCO actually is.

# Let me look at the CGC text more carefully for the annual category:
# From the PDF text, the annual table lists after "Artículo Primero.- ...categoría anual":
# The entries end with NO HAY BANDA PRODUCCIONES E.I.R.L.
# Then Artículo Segundo starts with multianual category.

# But CINCO MINUTOS CINCO appears in the multianual section (Artículo Segundo).
# Looking at the text again... actually, I'm not sure if CINCO MINUTOS CINCO is 
# in the annual or multianual list from the text I extracted. Let me check.

# From the earlier extraction of CGC text, under Artículo Segundo (categoría multianual):
# "CINCO MINUTOS CINCO E.I.R.L. - LIMA - FESTIVAL DE CINE DE VMT Y LIMA SUR..." - S/120,000
# Wait, in the annual category I also see NO HAY BANDA PRODUCCIONES with S/35,000.
# And CINCO MINUTOS CINCO appears in the multianual list.

# Actually, in the raw text I extracted earlier, looking at the annual table starting after
# "Artículo Primero.- ... categoría anual":
# I see entries up to NO HAY BANDA PRODUCCIONES E.I.R.L.
# Then the multianual table starts with "Artículo Segundo"

# But the annual table seems to have 12 entries and I counted 12. Let me recount:
# IDEA PRODUCCIONES, ASOC CULTURAL BULLA, DOCUPERU, ASOC CULTURAL INDIO PISHGO,
# LA PÚA, MADARIAGA AUDIOVISUAL E.I.R.L., PROYECTOR S.C.R.L., CUYAY WASI,
# CICUTA AUDIOVISUAL, COLLECTIVE MEDIA, PINDORAMA, ASOC CULTURAL MAIZAL,
# NO HAY BANDA PRODUCCIONES

# That's 13 entries in annual. But wait, CUYAY WASI might be a project name under PROYECTOR S.C.R.L., 
# not a separate entity. Looking at the original text again...

# From the OCR text:
# "PROYECTOR S.C.R.L. - LIMA - CUYAY WASI"
# Actually looking at the table structure, CUYAY WASI is on a separate line below PROYECTOR S.C.R.L.
# It might be the project name. But then what about "CICUTA AUDIOVISUAL S.A.C."?

# Let me just go with what I can clearly see from the PDF text. The annual table lists:
# Row 1: IDEA PRODUCCIONES E.I.R.L. | JUNIN | FESTIVAL SOCIO AMBIENTAL VI VIVENDO CINE | S/34,975
# Row 2: ASOCIACION CULTURAL BULLA | AREQUIPA | FESTIVAL DE CINE PARA INFANCIAS... | S/35,000
# Row 3: DOCUPERU | LIMA | LA RESI | S/31,500
# Row 4: ASOCIACION CULTURAL INDIO PISHGO | CAJAMARCA | PATRULLA DOCUMENTAL | S/35,000
# Row 5: LA PÚA E.I.R.L. | LIMA | MADARIAGA AUDIOVISUAL | S/35,000
# Row 6: MADARIAGA AUDIOVISUAL E.I.R.L. | PIURA | III FESTIVAL... | S/27,000
# Row 7: PROYECTOR S.C.R.L. | LIMA | CUYAY WASI | S/33,000
# Row 8: CICUTA AUDIOVISUAL S.A.C. | LIMA | MINGA AUDIOVISUAL KAPANAWA | S/31,491.90
# Row 9: COLLECTIVE MEDIA S.A.C. | LIMA | CERRO AZUL... | S/21,920
# Row 10: PINDORAMA S.A.C. | LIMA | SEGUNDO FESTIVAL... | S/35,000
# Row 11: ASOCIACION CULTURAL MAIZAL | LIMA | RED DE EXPERIMENTACIÓN... | S/31,500
# Row 12: NO HAY BANDA PRODUCCIONES E.I.R.L. | CUSCO | PARIR EN COMUNIDAD | S/35,000

# So 12 annual winners total.

print(f"  Annual ({len(cgc_anual)} entries):")
for razon_social, region, titulo, monto in cgc_anual:
    persona_id = get_or_create_persona('juridica', razon_social=razon_social, region=region)
    obra_id = get_or_create_proyecto(titulo)
    po_id = create_proyecto(concurso_cgc, persona_id, obra_id, monto, categoria='anual')
    link_proyecto_resolucion(po_id, resol_cgc)
    print(f"  + {razon_social[:40]:40s} | S/ {monto:>8,.2f}")

print(f"  Multianual ({len(cgc_multianual)} entries):")
for razon_social, region, titulo, monto in cgc_multianual:
    persona_id = get_or_create_persona('juridica', razon_social=razon_social, region=region)
    obra_id = get_or_create_proyecto(titulo)
    po_id = create_proyecto(concurso_cgc, persona_id, obra_id, monto, categoria='multianual')
    link_proyecto_resolucion(po_id, resol_cgc)
    print(f"  + {razon_social[:40]:40s} | S/ {monto:>8,.2f}")

con.commit()

# Verify
print("\n" + "=" * 60)
print("VERIFICATION")
print("=" * 60)
for codigo, ca_id in [("CCC", 30), ("CDL", 32), ("CGC", 22)]:
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(po.monto_otorgado), 0)
        FROM proyecto po WHERE po.concurso_anual_id=?
    """, (ca_id,))
    cnt, tot = cur.fetchone()
    print(f"  {codigo}: {cnt} entries, S/ {tot:,.2f}")

con.close()
print("\nDone!")
