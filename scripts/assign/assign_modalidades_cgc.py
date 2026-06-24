#!/usr/bin/env python3
"""
Asigna modalidad_id a proyectos CGC sin modalidad (Fase 2a).

Estrategia por año:

  2019-2021: PDF con dos artículos que declaran las categorías históricas:
    - Artículo Primero: 'categoría anual'      → modalidad 'Anual'
    - Artículo Segundo: 'categoría multianual'  → modalidad 'Multianual'
    Se cuentan RUCs en cada sección para asignar proyectos en orden.

  2023: RD compuesta sin split explícito por artículo. Usa umbral por monto:
    ≤ S/70,000 → 'Promoción y difusión' (Festivales)
    > S/70,000 → 'Formación y fortalecimiento de capacidades'

  2022: Single-categoría (sin anual/multianual). Ya asignados en script
    anterior como 'Festivales, encuentros y muestras'. Se mantienen.

Uso:
  python3 assign_modalidades_cgc.py            # dry-run
  python3 assign_modalidades_cgc.py --run
"""

import subprocess, re, sys, os, sqlite3, urllib.parse, unicodedata
from dafo_common import DB_PATH, TMP_DIR

os.makedirs(TMP_DIR, exist_ok=True)

# ── Nombres de modalidades ──────────────────────────────────────────────────

MOD_ANUAL = 'Anual'
MOD_MULTIANUAL = 'Multianual'
MOD_PROMOCION = 'Festivales, encuentros y muestras'    # 'Promoción y difusión'
MOD_FORMACION = 'Fortalecimiento de capacidades'        # 'Formación y fortalecimiento de capacidades'

# Umbral para distinguir categorías CGC 2023+
UMBRAL_CGC = 70000.0

FOOTER_NOISE = [
    'copia auténtica', 'Art. 25', '070-2013-PCM', 'validadorDocumental',
    'DIRECCIÓN GENERAL', 'DESPACHO', 'PATRIMONIO CULTURAL', 'INDUSTRIAS CULTURALES',
    'Decenio', 'Año de la', 'Año del', 'batallas heroicas', 'clave:',
    'firmado digitalmente', 'San Borja',
]


def _is_footer_noise(line):
    s = line.strip()
    if not s:
        return False
    low = s.lower()
    for kw in FOOTER_NOISE:
        if kw.lower() in low:
            return True
    if re.match(r'^["\']?(?:Decenio|Año\s+del?\s+|Perú\s+Suyuna)', s, re.IGNORECASE):
        return True
    if re.match(r'^clave:\s*', s, re.IGNORECASE):
        return True
    return False


