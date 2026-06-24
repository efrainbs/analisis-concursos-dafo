#!/usr/bin/env python3
"""Asigna modalidad_id a proyectos SIN modalidad, de forma NO destructiva.

Para cada proyecto sin modalidad, agrupada por su resolucion (un PDF ->
muchas proyectos), deriva la modalidad de:

  1. ARTICULO PRIMERO del PDF  (regex  modalidad de 'X'  /  categoria 'X')
     - Autoritativo: si el preambulo declara una unica modalidad, todas las
       proyectos de esa RD pertenecen a esa modalidad.
  2. Sub-codigo del nombre del archivo  (fallback, solo codigos no ambiguos)
     - Ej: 2025-CPF-D-FalloFinal.pdf -> CPF, sub 'D' -> 'Desarrollo'

Solo asigna cuando hay confianza (RD de modalidad unica). Los fallos
consolidados multi-modalidad (sin modalidad declarada en el preambulo ni
sub-codigo univoco) se DEJAN sin asignar para una fase posterior de parseo
de encabezados de seccion.

Uso:
  python3 assign_modalidades.py            # dry-run (reporte, sin escribir)
  python3 assign_modalidades.py --run      # aplica UPDATEs
  python3 assign_modalidades.py --year 2025
  python3 assign_modalidades.py --linea CPF
"""

import subprocess
import re
import sys
import os
import sqlite3
import urllib.parse
import unicodedata

from dafo_common import DB_PATH, TMP_DIR, get_modalidad_id

os.makedirs(TMP_DIR, exist_ok=True)

# ── Sub-codigos de filename NO ambiguos -> nombre canonico de modalidad ──
# (Solo codigos que mapean a una unica modalidad. Los combos como 'P-NR'
#  o 'P-PP-DS-D' son multi-modalidad y se excluyen del fallback.)
SUBCODE_MODALIDAD = {
    'CPF': {
        'D': 'Desarrollo',
        'R': 'Regiones',
        'NR': 'Nuevos realizadores',
        'NUEVOSREALIZADORES': 'Nuevos realizadores',
        'N': 'Nuevos realizadores',
        'TL': 'Tercer largometraje a más',
        'N-3ERO': 'Tercer largometraje a más',
        '3ERO': 'Tercer largometraje a más',
        # 2025: P-NR = modalidad Produccion, categoria Nuevos realizadores
        # DB trata 'Nuevos realizadores' como modalidad (convencion 2024/lista_espera)
        'P-NR': 'Nuevos realizadores',
        # 2025: P-R = Produccion exclusivo para Regiones
        'P-R': 'Regiones',
    },
    'CDO': {
        'D': 'Desarrollo',
        'P': 'Producción',
    },
    'CPC': {
        'OP': 'Ópera prima',
        'OPERAPRIMA': 'Ópera prima',
        '2DA': 'Segunda obra a más',
        '2DAOBRA': 'Segunda obra a más',
    },
    'CPA': {
        'C': 'Cortometrajes',
    },
    'CGC': {
        'FC': 'Fortalecimiento de capacidades',
        'FEM': 'Festivales, encuentros y muestras',
    },
    'CDV': {
        'PRE': 'Preproducción',
        'PROD': 'Producción',
    },
}

# ── Normalizacion: frase extraida del preambulo -> nombre canonico ──
# Se matchea por keyword (lowercase) contenido en la frase extraida.
CANONICAL_KEYS = [
    ('tercer largometraje', 'Tercer largometraje a más'),
    ('tercer largo', 'Tercer largometraje a más'),
    ('3er largometraje', 'Tercer largometraje a más'),
    ('nuevos realizadores', 'Nuevos realizadores'),
    ('nuevo realizador', 'Nuevos realizadores'),
    ('opera prima', 'Ópera prima'),
    ('ópera prima', 'Ópera prima'),
    ('segunda obra', 'Segunda obra a más'),
    ('2da obra', 'Segunda obra a más'),
    ('cortometraje', 'Cortometrajes'),
    ('regiones', 'Regiones'),
    ('region', 'Regiones'),
    ('desarrollo', 'Desarrollo'),
    ('preproduccion', 'Preproducción'),
    ('preproducción', 'Preproducción'),
    ('produccion', 'Producción'),
    ('producción', 'Producción'),
    ('festivales', 'Festivales, encuentros y muestras'),
    ('festivales, encuentros', 'Festivales, encuentros y muestras'),
    ('encuentros y muestras', 'Festivales, encuentros y muestras'),
    ('fortalecimiento de capacidades', 'Fortalecimiento de capacidades'),
    ('desarrollo de series', 'Desarrollo de series'),
]


