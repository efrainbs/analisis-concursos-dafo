#!/usr/bin/env python3
"""
Asigna modalidad a CPF pre-2024 y CPA 2025 (Fase 2c - remanentes).

CPF pre-2024 tenía subcategorías diferentes a las actuales.
Se extraen de los nombres de PDF y del texto del Artículo Primero.

Uso:
  python3 assign_modalidades_fase2c_restantes.py            # dry-run
  python3 assign_modalidades_fase2c_restantes.py --run
"""
import sqlite3, sys, re, os, subprocess, urllib.parse, unicodedata
from collections import defaultdict
from dafo_common import DB_PATH, TMP_DIR

def detect_cpf_subcat(url):
    """Extrae la subcateg del filename PDF para CPF pre-2024.
    Retorna (subcat_clave, modalidad_sugerida) o ('', '')."""
    if not url:
        return ('', '')
    fname = urllib.parse.unquote(url.split('/')[-1])
    fname_u = fname.upper()

    # Mapeo de codigos conocidos -> modalidad
    KNOWN = {
        'CDE': 'Desarrollo',          # ya manejado por fname_subcode, pero por si acaso
        'CFR': 'Regiones',             # ya manejado
        'CEA': 'Estímulo Alternativo', # "Concurso de Largometraje de Ficción (Estímulo Alternativo)"
        'CFN': 'Largometraje de Ficción',
        'EEC': 'Largometraje de Ficción',  # 2021 waitlist for main line
    }

    # Buscar patron: YYYY-AAA- o YYYY AAA - 
    m = re.search(r'(?:19|20)\d{2}[\s\-_]*([A-Z]{2,5})[\s\-_]', fname_u)
    if m:
        code = m.group(1)
        if code in KNOWN:
            return (code, KNOWN[code])

    # Check for "Largo ficción" specifically (Spanish text in filename)
    if 'LARGO FICCIÓN' in fname_u or 'LARGOFICCIÓN' in fname_u or 'LARGO FICCION' in fname_u or 'LARGOFICCION' in fname_u:
        return ('LF', 'Largometraje de Ficción')

    # DAFO Lista de espera / RD-XXXX-Lista de espera
    if 'LISTA DE ESPERA' in fname_u or 'LISTADEESPERA' in fname_u:
        return ('WAIT', '')  # need monto-based inference

    return ('', '')


def infer_waitlist_subcat(url, monto, anio):
    """Para proyectos de lista de espera, inferir subcategoria por monto."""
    if anio == 2019:
        if monto >= 400000:
            return 'Largometraje de Ficción'
        elif monto >= 100000:
            return 'Estímulo Alternativo'
    if anio == 2020:
        if monto >= 400000:
            return 'Largometraje de Ficción'
        elif monto >= 20000:
            return 'Desarrollo'
    if anio == 2021:
        if monto >= 400000:
            return 'Largometraje de Ficción'
    return 'Largometraje de Ficción'