def fetch_pdf_text(url, cache_key):
    pdf_path = os.path.join(TMP_DIR, cache_key)
    txt_path = os.path.join(TMP_DIR, cache_key + "_layout.txt")
    if os.path.exists(txt_path):
        with open(txt_path, encoding='utf-8') as f:
            return f.read()
    if not os.path.exists(pdf_path):
        try:
            subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url],
                           check=True, timeout=45)
        except Exception:
            return None
    try:
        subprocess.run(['pdftotext', '-layout', pdf_path, txt_path],
                       check=True, timeout=30)
    except Exception:
        return None
    try:
        with open(txt_path, encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def get_article_text(layout_text, article_label):
    """Extrae el texto de un artículo (Primero, Segundo, etc.) desde su
    encabezado hasta el siguiente artículo o fin del documento."""
    patterns = [
        rf'{article_label}[\.\s\-—]+(.*?)(?:Artículo\s+(?:Segundo|Tercero|Cuarto)|ART[ÍI]CULO\s+(?:SEGUNDO|TERCERO|CUARTO)|Regístrese|Comuníquese)',
    ]
    for pat in patterns:
        m = re.search(pat, layout_text, re.DOTALL)
        if m:
            return m.group(1)
    return None


def count_entries_in_section(text_lines):
    """Cuenta beneficiarios en una sección de tabla, detectando líneas con
    montos (S/...) en la columna derecha.
    En formatos históricos CGC, cada beneficiario tiene exactamente una línea
    con 'S/' en la región del monto (~posición 110+)."""
    monto_re = re.compile(r'S/?\.?\s*[\d\s,]+[.,]\d{0,2}')
    count = 0
    in_table = False
    for line in text_lines:
        if _is_footer_noise(line):
            continue
        if not in_table:
            if 'Persona Jurídica' in line or 'PERSONA JURÍDICA' in line:
                in_table = True
            continue
        # Count lines with monto pattern in the right column (pos 90+)
        if len(line) > 100 and monto_re.search(line[90:]):
            count += 1
        # Stop at next article boundary or end section markers
        if re.search(r'Artículo\s+(?:Segundo|Tercero)|Regístrese|Comuníquese', line):
            break
    return count


def assign_by_monto_anual_multianual(posts_ordered):
    """Fallback: asigna por umbral de monto para separar anual de multianual.
    En CGC 2019-2021, anual ≤ S/50,000 y multianual > S/50,000."""
    assignments = []
    for po_id, monto in posts_ordered:
        mod = MOD_ANUAL if monto <= 50000 else MOD_MULTIANUAL
        assignments.append((po_id, mod))
    return assignments


def assign_by_articles(text, posts_ordered):
    """Para PDFs con Artículo Primero (anual) y Artículo Segundo (multianual):
    extrae cada sección, cuenta RUCs, asigna proyectos en orden."""
    # Extraer texto de cada artículo
    a1 = get_article_text(text, 'Artículo Primero')
    a2 = get_article_text(text, 'Artículo Segundo')
    if not a1:
        return []

    # Verificar que los artículos mencionan las categorías esperadas
    a1_tiene_anual = bool(re.search(r'categor[ií]a\s+anual', a1, re.IGNORECASE))
    a2_tiene_multianual = bool(re.search(r'categor[ií]a\s+multianual', a2, re.IGNORECASE)) if a2 else False

    if not a1_tiene_anual:
        return []  # No es formato anual/multianual

    # Contar beneficiarios en cada artículo
    a1_lines = a1.split('\n')
    n_anual = count_entries_in_section(a1_lines)

    if a2_tiene_multianual:
        a2_lines = a2.split('\n')
        n_multianual = count_entries_in_section(a2_lines)
    else:
        n_multianual = 0

    total = n_anual + n_multianual
    if total != len(posts_ordered):
        # Fallback: inferir por monto (el conteo de S/ puede fallar en
        # formatos con montos partidos en varias líneas)
        return assign_by_monto_anual_multianual(posts_ordered)

    assignments = []
    for i, (po_id, monto) in enumerate(posts_ordered):
        mod = MOD_ANUAL if i < n_anual else MOD_MULTIANUAL
        assignments.append((po_id, mod))
    return assignments


def assign_by_monto(posts_ordered):
    """Asigna por umbral de monto (para 2023+)."""
    assignments = []
    for po_id, monto in posts_ordered:
        mod = MOD_PROMOCION if monto <= UMBRAL_CGC else MOD_FORMACION
        assignments.append((po_id, mod))
    return assignments


def ensure_modalidad(conn, ca_id, nombre):
    cur = conn.cursor()
    cur.execute("SELECT id FROM modalidad WHERE concurso_anual_id=? AND nombre=?",
                (ca_id, nombre))
    row = cur.fetchone()
    if row:
        return row[0], False
    cur.execute("INSERT INTO modalidad (concurso_anual_id, nombre) VALUES (?, ?)",
                (ca_id, nombre))
    conn.commit()
    return cur.lastrowid, True


def main():
    do_run = '--run' in sys.argv
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # Proyectos CGC sin modalidad
    cur.execute("""
        SELECT po.id, po.monto_otorgado, po.concurso_anual_id, r.id, r.url_pdf,
               r.numero, c.anio
        FROM proyecto po
        JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        WHERE lc.codigo = 'CGC' AND po.modalidad_id IS NULL
          AND r.url_pdf IS NOT NULL AND r.url_pdf <> ''
        ORDER BY c.anio, po.id
    """)
    rows = cur.fetchall()

    # Agrupar por resolución
    by_res = {}
    seen_posts = set()
    for po_id, monto, ca_id, r_id, url, rd_num, anio in rows:
        if po_id in seen_posts:
            continue
        seen_posts.add(po_id)
        by_res.setdefault(r_id, {
            'url': url, 'rd_num': rd_num, 'anio': anio, 'ca_id': ca_id,
            'posts': []
        })['posts'].append((po_id, monto))

    print(f"Proyectos CGC sin modalidad: {len(seen_posts)} en {len(by_res)} resoluciones.",
          file=sys.stderr)

    assignments = []
    skipped = []

    for r_id, info in sorted(by_res.items(), key=lambda x: x[1]['anio']):
        url = info['url']
        anio = info['anio']
        rd_num = info['rd_num']
        cache_key = re.sub(r'[^a-zA-Z0-9]', '_', urllib.parse.unquote(url.split('/')[-1]))[:90]

        text = fetch_pdf_text(url, cache_key)
        if not text:
            for po_id, monto in info['posts']:
                skipped.append((r_id, anio, rd_num, 'pdf_fail'))
            continue
        text = unicodedata.normalize('NFC', text)

        # 2019-2021: Formato histórico con Artículo Primero (anual) y
        # Artículo Segundo (multianual)
        if anio in (2019, 2020, 2021):
            result = assign_by_articles(text, info['posts'])
            if result:
                for po_id, mod in result:
                    assignments.append((po_id, anio, rd_num, 'articulos', mod))
                continue
            # Fallback: si no se encontraron los artículos (ej. lista_espera),
            # usar umbral por monto
            result = assign_by_monto_anual_multianual(info['posts'])
            for po_id, mod in result:
                assignments.append((po_id, anio, rd_num, 'monto_50k', mod))
            continue

        # 2023: RD compuesta, inferencia por monto
        if anio == 2023:
            result = assign_by_monto(info['posts'])
            for po_id, mod in result:
                assignments.append((po_id, anio, rd_num, 'monto_umbral', mod))
            continue

        # Otros años (2022 ya tiene modalidad, no debería llegar aquí)
        for po_id, monto in info['posts']:
            skipped.append((r_id, anio, rd_num, f'no_manejado_{anio}'))

    # ── Reporte ──
    print("\n" + "=" * 70, file=sys.stderr)
    print(f"ASIGNACIONES PROYECTADAS: {len(assignments)}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    by_anio = {}
    for po_id, anio, rd_num, source, mod in assignments:
        by_anio.setdefault(anio, []).append((source, mod))
    for anio, lst in sorted(by_anio.items(), reverse=True):
        mods = {}
        for source, mod in lst:
            mods[(source, mod)] = mods.get((source, mod), 0) + 1
        detail = ", ".join(f"{n}×{mod}({src})" for (src, mod), n in sorted(mods.items()))
        print(f"  {anio} ({len(lst):3} posts): {detail}", file=sys.stderr)

    print(f"\nSKIPPED: {len(skipped)}", file=sys.stderr)
    skip_reasons = {}
    for r_id, anio, rd_num, reason in skipped:
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
    for reason, n in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print(f"  {n:4} {reason}", file=sys.stderr)

    if not do_run:
        print("\n[DRY-RUN] Sin cambios. Usar --run para aplicar.", file=sys.stderr)
        conn.close()
        return

    # ── Aplicar ──
    print("\n[RUN] Aplicando UPDATEs...", file=sys.stderr)
    updated = 0
    created_mods = []
    for po_id, anio, rd_num, source, canonical in assignments:
        cur.execute("SELECT concurso_anual_id FROM proyecto WHERE id=?", (po_id,))
        ca_id = cur.fetchone()[0]
        mod_id, created = ensure_modalidad(conn, ca_id, canonical)
        if created:
            created_mods.append((anio, canonical, mod_id))
        cur.execute("UPDATE proyecto SET modalidad_id=? WHERE id=? AND modalidad_id IS NULL",
                    (mod_id, po_id))
        updated += cur.rowcount
    conn.commit()
    print(f"[RUN] Proyectos actualizadas: {updated}", file=sys.stderr)
    if created_mods:
        print(f"[RUN] Modalidades creadas: {len(created_mods)}", file=sys.stderr)
        for anio, nombre, mid in created_mods:
            print(f"  {anio} '{nombre}' id={mid}", file=sys.stderr)
    conn.close()


if __name__ == '__main__':
    main()
