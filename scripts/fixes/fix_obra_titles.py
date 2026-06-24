#!/usr/bin/env python3
"""
Reconstruct garbled obra titles from PDF extraction artifacts.

Strategy: for titles with extra spaces (multi-column PDF capture),
take the first meaningful fragment as the title. For completely
garbled titles, flag for PDF re-extraction.

Usage:
  python3 fix_obra_titles.py            # dry-run
  python3 fix_obra_titles.py --run      # apply fixes
"""
import sqlite3, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH

RUN = "--run" in sys.argv
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

SHORT_WORDS = {'A','E','Y','O','LA','EL','LO','AL','DEL','EN','UN','SU',
               'DE','SE','NO','MI','TU','SUS','LOS','LAS','CON','POR',
               'QUE','FUE','ES','YA','HA','HI','VA','VE','DA','LE','ME',
               'TE','SI','NI','3D','2D','II','IV','VI','V','X','8M','S/.'}

def is_garbled(t):
    t = t.strip()
    if len(t) < 5:
        return True
    if re.search(r'S/[\s\d,]+', t): return True
    if re.search(r'(DNI|RUC)\s*N?°?\s*\d', t): return True
    if re.search(r'  {2,}', t): return True
    words = re.split(r'[\s,]+', t)
    short_bad = [w for w in words if len(w) <= 2 and w.upper() not in SHORT_WORDS]
    if len(words) >= 3 and len(short_bad) / len(words) > 0.5:
        return True
    return False

def looks_like_title_fragment(text):
    t = text.strip().rstrip(',;:')
    if len(t) < 5:
        return False
    # Reject person-name patterns (Surname, Name)
    if re.match(r'^[A-ZÁÉÍÓÚÑÜ ]+,[ \t]*[A-ZÁÉÍÓÚÑÜ ]+', t):
        return False
    # Reject if mostly single letters
    words = t.split()
    single = sum(1 for w in words if len(w) <= 1 and w.isalpha())
    if len(words) >= 3 and single > len(words) * 0.3:
        return False
    # Must have at least one word longer than 3 chars
    if not any(len(w) > 3 for w in words):
        return False
    return True

def recover_title(t):
    t = t.strip()
    fragments = re.split(r'  +', t)
    fragments = [f.strip() for f in fragments if f.strip()]
    for f in fragments:
        clean = re.sub(r'^[\s\.\,\-\/\)\]\(\[]+', '', f)
        clean = re.sub(r'[\s\.\,\-\/\(\)\[\]"]+$', '', clean)
        if looks_like_title_fragment(clean):
            return clean
    return None

print(f"{'RUN MODE' if RUN else 'DRY RUN'} — DB: {DB_PATH}")
print("=" * 60)

c.execute("""
  SELECT o.id, o.titulo, lc.codigo, c.anio
  FROM obra o
  JOIN proyecto po ON po.obra_id = o.id
  JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
  JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
  JOIN convocatoria c ON c.id = ca.convocatoria_id
  ORDER BY o.id
""")
rows = c.fetchall()

recoverable = []
unrecoverable = []

for oid, titulo, codigo, anio in rows:
    if not is_garbled(titulo):
        continue
    recovered = recover_title(titulo)
    if recovered:
        recoverable.append((oid, recovered, titulo, codigo, anio))
    else:
        unrecoverable.append((oid, titulo, codigo, anio))

print(f"\nTotal problemáticos: {len(recoverable) + len(unrecoverable)}")
print(f"Recuperables:        {len(recoverable)}")
print(f"Requieren PDF:       {len(unrecoverable)}")

if recoverable:
    print(f"\n--- Títulos a corregir ---")
    for oid, new_t, old_t, codigo, anio in recoverable:
        print(f"  ID {oid:4d} [{codigo} {anio}] '{old_t[:60]}'")
        print(f"         → '{new_t}'")
        if RUN:
            # Check if another obra already uses this title
            cur = c.execute("SELECT id FROM obra WHERE titulo = ? AND id != ?", (new_t, oid))
            conflict = cur.fetchone()
            if conflict:
                new_t_suffixed = f"{new_t} [{codigo} {anio}]"
                print(f"         ⚠ conflicto con obra {conflict[0]}, usando '{new_t_suffixed}'")
                c.execute("UPDATE obra SET titulo = ? WHERE id = ?", (new_t_suffixed, oid))
            else:
                c.execute("UPDATE obra SET titulo = ? WHERE id = ?", (new_t, oid))

if unrecoverable:
    print(f"\n--- Títulos que requieren re-extracción PDF ---")
    for oid, t, codigo, anio in unrecoverable:
        print(f"  ID {oid:4d} [{codigo} {anio}] '{t[:70]}'")

if RUN:
    conn.commit()
    print(f"\n✅ {len(recoverable)} títulos actualizados.")
    print(f"⚠  {len(unrecoverable)} títulos requieren re-extracción manual de PDFs.")
else:
    print(f"\nUsa --run para aplicar {len(recoverable)} correcciones.")

conn.close()
