#!/usr/bin/env python3
"""
TARGETED FIXES for 2019 data, manually verified against DAFO 2019 PDF.

Only changes I am 100% certain about after manual PDF review:
1. Garbled obra titles (verified from PDF)
2. NULL razon_social (persona records need names filled in)
3. Concatenation artifacts in persona names ("L", "ARE" suffixes)
4. Truly missing projects
"""
import os, sqlite3, sys

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
DRY_RUN = '--run' not in sys.argv

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

def fix_titles():
    """Fix garbled obra titles, verified from PDF."""
    fixes = {
        # CPF "Desarrollo de Proyectos de Largometraje"
        61358: 'NO HAY IDA SIN RETORNO',
        61360: 'LA VIDA PARTIDA',
        61362: 'LAS ÚLTIMAS CONSECUENCIAS',
        61363: 'EL ARTE DE LA GUERRA',
        61364: 'AMIT Y EL SUEÑO TANDOORI',
        61366: 'CUSI YUPANQUI',
        61367: 'UKU PACHA (INFRAMUNDO)',
        61369: 'CRISTINA GÁLVEZ',
        61370: 'NO HAY REGRESO A CASA',
        61374: 'ROSA CUCHILLO',
        61375: 'UN MUNDO PARA ZIGGY',
        61378: 'MANIFESTA',
        61379: 'ESTADOS GENERALES',
        61380: 'EL CHUTO',
        61381: 'BUSCARÉ EN TU VOZ',
        # CPC "Cortometraje"
        61405: 'ALBA',
        61407: 'EL DÍA DE MI SUERTE',
        61408: 'MADRE AGUA',
        61402: 'KK\'AIRA MARKA (CIUDAD RANA)',
        61403: 'DERMA',
        61404: 'SCÁMARA',
        # CPF "Largometraje de Ficción"
        61426: 'VIGILADOS',
        61430: 'DELIVERY GIRL',
        61431: 'VIEJAS AMIGAS',
        61432: 'DONDE DUERMEN LOS SUEÑOS',
        # CDO "Documental Formato Largo"
        61411: 'YAKUQÑAN CAMINOS DEL AGUA',
        61414: 'EL PECADO SOCIAL',
        61415: 'SONIDO AMAZÓNICO',
        61417: 'EL MALDITO BASTARDO',
        61418: 'EL COLOR DEL CIELO',
        # CBI "Cortometrajes del Bicentenario"
        61340: 'BERNARDO DE MONTEAGUDO',
        61341: 'VARIACIONES DE UNA INDEPENDENCIA',
        61342: 'UN VIAJE POR LA IDENTIDAD PERUANA A TRAVÉS DE LOS PUEBLOS INDÍGENAS',
        # CGS
        61423: 'MICROCINE CHASKIMAC',
        61424: 'SALA OLAYA',
        # CDL
        61376: 'DISTRIBUCIÓN PROFUNDA',
        # PDS
        61440: 'GUERREROS - ALCANZANDO SUEÑOS',
        61441: 'EL LENGUAJE INVISIBLE - NACHI',
        61442: 'PATRIA AFRO - PATRIA SAMA',
    }
    
    fixed = 0
    skipped = 0
    for pid, new_title in sorted(fixes.items()):
        cur = db.execute("""
            SELECT o.titulo, o.id FROM proyecto p
            JOIN obra o ON o.id = p.obra_id
            WHERE p.id = ?
        """, (pid,))
        row = cur.fetchone()
        if row:
            current = (row['titulo'] or '').strip().upper()
            new_up = new_title.upper().strip()
            if current != new_up:
                if DRY_RUN:
                    print(f"  TITLE P{pid}: '{current[:45]}' → '{new_title[:45]}'")
                else:
                    # Check if title already exists in another obra record
                    exists = db.execute("SELECT id FROM obra WHERE titulo = ? AND id != ?",
                                       (new_title, row['id'])).fetchone()
                    if exists:
                        print(f"  SKIP P{pid}: '{new_title[:45]}' already exists in obra_id={exists['id']}")
                        skipped += 1
                        continue
                    db.execute("UPDATE obra SET titulo = ? WHERE id = ?", (new_title, row['id']))
                    print(f"  TITLE P{pid}: ✓ '{new_title[:45]}'")
                    db.commit()
                fixed += 1
            else:
                pass  # Already correct
        else:
            print(f"  WARN P{pid}: no obra record found")
    if skipped:
        print(f"  Skipped {skipped} titles due to UNIQUE conflicts (manual fix needed)")
    
    return fixed

