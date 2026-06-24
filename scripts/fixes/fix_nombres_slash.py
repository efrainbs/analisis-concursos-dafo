#!/usr/bin/env python3
"""
Fix personas with "/" and "S/" artifacts in names.
- Splits "/" concatenations into individual persona records
- Removes "S/" monetary artifacts  
- Fixes garbled names (missing first letters from PDF extraction)
"""
import os, re, sqlite3, sys

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
db.execute("PRAGMA foreign_keys = ON")

rows = db.execute("""
    SELECT id, nombres, apellidos FROM persona
    WHERE (nombres LIKE '%/%' OR apellidos LIKE '%/%'
           OR nombres LIKE '%S/%' OR nombres LIKE '%S/.%')
    ORDER BY id
""").fetchall()

# Define fixes for each persona ID: (nombres_final, apellidos_final) for the first person,
# plus extra personas to create as (nombres, apellidos)
# If 'skip', mark as needs manual review
FIXES = {
    # Clean splits (confident two-person concatenations)
    7960: {
        'first': ('JOSE ALBERTO', 'OSORIO VILLANUEVA'),
        'extra': [('JORGE GABRIEL', 'TEJADA SALAZAR')],
    },
    8492: {
        'first': ('CARLOS ALBERTO', 'SANCHEZ GIRALDO'),
        'extra': [('BETTY ISABEL', 'MADUEÑO MEDINA')],
    },
    8494: {
        'first': ('BEATRIZ AMELIA', 'TORRES ZEGARRA'),
        'extra': [('RUTH DIANA', 'CASTRO SANCHEZ')],
    },
    8496: {
        'first': ('JOSE CARLOS', 'GARCIA ANGULO'),
        'extra': [('PATRICIA', 'CABRERIZO REY DE CASTRO'),
                  ('REBECA FERNANDA', 'ALVAN LEON')],
    },
    8502: {
        'first': ('MARIO GONZALO', 'BENAVENTE SECCO'),
        'extra': [('GRECIA DANIELLA', 'BARBIERI RODRIGUEZ')],
    },
    8504: {
        'first': ('NICOLAS', 'SABA SALEM'),
        'extra': [('MORELLA', 'MORET CHIAPPE')],
    },
    8508: {
        'first': ('MANUEL HUMBERTO', 'FERREYROS MORENO'),
        'extra': [('LORENA NOEMI', 'UGARTECHE BARO')],
    },
    8512: {
        'first': ('GIANMARCO GUSTAVO', 'CASTILLO AGÜERO'),
        'extra': [('ILLARI MARIA', 'ORCCOTTOMA MENDOZA')],
    },
    8516: {
        'first': ('LARISA', 'BARREDA AYLLON'),
        'extra': [('YAELA BETSABE', 'GOTTLIEB RAMIREZ')],
    },
    8521: {
        'first': ('JULIA MARIA', 'NATERS ROMERO'),
        'extra': [('CARLOS LUIS', 'RIVAS VIDAL'),
                  ('LOSHUA VALERIA', 'FLORES GUERRA BAMONDE')],
    },
    8550: {
        'first': ('JOSE JAVIER', 'FERNANDEZ DEL RIO'),
        'extra': [('TITO', 'JARA HURTADO')],
    },
    8582: {
        'first': ('GIANPIERRE JUAN MANUEL', 'YOVERA INFANZON'),
        'extra': [('FRANCISCO MIGUEL', 'PASACHE LAZO')],
    },
    8593: {
        'first': ('DAMIAN ALEXANDER', 'LUNA PICON'),
        'extra': [('BETTY ISABEL', 'MADUEÑO MEDINA')],
    },
    8599: {
        'first': ('ROSEMARIE', 'LERNER RIZO PATRON'),
        'extra': [('NICOLAS ALFREDO', 'LANDA TAMI')],
    },
    8614: {
        'first': ('VIOLA', 'VAROTTO'),
        'extra': [('MAURICIO JOSE', 'GODOY PAREDES')],
    },
    9344: {
        'first': ('MAGALY GIOVANNA', 'TORRES BARRIENTOS'),
        'extra': [('MARCO LUIS', 'VERA GALLEGOS')],
    },

    # Garbled: missing first letter
    7923: {
        'first': ('LIZ A', 'FERNANDEZ'),
        'extra': [('DANIEL', 'LAGARES REZ')],
    },
    7944: {
        'first': ('ANTONIO BILL', None),  # Can't determine first letter - flag
    },

    # S/ artifact cases - remove S/ and fix
    9052: {
        'first': ('ROY', 'MELGAR CARI'),
    },
    9082: {
        'first': ('SONIA ANGELICA', 'TOLEDO ONES'),
        'extra': [('PEDRO', 'VIZ VIVANCO')],
    },

    # Complex cases (mark for review)
    8132: 'REVIEW',
    8226: 'REVIEW',
    8581: 'REVIEW',
    9069: 'REVIEW',
    9169: 'REVIEW',
    9188: 'REVIEW',
    9268: 'REVIEW',
    9278: 'REVIEW',
    9297: 'REVIEW',
    9322: 'REVIEW',
    9348: 'REVIEW',
    9354: 'REVIEW',
}

DRY_RUN = '--run' not in sys.argv

if DRY_RUN:
    print("=== DRY RUN ===")
    print()

for pid, fix in sorted(FIXES.items()):
    r = db.execute("SELECT id, nombres, apellidos FROM persona WHERE id=?", (pid,)).fetchone()
    if not r:
        print(f"ID {pid}: NOT FOUND in DB")
        continue

    if fix == 'REVIEW':
        print(f"ID {pid}: {r['nombres']} {r['apellidos']} → [REVIEW - needs manual check]")
        continue

    new_nom, new_ape = fix['first']
    extra = fix.get('extra', [])

    if DRY_RUN:
        print(f"ID {pid}: '{r['nombres']} {r['apellidos']}'")
        print(f"       → '{new_nom} {new_ape}'")
        for i, (en, ea) in enumerate(extra):
            print(f"       + new persona: '{en} {ea}'")
        continue

    # Apply fix
    db.execute("UPDATE persona SET nombres=?, apellidos=? WHERE id=?",
               (new_nom, new_ape, pid))

    # Get existing integrante links to replicate
    integrantes = db.execute(
        "SELECT proyecto_id, rol FROM proyecto_integrante WHERE persona_id=?", (pid,)
    ).fetchall()

    for en, ea in extra:
        if en and ea:
            cur = db.execute(
                "INSERT INTO persona (nombres, apellidos, tipo) VALUES (?, ?, 'natural')",
                (en, ea)
            )
            new_pid = cur.lastrowid
            for pi in integrantes:
                db.execute(
                    "INSERT OR IGNORE INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, ?)",
                    (pi['proyecto_id'], new_pid, pi['rol'])
                )
            print(f"ID {pid}: created persona {new_pid}: {en} {ea}")

    print(f"ID {pid}: updated → {new_nom} {new_ape}")

if not DRY_RUN:
    db.commit()
    print("\nCommitted!")
else:
    print("\nUse --run to apply changes")

db.close()