def normalize_modalidad(raw):
    """Normaliza una frase de modalidad extraida del PDF a nombre canonico.
    Retorna '' si no se reconoce (para no crear variantes duplicadas)."""
    if not raw:
        return ''
    s = raw.strip().strip('"\'""''«»').strip()
    low = re.sub(r'\s+', ' ', s.lower()).strip()
    # Match exacto preferente
    for key, canon in CANONICAL_KEYS:
        if key == low:
            return canon
    # Match por keyword contenido (orden: mas especifico primero)
    for key, canon in CANONICAL_KEYS:
        if key in low:
            return canon
    return ''  # no reconocido -> no asignar (evita variantes)


def extract_modalidad_from_a1(a1_text):
    """Extrae la modalidad declarada en ARTICULO PRIMERO.
    Retorna la frase cruda (sin normalizar) o ''."""
    # Comillas rectas y curvas (los PDFs del MINCULTUR usan ' ' frecuentemente)
    q = r"['\u2018\u2019\u00ab\u00bb\u201c\u201d]"
    patterns = [
        r"modalidad\s+de\s+" + q + r"([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)" + q,
        r"categor[ií]a\s+de\s+" + q + r"([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)" + q,
        r"categor[ií]a\s+" + q + r"([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)" + q,
    ]
    for pat in patterns:
        m = re.search(pat, a1_text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            if len(raw) >= 4 and not re.fullmatch(r'[^\w]+', raw):
                return raw
    return ''


def get_a1_text(layout_text):
    """Extrae el texto de ARTICULO PRIMERO."""
    m = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO|Artículo\s)',
                  layout_text, re.DOTALL)
    if not m:
        m = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|ART[ÍI]CULO SEGUNDO|Artículo\s)',
                      layout_text, re.DOTALL)
    if not m:
        return ''
    return m.group(1)


def fetch_pdf_text(url, cache_key):
    """Descarga el PDF y devuelve el texto layout. Cachea por cache_key."""
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


# Sub-codigos historicos: el filename usa el sub-codigo como codigo principal
# (ej: 2022-CDE-FalloFinal.pdf). Mapean a (linea, modalidad).
# Solo se incluyen casos NO ambiguos y consistentes a una unica modalidad.
HISTORICAL_SUBCODE = {
    # CDE = Concurso de Desarrollo de largometraje de ficcion -> CPF Desarrollo
    'CDE': ('CPF', 'Desarrollo'),
    # CFN: requiere inspeccion del filename (Nuevos realizadores vs Tercer largo).
    # Si el filename no aclara, es consolidado -> se maneja abajo, no aqui.
}