def main():
    do_run = '--run' in sys.argv
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # --- CPA 2025 ---
    print("=== CPA 2025 ===", file=sys.stderr)
    cur.execute("""
        SELECT po.id, po.monto_otorgado, ca.id
        FROM proyecto po
        JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria cv ON cv.id = ca.convocatoria_id
        WHERE lc.codigo = 'CPA' AND cv.anio = 2025 AND po.modalidad_id IS NULL
        ORDER BY po.id
    """)
    cpa_rows = cur.fetchall()
    print(f"  Encontrados: {len(cpa_rows)}", file=sys.stderr)

    cpa_assignments = []
    for po_id, monto, ca_id in cpa_rows:
        # CPA: S/50k -> Cortometrajes, S/75k+ -> Desarrollo/Preproducción/Series
        if monto is not None and monto <= 60000:
            mod = 'Cortometrajes'
        else:
            mod = 'Desarrollo, Preproducción, Desarrollo de series'
        cpa_assignments.append((po_id, ca_id, mod))

    print(f"  CPA 2025 a asignar: {len(cpa_assignments)}", file=sys.stderr)
    for pid, caid, mod in cpa_assignments:
        print(f"    ID={pid} -> \"{mod}\"", file=sys.stderr)

    # --- CPF pre-2024 ---
    print("\n=== CPF pre-2024 ===", file=sys.stderr)
    cur.execute("""
        SELECT po.id, po.monto_otorgado, r.url_pdf, ca.id, cv.anio
        FROM proyecto po
        JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria cv ON cv.id = ca.convocatoria_id
        LEFT JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
        LEFT JOIN resolucion r ON r.id = pr.resolucion_id
        WHERE lc.codigo = 'CPF'
          AND po.modalidad_id IS NULL
          AND cv.anio < 2024
        ORDER BY cv.anio, po.id
    """)
    cpf_rows = cur.fetchall()
    print(f"  Encontrados: {len(cpf_rows)}", file=sys.stderr)

    cpf_assignments = []
    for po_id, monto, url, ca_id, anio in cpf_rows:
        if url:
            code, mod = detect_cpf_subcat(url)
        else:
            code, mod = '', ''
        if not mod:
            mod = infer_waitlist_subcat(url, monto, anio) if url else ''
        if not mod:
            mod = 'Largometraje de Ficción'  # fallback
        cpf_assignments.append((po_id, ca_id, mod, anio, code or '?'))

    print(f"  CPF a asignar: {len(cpf_assignments)}", file=sys.stderr)
    for pid, caid, mod, anio, code in cpf_assignments:
        print(f"    {anio} ID={pid} [{code}] -> \"{mod}\"", file=sys.stderr)

    if not do_run:
        print("\n[DRY-RUN] Sin cambios. Usar --run para aplicar.", file=sys.stderr)
        conn.close()
        return

    # --- APPLY ---
    print("\n[RUN] Aplicando UPDATEs...", file=sys.stderr)

    # CPA 2025
    updated_cpa = 0
    for po_id, ca_id, mod_name in cpa_assignments:
        cur.execute("SELECT id FROM modalidad WHERE concurso_anual_id=? AND nombre=?",
                    (ca_id, mod_name))
        row = cur.fetchone()
        if row:
            mod_id = row[0]
        else:
            cur.execute("INSERT INTO modalidad (concurso_anual_id, nombre) VALUES (?, ?)",
                        (ca_id, mod_name))
            mod_id = cur.lastrowid
            print(f"    [NUEVA MOD] ca={ca_id}: \"{mod_name}\" id={mod_id}", file=sys.stderr)
        cur.execute("UPDATE proyecto SET modalidad_id=? WHERE id=? AND modalidad_id IS NULL",
                    (mod_id, po_id))
        if cur.rowcount:
            updated_cpa += 1

    # CPF pre-2024
    updated_cpf = 0
    for po_id, ca_id, mod_name, anio, code in cpf_assignments:
        # Use unique name: if multiple modalidades per year, disambiguate
        # Check if this mod name already used for different projects in same ca
        cur.execute("SELECT COUNT(*) FROM proyecto po "
                    "JOIN modalidad m ON m.id=po.modalidad_id "
                    "WHERE po.concurso_anual_id=? AND m.nombre=?",
                    (ca_id, mod_name))
        existing = cur.fetchone()[0]
        if existing > 0:
            # Already has this modalidad name for this ca
            pass

        cur.execute("SELECT id FROM modalidad WHERE concurso_anual_id=? AND nombre=?",
                    (ca_id, mod_name))
        row = cur.fetchone()
        if row:
            mod_id = row[0]
        else:
            cur.execute("INSERT INTO modalidad (concurso_anual_id, nombre) VALUES (?, ?)",
                        (ca_id, mod_name))
            mod_id = cur.lastrowid
            print(f"    [NUEVA MOD] ca={ca_id}: \"{mod_name}\" id={mod_id}", file=sys.stderr)
        cur.execute("UPDATE proyecto SET modalidad_id=? WHERE id=? AND modalidad_id IS NULL",
                    (mod_id, po_id))
        if cur.rowcount:
            updated_cpf += 1

    conn.commit()

    print(f"\n[RUN] CPA 2025 actualizadas: {updated_cpa}", file=sys.stderr)
    print(f"[RUN] CPF pre-2024 actualizadas: {updated_cpf}", file=sys.stderr)
    print(f"[RUN] Total: {updated_cpa + updated_cpf}", file=sys.stderr)

    conn.close()


if __name__ == '__main__':
    main()
