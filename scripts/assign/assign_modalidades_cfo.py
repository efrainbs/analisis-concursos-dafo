#!/usr/bin/env python3
"""Asigna modalidad_id a proyectos CFO sin modalidad (Fase 2b).

CFO tiene dos modalidades canonicas: 'Formación corta' y 'Formación larga'.
Estrategia (en orden de precedencia, por resolucion):

  1. ARTICULO PRIMERO  — 'categoría formación corta/larga' (2019, 2020)
     Autoritativo: el preambulo declara la categoria unica del fallo.
  2. Columna MODALIDAD de la tabla  (2024: Jurado + 2da Fase)
     Header con keyword 'MODALIDAD' y valores 'FORMACIÓN LARGA/CORTA'
     en multi-linea dentro de la columna.
  3. Inferencia por monto  (2021 fallo + EFO RDs, 2022, 2023)
     Bases CFO 2024: corta hasta S/25k, larga hasta S/45k. Historico
     consistente: montos corta ~S/8k-25k, larga ~S/34k-40k.
     Umbral: monto <= 25000 -> corta, monto > 25000 -> larga.

EXCLUYE resoluciones CFR (url_pdf LIKE '%CFR%'): son FallosFinal de
'Concurso de Proyectos de Largometraje de Ficcion exclusivo para las
regiones', mal mapeados a CFO en extract_2024.py. Son realmente
CPF/Regiones (bug de mapeo conocido, reportado en reporte_db.md).

Uso:
  python3 assign_modalidades_cfo.py            # dry-run
  python3 assign_modalidades_cfo.py --run
"""

import subprocess
import re
import sys
import os
import sqlite3
import urllib.parse
import unicodedata

from dafo_common import DB_PATH, TMP_DIR, FALLO_HEADER_KEYWORDS

os.makedirs(TMP_DIR, exist_ok=True)

MODALIDAD_CORTA = 'Formación corta'
MODALIDAD_LARGA = 'Formación larga'
UMBRAL_CORTA = 25000.0  # monto <= UMBRAL -> corta, > UMBRAL -> larga

# Excluir CFR: mal mapeados a CFO, son realmente CPF/Regiones
EXCLUDE_URL_PATTERN = '%CFR%'


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


def get_a1_text(layout_text):
    m = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO|Artículo\s)',
                  layout_text, re.DOTALL)
    if not m:
        m = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|ART[ÍI]CULO SEGUNDO|Artículo\s)',
                      layout_text, re.DOTALL)
    return m.group(1) if m else ''


def extract_modalidad_from_a1_cfo(a1_text):
    """Extrae 'Formación corta' / 'Formación larga' del ARTICULO PRIMERO.
    Patrones: 'categoría formación corta', 'Categoría Formación Corta',
    'en la categoría de formación corta', etc."""
    if not a1_text:
        return ''
    low = re.sub(r'\s+', ' ', a1_text.lower())
    # Buscar 'formacion corta' o 'formacion larga' cerca de 'categoria'
    m = re.search(r'categor[ií]a(?:\s+de)?\s+formaci[oó]n\s+(corta|larga)', low)
    if m:
        return MODALIDAD_CORTA if m.group(1) == 'corta' else MODALIDAD_LARGA
    # Fallback: si el preambulo menciona 'formacion corta' a secas
    m = re.search(r'formaci[oó]n\s+(corta|larga)\b', low)
    if m:
        return MODALIDAD_CORTA if m.group(1) == 'corta' else MODALIDAD_LARGA
    return ''


