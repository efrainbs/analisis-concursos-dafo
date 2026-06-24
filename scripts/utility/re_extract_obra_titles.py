#!/usr/bin/env python3
"""
Re-extract garbled obra titles from original PDF fallo final resolutions.

Strategy:
1. For each problematic obra, identify the (year, linea) and beneficiary
2. Download the fallo final PDF(s) for that year/linea
3. Parse layout text to find the matching beneficiary + obra title
4. Update obra.titulo where current is garbled

Usage:
  python3 re_extract_obra_titles.py            # dry-run (show what would change)
  python3 re_extract_obra_titles.py --run      # apply updates
  python3 re_extract_obra_titles.py --download-only  # just download PDFs
"""
import sqlite3, sys, os, re, json, subprocess, unicodedata, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH, TMP_DIR, FALLO_HEADER_KEYWORDS, REGION_NAMES_UPPER

RUN = "--run" in sys.argv
DOWNLOAD_ONLY = "--download-only" in sys.argv
os.makedirs(TMP_DIR, exist_ok=True)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dafo_pdfs_map.json")) as f:
    PDF_MAP = json.load(f)

SHORT_WORDS = {'A','E','Y','O','LA','EL','LO','AL','DEL','EN','UN','SU',
               'DE','SE','NO','MI','TU','SUS','LOS','LAS','CON','POR',
               'QUE','FUE','ES','YA','HA','HI','VA','VE','DA','LE','ME',
               'TE','SI','NI','3D','2D','II','IV','VI','V','X','8M','S/.'}

def is_garbled(t):
    t = t.strip()
    if len(t) < 5: return True
    if re.search(r'S/[\s\d,]+', t): return True
    if re.search(r'(DNI|RUC)\s*N?°?\s*\d', t): return True
    if re.search(r'  {2,}', t): return True
    words = re.split(r'[\s,]+', t)
    short_bad = [w for w in words if len(w) <= 2 and w.upper() not in SHORT_WORDS]
    if len(words) >= 3 and len(short_bad) / len(words) > 0.5: return True
    return False

# ── PDF helpers ─────────────────────────────────────────────────────────────

def download_pdf(url, pdf_path):
    if os.path.exists(pdf_path):
        return True
    try:
        subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, url], check=True, timeout=45)
        return True
    except Exception as e:
        print(f"  Download error: {e}", file=sys.stderr)
        return False

def get_layout_text(pdf_path):
    txt_path = pdf_path + "_layout.txt"
    if not os.path.exists(txt_path):
        try:
            subprocess.run(['pdftotext', '-layout', pdf_path, txt_path], check=True, timeout=30)
        except Exception as e:
            return None, str(e)
    with open(txt_path) as f:
        text = f.read()
    text = unicodedata.normalize('NFC', text)
    return text, None

