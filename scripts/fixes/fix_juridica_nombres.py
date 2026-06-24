#!/usr/bin/env python3
"""
Fix concatenated juridica razon_social records.
Strategy per category:
  A) RUC/garbage suffix → strip trailing garbage
  B) Redundant long legal names → shorten to standard abbreviation
  C) True multi-company concatenation → take first valid name
"""
import sqlite3, re, unicodedata, sys

DB = '/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db'
DRY_RUN = '--run' not in sys.argv

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
db.execute("PRAGMA journal_mode=WAL")

# All concatenated IDs
all_ids = [8877,7722,9333,9258,7633,7663,8333,8713,8873,7664,9124,8131,8452,8876,7794,9195,7631,9018,9138,8580,7915,7957,9335,9140,7953,8711,8200,9076,8175,8710,7943,9210,7712,9167,7975,7584,8851,9267,8867,9353,9274,9199,9347,8027,9345,9256,7969,10471,9146,7838,8567,8712,7840,9009,8055,10486,7448,8706,8096,7446,9296,8169,8619,9187,7937,10648,7951]

def strip_ruc_suffix(name):
    """Strip trailing RUC number, region name, or garbage."""
    # (RUC N°... / (2060... / LA LIBERTAD / LO / LI / A
    name = re.sub(r'\s*\(RUC\s*N°.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(\d{11,}.*', '', name)
    name = re.sub(r'\s*\(2060\d*.*', '', name)
    # Single trailing word that's a region/department
    regions = ['LA LIBERTAD', 'LIMA', 'LAMBAYEQUE', 'PUNO', 'CUSCO', 'AREQUIPA', 'JUNIN',
               'JUNÍN', 'PIURA', 'AYACUCHO', 'CAJAMARCA', 'ANCASH', 'ÁNCASH', 'HUANUCO',
               'HUÁNUCO', 'ICA', 'SAN MARTIN', 'SAN MARTÍN', 'LORETO', 'TACNA', 'TUMBES',
               'UCAYALI', 'MADRE DE DIOS', 'MOQUEGUA', 'PASCO', 'APURIMAC', 'APURÍMAC',
               'AMAZONAS', 'HUANCAVELICA', 'HUANCAVELICA', 'CALLAO']
    for r in sorted(regions, key=len, reverse=True):
        if name.upper().endswith(' ' + r):
            name = name[:-(len(r)+1)]
        if name.upper().endswith(' ' + r + ')'):
            name = name[:-(len(r)+2)]
    # Single trailing letter that's truncated
    name = re.sub(r'\s+[AL]$', '', name)
    name = re.sub(r'\s+LO$', '', name)
    name = re.sub(r'\s+LI$', '', name)
    name = re.sub(r'\s+AR$', '', name)
    # Single trailing A after dot
    name = re.sub(r'\s*\.\s*A\s*$', '.', name)
    # Trailing "A (" after E.I.R.L. or just trailing " ("
    name = re.sub(r'\s*[A-Z]\s*\(.*', '', name)
    name = re.sub(r'\s*\(.*', '', name)
    return name.strip()

def shorten_legal_form(name):
    """Shorten long legal forms to standard abbreviations."""
    replacements = [
        (r'SOCIEDAD ANONIMA CERRADA\s*[-–—]+\s*', ''),
        (r'\s*[-–—]+\s*SOCIEDAD ANONIMA CERRADA', ''),
        (r'\bSOCIEDAD ANONIMA CERRADA\b', 'S.A.C.'),
        (r'\bSOCIEDAD ANONIMA A CERRADA\b', 'S.A.C.'),
        (r'\bSOCIEDAD COMERCIAL DE RESPONSABILIDAD LIMITADA\b', 'S.R.L.'),
        (r'\bEMPRESA INDIVIDUAL DE RESPONSABILIDAD LIMITADA\b', 'E.I.R.L.'),
        (r'\bEMPRESA INDIVIDUAL DE RESPONSABILIDA D LIMITADA\b', 'E.I.R.L.'),
        (r'\bEMPRESA INDIVIDUAL DE AR RESPONSABILIDAD LIMITADA\b', 'E.I.R.L.'),
        (r'\bINIDIVIDUAL\b', 'INDIVIDUAL'),
        # Clean up doubled abbreviations
        (r'\bS\.A\.C\.\s*[-–—]*\s*S\.A\.C\.?', 'S.A.C.'),
        (r'\bS\.R\.L\.\s*[-–—]*\s*S\.R\.L\.?', 'S.R.L.'),
        (r'\bE\.I\.R\.L\.\s*[-–—]*\s*E\.I\.R\.L\.?', 'E.I.R.L.'),
        # S.C.R.L. variant
        (r'\bSOCIEDAD COMERCIAL DE RESPONSABILIDAD LIMITADA\b', 'S.R.L.'),
        (r'\bS\.C\.R\.L\.', 'S.R.L.'),
    ]
    for pat, repl in replacements:
        name = re.sub(pat, repl, name, flags=re.IGNORECASE)
    return name.strip()