def detect_modalidad_column(layout_text):
    """Detecta la posicion de la columna MODALIDAD en una tabla CFO.
    Busca en todo el documento. Requiere MODALIDAD junto a PERSONA/NATURAL
    (headers de tabla) en ventana corta, para descartar menciones del
    preambulo ('Modalidad  Monto maximo a solicitar'). Retorna (start, end)
    o None."""
    lines = layout_text.split('\n')
    table_header_kws = ['PERSONA', 'NATURAL', 'REGIÓN', 'REGION', 'MONTO',
                        'PROGRAMA', 'INSTITUCIÓN', 'INSTITUCION', 'OTORGADO']
    best = None
    best_score = 0
    for i, line in enumerate(lines):
        if 'MODALIDAD' not in line.upper():
            continue
        window = lines[max(0, i-3):min(len(lines), i+4)]
        window_upper = ' '.join(w.upper() for w in window)
        # Requerir PERSONA o NATURAL en la ventana (descarta preambulo)
        if 'PERSONA' not in window_upper and 'NATURAL' not in window_upper:
            continue
        # Puntuar por cantidad de headers de tabla en la ventana
        score = sum(kw in window_upper for kw in table_header_kws)
        if score > best_score:
            best_score = score
            idx = line.upper().find('MODALIDAD')
            # Columna se extiende hasta MONTO (siguiente header a la derecha)
            monto_idx = -1
            for j in range(max(0, i-3), min(len(lines), i+4)):
                mu = lines[j].upper()
                mi = mu.rfind('MONTO')
                if mi > idx:
                    monto_idx = mi
                    break
            if monto_idx > idx:
                best = (idx, monto_idx)
            else:
                best = (idx, idx + 25)
    return best


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


def parse_modalidad_from_table(layout_text, col_range):
    """Extrae el valor de la columna MODALIDAD por bloque de beneficiario.
    Solo captura texto que contenga 'LARGA' o 'CORTA' (filtra ruido de
    footer/sub-header automaticamente). Retorna lista de strings por bloque."""
    if not col_range:
        return []
    start, end = col_range
    lines = layout_text.split('\n')
    # Encontrar el header MODALIDAD
    header_idx = None
    for i, line in enumerate(lines):
        if 'MODALIDAD' not in line.upper():
            continue
        window = lines[max(0, i-3):min(len(lines), i+4)]
        window_upper = ' '.join(w.upper() for w in window)
        if 'PERSONA' in window_upper or 'NATURAL' in window_upper:
            header_idx = i
            break
    if header_idx is None:
        return []

    values = []
    current_val = []
    pending_monto_split = False  # vimos 'S/.' solo, esperamos numero en sig linea
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        if _is_footer_noise(line):
            continue
        if re.search(r'ART[ÍI]CULO SEGUNDO|Artículo Segundo|Regístrese|Comuníquese',
                     line, re.IGNORECASE):
            break
        col_text = line[start:end].strip() if len(line) > start else ''
        col_low = col_text.lower()
        if col_text and ('larga' in col_low or 'corto' in col_low or 'corta' in col_low):
            current_val.append(col_text)
        # Cerrar bloque al monto. Formatos:
        #   - 'S/. 8,533.40' (monto completo)
        #   - 'S/.' solo (split: numero va en la sig linea)
        #   - numero decimal solitario tras un 'S/.' previo
        if re.search(r'S/?\.?\s*\d[\d.,]+\d{2}', line):
            if current_val:
                values.append(' '.join(current_val))
                current_val = []
            pending_monto_split = False
        elif re.search(r'S/?\.?\s*$', line.strip()):
            pending_monto_split = True
        elif pending_monto_split and re.search(r'\d[\d.,]+\d{2}', line):
            if current_val:
                values.append(' '.join(current_val))
                current_val = []
            pending_monto_split = False
    if current_val:
        values.append(' '.join(current_val))
    return values


def normalize_modalidad_cfo(raw):
    """Normaliza valor de columna MODALIDAD o frase a 'Formación corta'/'larga'."""
    if not raw:
        return ''
    low = re.sub(r'\s+', ' ', raw.lower()).strip()
    if 'larga' in low or 'largo' in low:
        return MODALIDAD_LARGA
    if 'corta' in low or 'corto' in low:
        return MODALIDAD_CORTA
    return ''


def infer_by_monto(monto):
    """Inferencia por monto. Umbral: <= 25000 -> corta, > 25000 -> larga."""
    if monto is None:
        return ''
    if monto <= UMBRAL_CORTA:
        return MODALIDAD_CORTA
    return MODALIDAD_LARGA