def detect_table_columns(layout_lines, extra_keywords=None):
    keywords = list(FALLO_HEADER_KEYWORDS)
    if extra_keywords:
        keywords.extend(extra_keywords)

    header_line_set = set()
    for i, line in enumerate(layout_lines[:30]):
        count = 0
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', line):
                count += 1
        if count >= 2:
            header_line_set.add(i)

    if header_line_set:
        min_h = min(header_line_set)
        max_h = max(header_line_set)
        for i in range(max(0, min_h - 1), min(len(layout_lines[:30]), max_h + 2)):
            count = 0
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', layout_lines[i]):
                    count += 1
            if count >= 1:
                header_line_set.add(i)

    if not header_line_set:
        for i in range(min(30, len(layout_lines))):
            header_line_set.add(i)

    headers_found = {}
    for i, line in enumerate(layout_lines[:30]):
        if i not in header_line_set:
            continue
        for kw in keywords:
            m = re.search(r'\b' + re.escape(kw) + r'\b', line)
            if m:
                idx = m.start()
                if kw not in headers_found or idx < headers_found[kw]:
                    headers_found[kw] = idx

    sorted_kws = sorted(headers_found.items(), key=lambda x: x[1])
    col_defs = []

    c1_end = None
    for kw, pos in sorted_kws:
        if kw not in ('PERSONA', 'JURÍDICA', '(RUC)', 'NATURAL'):
            c1_end = pos
            break
    col_defs.append(('empresa', 0, c1_end or 40))

    has_titulo = 'TÍTULO' in headers_found or 'TITULO' in headers_found
    has_proyecto = 'PROYECTO' in headers_found
    has_categoria = 'CATEGORÍA' in headers_found
    region_pos = headers_found.get('REGIÓN', 40) if 'REGIÓN' in headers_found else headers_found.get('REGION', 40)

    director_pos = None
    for k in ('RESPONSABLE', 'DIRECTOR'):
        if k in headers_found:
            director_pos = headers_found[k]
            break
    if director_pos is None:
        director_pos = 90

    categoria_pos = headers_found.get('CATEGORÍA', None)
    evento_pos = headers_found.get('EVENTO', None)
    obra_pos = headers_found.get('OBRA', None)
    institucion_pos = headers_found.get('INSTITUCIÓN', None) or headers_found.get('INSTITUCION', None)
    programa_pos = headers_found.get('PROGRAMA', None)
    monto_pos = None
    for mk in ('MONTO', 'OTORGADO', 'PREMIO'):
        if mk in headers_found:
            monto_pos = headers_found[mk]
            break
    if monto_pos is None:
        monto_pos = director_pos + 10

    def end_before(ref_pos, margin=2):
        if ref_pos:
            return max(region_pos + 10, ref_pos - margin)
        return ref_pos

    if institucion_pos and programa_pos:
        col_defs.append(('region', region_pos, institucion_pos))
        col_defs.append(('institucion', institucion_pos, programa_pos))
        col_defs.append(('programa', programa_pos, director_pos))
    elif evento_pos:
        evento_end = director_pos
        for ek in ('MONTO', 'OTORGADO'):
            if ek in headers_found:
                evento_end = max(evento_pos + 10, headers_found[ek] - 2)
                break
        if obra_pos:
            col_defs.append(('region', region_pos, obra_pos))
            col_defs.append(('proyecto', obra_pos, evento_pos))
            col_defs.append(('evento', evento_pos, evento_end))
        else:
            col_defs.append(('region', region_pos, evento_pos))
            col_defs.append(('evento', evento_pos, evento_end))
    elif has_titulo:
        titulo_pos = headers_found['TÍTULO' if 'TÍTULO' in headers_found else 'TITULO']
        p_start = max(0, titulo_pos - 2)
        p_end = end_before(categoria_pos or director_pos)
        d_start = end_before(director_pos, 2)
        col_defs.append(('region', region_pos, p_start))
        col_defs.append(('proyecto', p_start, p_end))
        col_defs.append(('director', d_start, d_start + 22))
    elif has_proyecto and has_categoria:
        p_start = region_pos + 13
        p_end = end_before(categoria_pos)
        d_start = end_before(director_pos, 4)
        c_start = max(p_end, categoria_pos - 2)
        c_end = d_start - 2 if d_start and d_start > c_start else c_start + 15
        col_defs.append(('region', region_pos, p_start))
        col_defs.append(('proyecto', p_start, p_end))
        col_defs.append(('categoria', c_start, c_end))
        col_defs.append(('director', d_start, d_start + 22))
    elif has_proyecto:
        p_start = region_pos + 15
        p_end = end_before(director_pos or categoria_pos or monto_pos)
        d_start = p_end + 2
        col_defs.append(('region', region_pos, p_start))
        col_defs.append(('proyecto', p_start, p_end))
        col_defs.append(('director', d_start, d_start + 22))
    else:
        col_defs.append(('region', region_pos, region_pos + 20))
        col_defs.append(('proyecto', region_pos + 20, director_pos - 2))
        col_defs.append(('director', director_pos, director_pos + 22))

    # Add monto column
    monto_col_start = None
    for mk in ('MONTO', 'OTORGADO', 'PREMIO'):
        if mk in headers_found:
            monto_col_start = headers_found[mk]
            break
    if monto_col_start is None:
        monto_col_start = max(director_pos + 5, 110)
    monto_col_end = monto_col_start + 25
    col_defs.append(('monto', monto_col_start, monto_col_end))

    return col_defs

