#!/usr/bin/env python3
"""Analyze unrecoverable obra titles - which have resolution URLs."""
import sqlite3, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH

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
    if re.match(r'^[A-ZÁÉÍÓÚÑÜ ]+,[ \t]*[A-ZÁÉÍÓÚÑÜ ]+', t):
        return False
    words = t.split()
    single = sum(1 for w in words if len(w) <= 1 and w.isalpha())
    if len(words) >= 3 and single > len(words) * 0.3:
        return False
    if not any(len(w) > 3 for w in words):
        return False
    return True

def recover_title(t):
    t = t.strip()
    fragments = re.split(r'  +', t)
    fragments = [f.strip() for f in fragments if f.strip()]
    for f in fragments:
        clean = re.sub(r'^[\s\.,\-\/\)\]\[\(]+', '', f)
        clean = re.sub(r'[\s\.,\-\/\(\)\[\]"]+$', '', clean)
        if looks_like_title_fragment(clean):
            return clean
    return None

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("""
    SELECT o.id, o.titulo, lc.codigo, c.anio, r.url_pdf, po.monto_otorgado,
           po.persona_beneficiaria_id
    FROM obra o
    JOIN proyecto po ON po.obra_id = o.id
    JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    JOIN convocatoria c ON c.id = ca.convocatoria_id
    LEFT JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
    LEFT JOIN resolucion r ON r.id = pr.resolucion_id
    ORDER BY o.id
""")
rows = c.fetchall()

unrecoverable = []
for r in rows:
    oid, titulo, codigo, anio, url, monto, pbid = r
    if not is_garbled(titulo):
        continue
    if recover_title(titulo):
        continue
    unrecoverable.append(r)

print(f"Unrecoverable: {len(unrecoverable)}")
has_url = sum(1 for r in unrecoverable if r[4])
print(f"  With URL: {has_url}")
print(f"  Without URL: {len(unrecoverable) - has_url}")
print()

print("Unrecoverable by linea/year:")
from collections import Counter
ly_counts = Counter()
for r in unrecoverable:
    ly_counts[(r[2], r[3], r[4] is not None)] += 1
for (cod, anio, has_u), cnt in sorted(ly_counts.items()):
    print(f"  {cod} {anio} {'URL' if has_u else 'NO-URL'}: {cnt}")

print()
print("Without URL:")
for r in unrecoverable:
    if not r[4]:
        from urllib.parse import unquote
        print(f"  [{r[2]} {r[3]}] ID={r[0]} \"{r[1][:70]}\"")