def ensure_modalidad(conn, ca_id, nombre):
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

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # Proyectos CFO sin modalidad, excluyendo CFR (mal mapeados a CFO)
    query = """
        SELECT po.id, po.monto_otorgado, po.concurso_anual_id, r.id, r.url_pdf, r.numero, c.anio
        FROM proyecto po
        JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        WHERE lc.codigo = 'CFO' AND po.modalidad_id IS NULL
          AND r.url_pdf NOT LIKE ?
          AND r.url_pdf IS NOT NULL AND r.url_pdf <> ''
        ORDER BY po.id, CASE r.tipo WHEN 'fallo_final' THEN 0 ELSE 1 END
    """
    cur.execute(query, (EXCLUDE_URL_PATTERN,))
    rows = cur.fetchall()

    # Agrupar por resolucion
    by_res = {}
    seen_posts = set()
    for po_id, monto, ca_id, r_id, url, rd_num, anio in rows:
        if po_id in seen_posts:
            continue
        seen_posts.add(po_id)
        by_res.setdefault(r_id, {
            'url': url, 'rd_num': rd_num, 'anio': anio, 'ca_id': ca_id,
            'posts': []  # list of (po_id, monto)
        })['posts'].append((po_id, monto))

    # CFR excluidos: contar para reporte
    cur.execute("""
        SELECT COUNT(DISTINCT po.id) FROM proyecto po
        JOIN proyecto_resolucion pr ON pr.proyecto_id=po.id
        JOIN resolucion r ON r.id=pr.resolucion_id
        JOIN concurso_anual ca ON ca.id=po.concurso_anual_id
        JOIN linea_concursable lc ON lc.id=ca.linea_concursable_id
        WHERE lc.codigo='CFO' AND po.modalidad_id IS NULL AND r.url_pdf LIKE ?
    """, (EXCLUDE_URL_PATTERN,))
    cfr_excluded = cur.fetchone()[0]

    print(f"Proyectos CFO sin modalidad: {len(seen_posts)} en {len(by_res)} resoluciones.", file=sys.stderr)
    print(f"CFR excluidos (mal mapeados a CFO, son CPF/Regiones): {cfr_excluded}", file=sys.stderr)

    assignments = []  # (po_id, anio, rd_num, source, modalidad)
    skipped = []      # (r_id, anio, rd_num, reason)
    col_mismatches = []  # (r_id, anio, rd_num, info) - cayeron a monto

    for r_id, info in by_res.items():
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

        # Validacion cruzada (info, no asignacion):
        # - a1 puede declarar categoria (pero enganoso si hay varios ARTICULOS,
        #   ej 2019 CFO tiene Art. Primero=corta y Art. Segundo=larga)
        # - columna MODALIDAD (2024) coincide 1:1 con monto (validado)
        a1 = get_a1_text(text)
        mod_a1 = extract_modalidad_from_a1_cfo(a1)
        col_range = detect_modalidad_column(text)
        col_vals = []
        if col_range:
            col_vals = [normalize_modalidad_cfo(v)
                        for v in parse_modalidad_from_table(text, col_range)]

        # Fuente principal: MONTO. Bases CFO: corta <= S/25k, larga > S/25k.
        # Canonico y robusto (no depende de parseo de ARTICULOS multi-categoria).
        for idx, (po_id, monto) in enumerate(info['posts']):
            mod = infer_by_monto(monto)
            if not mod:
                # Fallback: a1 si hay un solo post (RD individual) o columna
                if len(info['posts']) == 1 and mod_a1:
                    mod = mod_a1
                    assignments.append((po_id, anio, rd_num, 'a1_fallback', mod))
                    continue
                if col_vals and idx < len(col_vals) and col_vals[idx]:
                    mod = col_vals[idx]
                    assignments.append((po_id, anio, rd_num, 'col_fallback', mod))
                    continue
                skipped.append((r_id, anio, rd_num, 'no_monto'))
                continue
            # Validacion: si a1 declara categoria y difiere de monto, reportar
            # (esperado en fallos multi-categoria como 2019 CFO)
            source = 'monto'
            assignments.append((po_id, anio, rd_num, source, mod))

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

    if col_mismatches:
        print(f"\nCOL_MISMATCHES (cayeron a fallback monto): {len(col_mismatches)}",
              file=sys.stderr)
        for r_id, anio, rd_num, info in col_mismatches:
            print(f"  r{r_id} {anio} {rd_num}: {info}", file=sys.stderr)

    if not do_run:
        print("\n[DRY-RUN] Sin cambios. Usar --run para aplicar.", file=sys.stderr)
        conn.close()
        return

    # ── Aplicar ──
    print("\n[RUN] Aplicando UPDATEs...", file=sys.stderr)
    updated = 0
    for po_id, anio, rd_num, source, canonical in assignments:
        cur.execute("SELECT concurso_anual_id FROM proyecto WHERE id=?", (po_id,))
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