def extract_fallo_beneficiaries(layout_text):
    """Simplified fallo beneficiary extraction — just returns list of rows with
    empresa, proyecto, monto text snippets for matching."""
    a1_match = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO|Artículo\s)', layout_text, re.DOTALL)
    if not a1_match:
        a1_match = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|ART[ÍI]CULO SEGUNDO|Artículo\s|ART[ÍI]CULO\s)', layout_text, re.DOTALL)
    if not a1_match:
        return None, "No ARTÍCULO PRIMERO found"

    a1 = a1_match.group(1)
    lines = a1.split('\n')

    col_defs = detect_table_columns(lines)

    # Build column name -> (start, end) map
    col_map = {}
    for cname, cstart, cend in col_defs:
        col_map[cname] = (cstart, cend)

    emp_start, emp_end = col_map.get('empresa', (0, 40))
    proj_start, proj_end = col_map.get('proyecto', (40, 80))
    monto_start, monto_end = col_map.get('monto', (110, 135))

    # Find data start line
    header_passed = False
    data_start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if any(kw in line for kw in FALLO_HEADER_KEYWORDS):
            header_passed = True
            continue
        if not header_passed:
            continue
        if any(kw in stripped for kw in ['DECLARAR', 'Declárese', 'Declarar', 'Consígnese',
                                           'Art.', 'copia auténtica', 'DESPACHO']):
            continue
        if len(line[:20].strip()) < 3:
            continue
        data_start = i
        break

    if data_start is None:
        return None, "No data start found"

    # Parse rows
    rows = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        if any(kw in stripped for kw in ['ARTÍCULO SEGUNDO', 'ARTICULO SEGUNDO',
                                           'Artículo Segundo', 'Regístrese', 'Comuníquese']):
            break

        empresa = line[emp_start:emp_end].strip() if len(line) > emp_start else ''
        proyecto = line[proj_start:proj_end].strip() if len(line) > proj_start else ''
        monto_text = line[monto_start:monto_end].strip() if len(line) > monto_start else ''

        monto = None
        m = re.search(r'S/?\.?\s*([\d\s,]+[.,]\d{2})', monto_text)
        if m:
            try:
                monto = float(m.group(1).replace(' ', '').replace(',', '.'))
            except ValueError:
                pass

        rows.append({
            'empresa': empresa,
            'proyecto': proyecto,
            'monto_text': monto_text,
            'monto': monto,
            'raw': line,
        })

    return rows, None