def extract_first_company(name):
    """From a multi-company concatenation, extract the first valid company name."""
    # Split on known company name boundaries
    # Patterns where one company ends and another begins
    # E.I.R.L. followed by uppercase text → likely next company
    # S.A.C. followed by uppercase text → likely next company
    # S.R.L. followed by uppercase text → likely next company
    
    # First try: split on company suffix + capital letter pattern
    parts = re.split(r'(E\.I\.R\.L\.|S\.A\.C\.|S\.R\.L\.|S\.A\.|SOCIEDAD ANONIMA CERRADA|SOCIEDAD COMERCIAL DE RESPONSABILIDAD LIMITADA|EMPRESA INDIVIDUAL DE RESPONSABILIDAD LIMITADA)\s+(?=[A-ZÁÉÍÓÚ])', name, maxsplit=1)
    
    if len(parts) >= 3:
        # parts[0] = before first suffix (empty usually)
        # parts[1] = first suffix
        # parts[2] = rest
        first = (parts[0] + parts[1]).strip()
        # Clean up
        first = re.sub(r'^\d+\.\s*', '', first)  # Remove leading "8. "
        return first
    
    # Second try: split at "S.A.C." or "E.I.R.L." 
    for sep in [' S.A.C. ', ' E.I.R.L. ', ' S.R.L. ']:
        parts = name.split(sep, 1)
        if len(parts) > 1:
            nxt = parts[1].strip()
            if nxt and len(nxt) > 3 and nxt[0].isupper():
                return parts[0] + sep.strip()
    
    return name

def fix_razon_social(pid, rs):
    """Attempt to fix a concatenated razon_social. Returns (fixed_name, fix_type) or None."""
    original = rs
    
    # Step 1: Strip RUC/garbage suffix
    rs = strip_ruc_suffix(rs)
    
    # Step 2: Handle "X LONG_FORM - X SHORT_FORM" duplication (Case B)
    # Pattern: same company name appears before and after the legal form separator
    long_forms = [
        ('SOCIEDAD ANONIMA CERRADA', 'S.A.C.'),
        ('SOCIEDAD COMERCIAL DE RESPONSABILIDAD LIMITADA', 'S.R.L.'),
        ('EMPRESA INDIVIDUAL DE RESPONSABILIDAD LIMITADA', 'E.I.R.L.'),
    ]
    for long_form, short_form in long_forms:
        # Pattern: "X LONG_FORM - X SHORT_FORM" or "X LONG_FORM - X SHORT"
        pat = re.compile(
            r'^(.+?)\s+' + re.escape(long_form) + r'\s*[-–—]+\s*\1\s+' +
            re.escape(short_form.rstrip('.')) + r'$',
            re.IGNORECASE
        )
        m = pat.match(rs.strip())
        if m:
            base = m.group(1).strip()
            rs = f'{base} {short_form}'
            if rs != original:
                return (rs, 'fixed')
    
    # Step 3: Shorten legal forms (for Case A: no short form present)
    rs = shorten_legal_form(rs)
    
    # Step 4: Check for multi-company concatenation (Case C)
    rs = extract_first_company(rs)
    
    # Step 5: Final cleanup
    rs = re.sub(r'\s+', ' ', rs).strip()
    # Remove trailing period before adding proper suffix
    rs = rs.rstrip('.')
    suffixes = ['S.A.C', 'S.R.L', 'E.I.R.L', 'S.A']
    for s in suffixes:
        if rs.endswith(s) and not rs.endswith(s + '.'):
            rs = rs + '.'
    
    if rs != original and len(rs) >= 5:
        return (rs, 'fixed')
    return None

# Special cases that need manual naming or override
SPECIAL_NAMES = {
    10486: 'CINECLUB INSOLITO S.A.C.',
    7448: 'S.R.L.',  # No company name extracted - just keep the legal form
    8867: 'NIVO STUDIOS S.A.C.',
    9140: 'FUEGO DEL 96 E.I.R.L.',
    8027: 'TARGET MKT E.I.R.L.',
    9333: 'AUDIO S.C.R.L.',
    9256: 'PRODUCTORA SANTIAGO E.I.R.L.',
    7633: 'AUTOCINEMA FILMS S.A.C.',
}

# Process all
changes = []
errors = []
for pid in all_ids:
    if pid in SPECIAL_NAMES:
        original = db.execute('SELECT razon_social FROM persona WHERE id = ?', (pid,)).fetchone()[0]
        fixed = SPECIAL_NAMES[pid]
        changes.append((pid, original, fixed))
        if not DRY_RUN:
            db.execute('UPDATE persona SET razon_social = ? WHERE id = ?', (fixed, pid))
        continue
    row = db.execute('SELECT id, razon_social FROM persona WHERE id = ?', (pid,)).fetchone()
    row = db.execute('SELECT id, razon_social FROM persona WHERE id = ?', (pid,)).fetchone()
    if not row:
        continue
    original = row['razon_social']
    result = fix_razon_social(pid, original)
    if result and result[0] != original:
        changes.append((pid, original, result[0]))
        if not DRY_RUN:
            db.execute('UPDATE persona SET razon_social = ? WHERE id = ?', (result[0], pid))

if not DRY_RUN:
        db.commit()

print(f"{'DRY RUN - ' if DRY_RUN else ''}Fixed {len(changes)} concatenated juridica names:\n")
for pid, orig, fixed in changes:
    print(f"  PID {pid}:")
    print(f"    Before: {orig[:80]}")
    print(f"    After:  {fixed[:80]}")
    print()

db.close()
if DRY_RUN:
    print(f"Run with --run to apply changes.")