def fix_prefix_suffix():
    """Fix 'L', 'ARE' suffix artifacts from concatenation cleanup in persona names."""
    fixes = {
        # CPF persona names with artifacts
        61362: ('VIA EXPRESA ARE CINE Y VIDEO S.R.L', 'VIA EXPRESA CINE Y VIDEO S.R.L.'),
        61363: ('AUTOCINEMA L FILMS S.A.C', 'AUTOCINEMA FILMS S.A.C.'),
        61364: ('MERTHIOLATE PRODUCCIONES L E.I.R.L', 'MERTHIOLATE PRODUCCIONES E.I.R.L.'),
        61366: ('POR DOS PRODUCCIONES L S.A.C', 'POR DOS PRODUCCIONES S.A.C.'),
        61367: ('EL TOPO L PRODUCCIONES S.A.C', 'EL TOPO PRODUCCIONES S.A.C.'),
        61368: ('INVISIBLE CINE L E.I.R.L', 'INVISIBLE CINE E.I.R.L.'),
        61370: ('MEDIAPANGEA L S.A.C', 'MEDIAPANGEA S.A.C.'),
        61371: ('KONSTELACION - PRODUCTORA ARE AUDIOVISUAL E.I.R.L', 'KONSTELACION - PRODUCTORA AUDIOVISUAL E.I.R.L.'),
        61429: ('CINE DE BARRIO E.I.R.L. L', 'CINE DE BARRIO E.I.R.L.'),
        61431: ('FUNNY GAMES FILMS S.A.C', 'FUNNY GAMES FILMS S.A.C.'),
        # CPF suffix fix
        61405: ('WUF PRODUCCIONES S.A.C', 'WUF PRODUCCIONES S.A.C.'),
        61432: ('BONZO FILMS E.I.R.L', 'BONZO FILMS E.I.R.L.'),
        # CPC suffix fix
        61349: ('POR DOS PRODUCCIONES S.A.C', 'POR DOS PRODUCCIONES S.A.C.'),
        61352: ('HOLA FAMAS S.A.C', 'HOLA FAMAS S.A.C.'),
        # CDO suffix fix
        61413: ('LA GORDA FILMS S.A.C', 'LA GORDA FILMS S.A.C.'),
        61415: ('SACHA CINE S.A.C.', 'SACHA CINE S.A.C.'),  # already has .
        61417: ('BLUE PRODUCCIONES EIRL', 'BLUE PRODUCCIONES E.I.R.L.'),
        # NULL persona projects - fix the persona record directly
    }
    
    # Use persona_id from the proyecto to update razon_social
    pid_to_persona = {}
    for pid in list(fixes.keys()):
        cur = db.execute("SELECT persona_beneficiaria_id FROM proyecto WHERE id = ?", (pid,))
        row = cur.fetchone()
        if row and row[0]:
            pid_to_persona[pid] = row[0]
    
    # Check current razon_social
    for pid, (old_raz, new_raz) in sorted(fixes.items()):
        pid_id = pid_to_persona.get(pid)
        if not pid_id:
            print(f"  WARN P{pid}: no persona_beneficiaria_id")
            continue
        cur = db.execute("SELECT id, razon_social FROM persona WHERE id = ?", (pid_id,))
        row = cur.fetchone()
        if row:
            current = (row['razon_social'] or '').strip()
            if current != new_raz:
                if DRY_RUN:
                    print(f"  PERSONA P{pid}: id={pid_id} '{current[:40]}' → '{new_raz[:40]}'")
                else:
                    db.execute("UPDATE persona SET razon_social = ? WHERE id = ?", (new_raz, pid_id))
                    db.commit()
                    print(f"  PERSONA P{pid}: id={pid_id} ✓ '{new_raz[:40]}'")
        else:
            print(f"  WARN persona id={pid_id} not found for P{pid}")

def fix_null_personas():
    """Fill in NULL razon_social for existing persona records."""
    fixes = {
        # (persona_id, new_razon_social) - verified from PDF
        9924: 'WOMB E.I.R.L.',
        9925: 'ARCADIA VISUAL E.I.R.L.',
        9926: 'JAMES MAKI S.R.L.',
        9937: 'SAQRA PROCESOS COMUNICATIVOS S.R.L.',
        9940: 'PANOGRAMA LABS E.I.R.L.',
    }
    
    fixed = 0
    for pid, razon in sorted(fixes.items()):
        cur = db.execute("SELECT id, razon_social FROM persona WHERE id = ?", (pid,))
        row = cur.fetchone()
        if row:
            current = (row['razon_social'] or '').strip()
            if not current or current != razon:
                if DRY_RUN:
                    print(f"  PERSONA id={pid}: '{current or 'NULL'}' → '{razon}'")
                else:
                    db.execute("UPDATE persona SET razon_social = ? WHERE id = ?", (razon, pid))
                    db.commit()
                    print(f"  PERSONA id={pid}: ✓ '{razon}'")
                fixed += 1
        else:
            print(f"  WARN persona id={pid} not found")
    
    # Also check specific project-to-persona mappings
    # P61353 → persona_id=9924 → WOMB E.I.R.L.
    # P61355 → persona_id=9792 → MYXOMATOSIS KINO E.I.R.L.
    # P61412 → persona_id=9937 → SAQRA PROCESOS COMUNICATIVOS S.R.L.
    # P61436 → persona_id=9940 → PANOGRAMA LABS E.I.R.L.
    # P61418 → no persona, but should be SONTRAC S.AC. with title "EL COLOR DEL CIELO"
    
    return fixed

def add_missing_projects():
    """Add truly missing projects found in PDF but not in DB."""
    # TODO: This requires creating persona + obra + proyecto records
    # which is more involved. For now, just report them.
    print("\n  --- Missing projects (not yet added) ---")
    print("  CPC: Virent S.R.L. → El motor y la melodía")
    print("  CPC: CDO/Huaca Rajada etc → need concurso reassignment")
    print("  CBI: Candu Films S.A.C. → Palabras Urgentes")
    print("  NMA: Artefactos Films E.I.R.L. → Aline")
    print("  CGS: needs full audit")
    print("  CIN: needs full audit")
    print("  PDS: Alelo Films, Totora, Maretazo, Cayumba (PDS), etc.")
    print("  EPI: needs full audit")

# ---- Main ----
print(f"{'='*60}")
print(f"FIX 1: Garbled obra titles")
print(f"{'='*60}")
fixed_t = fix_titles()

print(f"\n{'='*60}")
print(f"FIX 2: Persona name artifacts (L/ARE suffixes)")
print(f"{'='*60}")
fix_prefix_suffix()

print(f"\n{'='*60}")
print(f"FIX 3: NULL razon_social")
print(f"{'='*60}")
fix_null_personas()

print(f"\n{'='*60}")
print(f"FIX 4: Missing projects")
print(f"{'='*60}")
add_missing_projects()

print(f"\nTitles fixed: {fixed_t}")
if DRY_RUN:
    print("Use --run to apply")

db.close()