def fname_subcode(url, linea_code):
    """Extrae la modalidad del filename. Solo casos NO ambiguos.
    Retorna nombre canonico o ''.

    Dos estilos:
      Moderno:  YYYY-LINEA-SUB-FalloFinal.pdf  (LINEA=CPF, SUB=D/NR/TL/...)
      Historico: YYYY-SUBCODE-FalloFinal.pdf    (SUBCODE=CDE/CFN, mapea a linea)
    """
    fname = urllib.parse.unquote(url.split('/')[-1])
    f = fname.upper().replace(' ', '')
    linea_u = linea_code.upper()

    # --- Estilo moderno: LINEA- aparece en el filename ---
    prefix = linea_u + '-'
    if prefix in f:
        rest = f.split(prefix, 1)[1]
        for sep in ['-FALLO', '-RD', '-BENEFICIARIO', '-JURADO', '.PDF', '_FALLO']:
            if sep in rest:
                rest = rest.split(sep, 1)[0]
                break
        sub = rest.strip('-').strip()
        if sub:
            mapping = SUBCODE_MODALIDAD.get(linea_u, {})
            if sub in mapping:
                return mapping[sub]
            if '-' in sub:
                return ''  # combo no listado -> ambiguo
            sub_nohyphen = sub.replace('-', '')
            if sub_nohyphen in mapping:
                return mapping[sub_nohyphen]

    # --- Estilo historico: el codigo principal es un sub-codigo ---
    # Extraer el token despues de YYYY-
    m = re.match(r'(?:19|20)\d{2}[-_]?([A-Z]{2,5})[-_]', f)
    if m:
        code = m.group(1)
        # CFN: depende del resto del filename
        if code == 'CFN' and linea_u == 'CPF':
            if re.search(r'TERCER|3ERO|3ER', f):
                return 'Tercer largometraje a más'
            if re.search(r'NUEVOS|NUEVOSREALIZADORES|\bNR\b', f):
                return 'Nuevos realizadores'
            return ''  # CFN sin aclarar -> consolidado, skip
        # CFR 2023+: "Concurso de Proyectos de Largometraje de Ficcion exclusivo
        # para las regiones" -> CPF Regiones. (En 2020-2022 se mapeo a CFO; ahi
        # linea != CPF y este branch no aplica.)
        if code == 'CFR' and linea_u == 'CPF':
            return 'Regiones'
        if code in HISTORICAL_SUBCODE:
            hist_linea, hist_mod = HISTORICAL_SUBCODE[code]
            if hist_linea == linea_u:
                return hist_mod
    return ''