# ── Main logic ──────────────────────────────────────────────────────────────

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Get all obras with garbled titles + beneficiary info
    c.execute("""
      SELECT o.id, o.titulo, lc.codigo, c.anio,
             p.monto_otorgado,
             CASE WHEN per.tipo='natural' THEN per.nombres || ' ' || per.apellidos
                  ELSE per.razon_social END AS persona_nombre,
             per.tipo AS persona_tipo,
             COALESCE(per.dni, per.ruc) AS persona_doc
      FROM obra o
      JOIN proyecto p ON p.obra_id = o.id
      JOIN concurso_anual ca ON ca.id = p.concurso_anual_id
      JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
      JOIN convocatoria c ON c.id = ca.convocatoria_id
      JOIN persona per ON per.id = p.persona_beneficiaria_id
      ORDER BY o.id
    """)
    all_rows = c.fetchall()

    problematic = [r for r in all_rows if is_garbled(r[1])]
    print(f"Total problematic obras: {len(problematic)}")

    # Group by (anio, codigo)
    from collections import defaultdict
    grouped = defaultdict(list)
    for r in problematic:
        oid, titulo, codigo, anio, monto, pnombre, ptipo, pdoc = r
        grouped[(anio, codigo)].append(r)

    # For each group, find and process the fallo final PDF
    fixes = []
    for (anio, codigo), obras in sorted(grouped.items()):
        year_str = str(anio)
        if year_str not in PDF_MAP or codigo not in PDF_MAP[year_str]:
            print(f"\n⚠ No PDF map entry for {anio} {codigo}")
            continue

        # Find fallo_final PDFs
        fallos = [p for p in PDF_MAP[year_str][codigo].get('pdfs', [])
                  if p.get('category') == 'fallo_final']

        if not fallos:
            print(f"\n⚠ No fallo_final PDF for {anio} {codigo} — {len(obras)} obras unfixed")
            continue

        print(f"\n{'='*60}")
        print(f"{anio} {codigo}: {len(obras)} problematic obras, {len(fallos)} fallo PDF(s)")
        print(f"{'='*60}")

        for pdf_info in fallos:
            url = pdf_info['url']
            fname = urllib.parse.unquote(url.split('/')[-1])
            pdf_path = os.path.join(TMP_DIR, f"re_extract_{fname}")

            print(f"\n  PDF: {fname}")

            if not download_pdf(url, pdf_path):
                print(f"    ⚠ Download failed, skipping")
                continue

            if DOWNLOAD_ONLY:
                print(f"    ✓ Downloaded")
                continue

            layout_text, err = get_layout_text(pdf_path)
            if err:
                print(f"    ⚠ Text extraction error: {err}")
                continue

            rows, err = extract_fallo_beneficiaries(layout_text)
            if err:
                print(f"    ⚠ Parse error: {err}")
                continue

            if not rows:
                print(f"    ⚠ No data rows found")
                continue

            print(f"    ✓ {len(rows)} data rows extracted")

            # Try to match each problematic obra
            for obra in obras:
                oid, titulo_actual, codigo, anio, monto, pnombre, ptipo, pdoc = obra

                # Try to find matching row
                best_match = None
                best_score = 0

                for row in rows:
                    emp = row['empresa'].upper()
                    # Skip header-like rows
                    if any(kw in emp for kw in FALLO_HEADER_KEYWORDS):
                        continue
                    if len(emp) < 3:
                        continue

                    pnombre_upper = pnombre.upper().strip() if pnombre else ''
                    score = 0

                    # Check if persona name appears in empresa text
                    if pnombre_upper:
                        # Try exact match
                        if pnombre_upper == emp:
                            score = 100
                        # Try contains
                        elif pnombre_upper in emp:
                            score = 80
                        elif emp in pnombre_upper:
                            score = 70
                        # Try first words
                        else:
                            p_words = pnombre_upper.split()
                            e_words = emp.split()
                            common = set(p_words) & set(e_words)
                            if common:
                                # Filter out very common words
                                meaningful = [w for w in common if len(w) > 3]
                                if meaningful:
                                    score = 50 + len(meaningful) * 10

                    # Boost score if monto matches
                    if monto and row['monto']:
                        if abs(monto - row['monto']) < 0.01:
                            score += 20
                        elif abs(monto - row['monto']) < 1.0:
                            score += 10

                    if score > best_score:
                        best_score = score
                        best_match = row

                if best_match and best_score >= 60:
                    new_titulo = best_match['proyecto']
                    if new_titulo and len(new_titulo) >= 3 and new_titulo != titulo_actual:
                        fixes.append((oid, titulo_actual, new_titulo, best_score, pnombre, best_match['empresa']))
                    elif new_titulo == titulo_actual:
                        print(f"    ID {oid}: same title '{titulo_actual[:60]}' (score={best_score})")
                    else:
                        print(f"    ID {oid}: no usable title found, best='{new_titulo[:60] if new_titulo else ''}' (score={best_score})")
                else:
                    print(f"    ID {oid}: no match found (best_score={best_score})")
                    if best_match:
                        print(f"      looking for: '{pnombre}'")
                        print(f"      closest: '{best_match['empresa']}' -> proy='{best_match['proyecto'][:60]}'")

    if DOWNLOAD_ONLY:
        print(f"\nDownloads complete.")
        conn.close()
        return

    # Show / apply fixes
    print(f"\n{'='*60}")
    print(f"RESULTS: {len(fixes)} fixes found")
    print(f"{'='*60}")

    for oid, old, new, score, pnombre, empresa in fixes:
        print(f"\n  ID {oid}:")
        print(f"    persona: {pnombre}")
        print(f"    empresa: {empresa}")
        print(f"    old: '{old[:70]}'")
        print(f"    new: '{new}'")
        print(f"    score: {score}")

        if RUN:
            c.execute("UPDATE obra SET titulo = ? WHERE id = ?", (new, oid))
            print(f"    → APPLIED")

    if RUN:
        conn.commit()
        print(f"\n✅ {len(fixes)} obras actualizadas.")
    else:
        print(f"\nDry run — {len(fixes)} fixes would be applied. Use --run to apply.")

    conn.close()


if __name__ == '__main__':
    main()
