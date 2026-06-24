#!/usr/bin/env python3
"""Fix anomalous montos — conservative v2.

Rules:
- monto < 100: always ×1000 (clearly missing decimal → thousands)
- 100 ≤ monto < 1000: ×1000 only if result is within [0.5×min, 2×max]
- EPA 2025 duplicates: consolidate to one entry, keep amount as-is
- Don't touch EPI entries
"""

import sqlite3, os
from collections import defaultdict

DB_PATH = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")
BACKUP_PATH = DB_PATH + ".pre_fix_montos_v4"
os.system(f"cp {DB_PATH} {BACKUP_PATH}")
print(f"Backup: {BACKUP_PATH}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
c = conn.cursor()

TYPICAL_MIN = {'CBI': 50000, 'CCC': 40000, 'CCE': 10000, 'CCM': 180000,
    'CDC': 40000, 'CDO': 30000, 'CDV': 30000, 'CFO': 5000,
    'CGC': 30000, 'CGS': 50000, 'CIC': 190000, 'CIN': 30000,
    'CPA': 40000, 'CPC': 15000, 'CPF': 30000, 'EDI': 50000,
    'EPA': 40000, 'EPI': 1000, 'FCA': 10000, 'FCP': 100000,
    'NMA': 40000, 'PAL': 180000, 'PDS': 60000, 'PDT': 7000, 'DLO': 80000}
TYPICAL_MAX = {'CBI': 100000, 'CCC': 200000, 'CCE': 30000, 'CCM': 360000,
    'CDC': 150000, 'CDO': 450000, 'CDV': 150000, 'CFO': 600000,
    'CGC': 120000, 'CGS': 200000, 'CIC': 220000, 'CIN': 50000,
    'CPA': 550000, 'CPC': 80000, 'CPF': 850000, 'EDI': 120000,
    'EPA': 160000, 'EPI': 20000, 'FCA': 50000, 'FCP': 150000,
    'NMA': 80000, 'PAL': 200000, 'PDS': 80000, 'PDT': 15000, 'DLO': 100000}

def in_range_flex(monto, codigo):
    mn = TYPICAL_MIN.get(codigo, 0)
    mx = TYPICAL_MAX.get(codigo, 999999)
    # Allow 0.5× min and 2× max
    return (mn * 0.5) <= monto <= (mx * 2)

# ── 1. Fix anomalous montos ──
rows = c.execute("""
    SELECT po.id, po.monto_otorgado, lc.codigo
    FROM proyecto po
    JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    WHERE po.monto_otorgado > 0 AND po.monto_otorgado < 1000
""").fetchall()

fixed = 0
kept_anomalous = []
for r in rows:
    m = r['monto_otorgado']
    cod = r['codigo']
    candidate = m * 1000
    if m < 100:
        # Montos < 100 are always wrong; multiply even if slightly out of range
        c.execute("UPDATE proyecto SET monto_otorgado = ? WHERE id = ?", (candidate, r['id']))
        fixed += 1
    elif in_range_flex(candidate, cod):
        c.execute("UPDATE proyecto SET monto_otorgado = ? WHERE id = ?", (candidate, r['id']))
        fixed += 1
    else:
        kept_anomalous.append((r['id'], m, cod))

print(f"Fixed {fixed} montos (×1000)")
for aid, am, acod in kept_anomalous:
    print(f"  Kept anomalous: proyecto {aid}, monto {am}, linea {acod}")

# ── 2. Remove duplicate resolution ──
dups = c.execute("""
    SELECT r.id FROM resolucion r
    JOIN proyecto_resolucion pr ON pr.resolucion_id = r.id
    WHERE r.numero = '001167-2024-DGIA-VMPCIC/MC'
    ORDER BY r.id
""").fetchall()
if len(dups) > 1:
    for d in dups[1:]:
        c.execute("DELETE FROM proyecto_resolucion WHERE resolucion_id = ?", (d['id'],))
        c.execute("DELETE FROM resolucion WHERE id = ?", (d['id'],))
    print(f"Removed {len(dups)-1} duplicate resolution(s)")

# ── 3. Remove orphan resolutions ──
orphans = c.execute("""
    SELECT r.id FROM resolucion r
    LEFT JOIN proyecto_resolucion pr ON pr.resolucion_id = r.id
    WHERE pr.proyecto_id IS NULL
""").fetchall()
for o in orphans:
    c.execute("DELETE FROM resolucion WHERE id = ?", (o['id'],))
print(f"Removed {len(orphans)} orphan resolutions")

# ── 4. Consolidate EPA 2025 duplicates (keep amount, drop extras) ──
epa = c.execute("""
    SELECT po.id, po.monto_otorgado, ob.titulo, p.razon_social
    FROM proyecto po
    JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
    JOIN convocatoria co ON co.id = ca.convocatoria_id
    JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
    JOIN obra ob ON ob.id = po.obra_id
    JOIN persona p ON p.id = po.persona_beneficiaria_id
    WHERE co.anio = 2025 AND lc.codigo = 'EPA'
    ORDER BY ob.titulo
""").fetchall()

epa_groups = defaultdict(list)
for ed in epa:
    key = (ed['titulo'], ed['razon_social'] or '')
    epa_groups[key].append(ed)

del_epa = []
for k, group in epa_groups.items():
    if len(group) > 1:
        keep = group[0]
        # Don't multiply — amount is already correct (S/55k-S/80k)
        for g in group[1:]:
            del_epa.append(g['id'])
for did in del_epa:
    c.execute("DELETE FROM proyecto_integrante WHERE proyecto_id = ?", (did,))
    c.execute("DELETE FROM proyecto_resolucion WHERE proyecto_id = ?", (did,))
    c.execute("DELETE FROM proyecto WHERE id = ?", (did,))
print(f"Consolidated {len(del_epa)} EPA 2025 duplicates")

conn.commit()

# Summary
total = c.execute("SELECT printf('%.2f', SUM(monto_otorgado)) as t FROM proyecto").fetchone()['t']
cnt = c.execute("SELECT COUNT(*) as c FROM proyecto").fetchone()['c']
anom = c.execute("SELECT COUNT(*) FROM proyecto WHERE monto_otorgado > 0 AND monto_otorgado < 1000").fetchone()[0]
zeros = c.execute("SELECT COUNT(*) FROM proyecto WHERE monto_otorgado = 0").fetchone()[0]
print(f"\nProyectos: {cnt}")
print(f"Total: S/ {total}")
print(f"Montos < 1000: {anom}")
print(f"Montos cero: {zeros}")
print(f"Done! Backup at: {BACKUP_PATH}")

conn.close()