def ensure_modalidad(conn, ca_id, nombre):
    """INSERT OR IGNORE una modalidad y retorna su id."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM modalidad WHERE concurso_anual_id=? AND nombre=?",
                (ca_id, nombre))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("INSERT INTO modalidad (concurso_anual_id, nombre) VALUES (?, ?)",
                (ca_id, nombre))
    conn.commit()
    return cur.lastrowid


def main():
    do_run = '--run' in sys.argv
    year_filter = None
    linea_filter = None
    for a in sys.argv[1:]:
        if a.startswith('--year='):
            year_filter = a.split('=', 1)[1]
        elif a == '--year' and sys.argv.index(a) + 1 < len(sys.argv):
            year_filter = sys.argv[sys.argv.index(a) + 1]
        elif a.startswith('--linea='):
            linea_filter = a.split('=', 1)[1]
        elif a == '--linea' and sys.argv.index(a) + 1 < len(sys.argv):
            linea_filter = sys.argv[sys.argv.index(a) + 1]

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # Proyectos sin modalidad, agrupadas por resolucion.
    # Preferir resolucion de tipo fallo_final / lista_espera sobre acta.
    query = """
        SELECT po.id, po.concurso_anual_id, r.id, r.url_pdf, r.numero,
               lc.codigo, cv.anio
        FROM proyecto po
        JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria cv ON cv.id = ca.convocatoria_id
        WHERE po.modalidad_id IS NULL
          AND r.url_pdf IS NOT NULL AND r.url_pdf <> ''
    """
    params = []
    if year_filter:
        query += " AND cv.anio = ?"
        params.append(int(year_filter))
    if linea_filter:
        query += " AND lc.codigo = ?"
        params.append(linea_filter)
    # Ordenar para preferir fallo_final primero dentro de cada proyecto
    query += " ORDER BY po.id, CASE r.tipo WHEN 'fallo_final' THEN 0 WHEN 'lista_espera' THEN 1 ELSE 2 END"
    cur.execute(query, params)
    rows = cur.fetchall()

    # Agrupar proyectos por resolucion_id (una descarga de PDF sirve para muchas)
    by_res = {}
    seen_posts = set()
    for po_id, ca_id, r_id, url, rd_num, linea, anio in rows:
        if po_id in seen_posts:
            continue  # ya tenemos una resolucion para esta proyecto
        seen_posts.add(po_id)
        by_res.setdefault(r_id, {
            'url': url, 'rd_num': rd_num, 'linea': linea, 'anio': anio,
            'ca_id': ca_id, 'posts': []
        })['posts'].append(po_id)

    print(f"Proyectos sin modalidad: {len(seen_posts)} en {len(by_res)} resoluciones.",
          file=sys.stderr)

    assignments = []   # (po_id, linea, anio, rd_num, source, modalidad)
    skipped = []       # (r_id, linea, anio, rd_num, reason)
    errors = []        # (r_id, reason)

    for r_id, info in by_res.items():
        url = info['url']
        linea = info['linea']
        anio = info['anio']
        rd_num = info['rd_num']
        cache_key = re.sub(r'[^a-zA-Z0-9]', '_', urllib.parse.unquote(url.split('/')[-1]))[:90]

        text = fetch_pdf_text(url, cache_key)
        if not text:
            errors.append((r_id, f"download/parse fail: {url}"))
            for po_id in info['posts']:
                skipped.append((r_id, linea, anio, rd_num, 'pdf_fail'))
            continue
        text = unicodedata.normalize('NFC', text)

        # 1) FILENAME primero: codifica la taxonomia canonica del proyecto
        #    (categoria: Nuevos realizadores / Tercer largometraje / Regiones).
        canonical = fname_subcode(url, linea)
        source = 'filename'
        modalidad_raw = canonical

        # 2) a1 como fallback si el filename no resolvio
        if not canonical:
            a1 = get_a1_text(text)
            modalidad_raw = extract_modalidad_from_a1(a1) if a1 else ''
            if modalidad_raw:
                source = 'a1'
                canonical = normalize_modalidad(modalidad_raw)

        if not canonical:
            reason = f'unrecognized:{modalidad_raw[:30]}' if modalidad_raw else 'no_modalidad'
            for po_id in info['posts']:
                skipped.append((r_id, linea, anio, rd_num, reason))
            continue

        for po_id in info['posts']:
            assignments.append((po_id, linea, anio, rd_num, source, canonical))

    # ── Reporte ──
    print("\n" + "=" * 70, file=sys.stderr)
    print(f"ASIGNACIONES PROYECTADAS: {len(assignments)}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    by_linea = {}
    for po_id, linea, anio, rd_num, source, mod in assignments:
        by_linea.setdefault((anio, linea), []).append((source, mod))
    for (anio, linea), lst in sorted(by_linea.items(), reverse=True):
        mods = {}
        for source, mod in lst:
            mods[(source, mod)] = mods.get((source, mod), 0) + 1
        detail = ", ".join(f"{n}×{mod}({src})" for (src, mod), n in sorted(mods.items()))
        print(f"  {anio} {linea:4} ({len(lst):3} posts): {detail}", file=sys.stderr)

    print(f"\nSKIPPED (sin asignar): {len(skipped)}", file=sys.stderr)
    skip_reasons = {}
    for r_id, linea, anio, rd_num, reason in skipped:
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
    for reason, n in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print(f"  {n:4} {reason}", file=sys.stderr)

    if errors:
        print(f"\nERRORES: {len(errors)}", file=sys.stderr)
        for r_id, reason in errors[:10]:
            print(f"  r{id}: {reason[:80]}", file=sys.stderr)

    if not do_run:
        print("\n[DRY-RUN] Sin cambios. Usar --run para aplicar.", file=sys.stderr)
        conn.close()
        return

    # ── Aplicar ──
    print("\n[RUN] Aplicando UPDATEs...", file=sys.stderr)
    updated = 0
    for po_id, linea, anio, rd_num, source, canonical in assignments:
        # ca_id por proyecto (puede diferir si la resolucion agrupa varias lineas,
        # pero en DAFO una RD pertenece a un unico concurso_anual)
        cur.execute("""SELECT po.concurso_anual_id FROM proyecto po WHERE po.id=?""", (po_id,))
        ca_id = cur.fetchone()[0]
        mod_id = ensure_modalidad(conn, ca_id, canonical)
        cur.execute("UPDATE proyecto SET modalidad_id=? WHERE id=? AND modalidad_id IS NULL",
                    (mod_id, po_id))
        updated += cur.rowcount
    conn.commit()
    print(f"[RUN] Proyectos actualizadas: {updated}", file=sys.stderr)
    conn.close()


if __name__ == '__main__':
    main()
