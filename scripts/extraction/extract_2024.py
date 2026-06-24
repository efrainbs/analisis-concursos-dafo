#!/usr/bin/env python3
"""
Extract DAFO beneficiaries from PDFs across multiple years (2019-2025).
Reads PDF URLs from dafo_pdfs_map.json, parses, and outputs SQL.
"""

import subprocess, re, sys, os, json, sqlite3, urllib.parse, unicodedata

from dafo_common import (
    _parse_amount_str, extract_rd_num, extract_fecha, q, split_name,
    REGIONS, REGION_NAMES_UPPER, FALLO_HEADER_KEYWORDS,
    get_concurso_anual_id, get_modalidad_id, resolve_region,
    DB_PATH, TMP_DIR
)

os.makedirs(TMP_DIR, exist_ok=True)

with open(os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/dafo_pdfs_map.json")) as f:
    PDF_MAP = json.load(f)

# Aliases for backward compatibility
get_code = get_concurso_anual_id
get_modalidad = get_modalidad_id

# ── Year Configuration ────────────────────────────────────────────────────

YEAR_CONFIG = {
    '2024': {
        'convocatoria_id': 6,
        'fallo_final_mapping': {
            '2024-CPF-D-FalloFinalJurado.pdf': ('CPF', 'Desarrollo'),
            '2024-CPF-N-NuevosRealizadores-FalloFinal.pdf': ('CPF', 'Nuevos realizadores'),
            '2024-CPF-N-3ERO-FalloFinal.pdf': ('CPF', 'Tercer largometraje a más'),
            '2024-CPF-R-FalloFinal.pdf': ('CPF', 'Regiones'),
            '2024-CDO-D-FalloFinalJurado.pdf': ('CDO', 'Desarrollo'),
            '2024-CDO-P-FalloFinalJurado.pdf': ('CDO', 'Producción'),
            '2024-CPC-OperaPrima-FalloFinal+RVM000334-2024-VMPCIC.pdf': ('CPC', 'Ópera prima'),
            '2024-CPC-OP-FalloFinalJurado.pdf': ('CPC', 'Ópera prima'),
            '2024-CPC-2daObra-FalloFinalJurado+Dejarsinefecto.pdf': ('CPC', 'Segunda obra a más'),
            '2024-CPC-2daObra-FalloFinalJurado.pdf': ('CPC', 'Segunda obra a más'),
            '2024-CPA-D-S-Pre-FalloFinal.pdf': ('CPA', 'Desarrollo, Preproducción, Desarrollo de series'),
            '2024-CPA-C-FalloFinal.pdf': ('CPA', 'Cortometrajes'),
            '2024-CDV-FalloFinal.pdf': ('CDV', ''),
            '2024-CGC-FalloFinalJurado.pdf': ('CGC', ''),
            '2024-CCM-FalloFinal.pdf': ('CCM', ''),
            '2024-CDC-FalloFinal.pdf': ('CDC', ''),
            '2024-CGS-FalloFinal.pdf': ('CGS', ''),
            '2024-CFO-FalloFinalJurado.pdf': ('CFO', ''),
            '2024-CFO-FalloFinalSegundaFase.pdf': ('CFO', ''),
            '2024-CIC-FalloFinalJurado.pdf': ('CIC', ''),
            '2024-CHB-FalloFinal.pdf.pdf': ('CBI', ''),
        },
        'rd_single_cols': {
            'EDI': [
                ('empresa', 0, 55),
                ('region', 55, 83),
                ('proyecto', 83, 110),
                ('monto', 110, 140),
            ],
            'EPA': [
                ('codigo', 0, 27),
                ('empresa', 27, 49),
                ('region', 49, 64),
                ('proyecto', 64, 89),
                ('responsable', 89, 114),
                ('monto', 114, 140),
            ],
            'EPI': [
                ('nombre', 0, 33),
                ('region', 33, 50),
                ('obra', 50, 82),
                ('evento', 82, 113),
                ('monto', 113, 140),
            ],
        },
    },
    '2023': {
        'convocatoria_id': 5,
        'fallo_final_mapping': {
            '2023-CDV-Fallo-RD 001128-2023-DGIA.pdf': ('CDV', ''),
        },
        'rd_single_cols': {
            'EDI': [
                ('empresa', 0, 45),
                ('region', 45, 60),
                ('proyecto', 60, 100),
                ('monto', 100, 140),
            ],
            'EPA': [
                ('codigo', 0, 8),
                ('empresa', 8, 45),
                ('region', 45, 60),
                ('proyecto', 60, 100),
                ('responsable', 100, 120),
                ('monto', 120, 140),
            ],
            'EPI': [
                ('nombre', 0, 45),
                ('region', 45, 60),
                ('evento', 60, 110),
                ('monto', 110, 140),
            ],
        },
    },
    '2022': {
        'convocatoria_id': 4,
        'fallo_final_mapping': {
            '2022-CCC-FalloFinal.pdf': ('CCC', ''),
            '2022-CCE-FalloFinal.pdf': ('CCE', ''),
            '2022-CCM-FalloFinal.pdf': ('CCM', ''),
            '2022-CDC-FalloFinal.pdf': ('CDC', ''),
            '2022-CDE-FalloFinal.pdf': ('CPF', ''),
            '2022-CDL-FalloFinalJurado.pdf': ('DLO', ''),
            '2022-CDO-FalloFinal.pdf': ('CDO', ''),
            '2022-CDV-FalloFinal.pdf': ('CDV', ''),
            '2022-CFO-FalloFinal.pdf': ('CFO', ''),
            '2022-CGC-FalloFinalJurado.pdf': ('CGC', ''),
            '2022-CGS-FalloFinalJurado.pdf': ('CGS', ''),
            '2022-CIC-FalloFinal.pdf.pdf': ('CIC', ''),
            '2022-CIN-FalloFinalJurado.pdf': ('CIN', ''),
            '2022-CNM-FalloFinal.pdf': ('NMA', ''),
            '2022-CPA-FalloFinal.pdf': ('CPA', ''),
            '2022-CPC-FalloFinal.pdf': ('CPC', ''),
            '2022-CPR-FalloFinal+ErrorMaterial.pdf': ('EPA', ''),
            '2022-CPS-FalloFinalJurado.pdf': ('PDS', ''),
            '2022-CFN-FalloFinalNuevosRealizadores.pdf': ('CPF', ''),
            '2022-CFN-FalloFinalTercer.pdf': ('CPF', ''),
            '2022-CFR-FalloFinal.pdf': ('CFO', ''),
        },
        'rd_single_cols': {
            'EDI': [
                ('empresa', 0, 50),
                ('region', 50, 65),
                ('proyecto', 65, 105),
                ('monto', 105, 140),
            ],
            'EPI': [
                ('nombre', 0, 45),
                ('region', 45, 60),
                ('evento', 60, 110),
                ('monto', 110, 140),
            ],
        },
    },
    '2021': {
        'convocatoria_id': 3,
        'fallo_final_mapping': {
            '2021-CCE-FalloFinalJurado.pdf': ('CCE', ''),
            '2021-CCM-FalloFinal.pdf': ('CCM', ''),
            '2021-CDE-FalloFinal.pdf': ('CPF', ''),
            '2021-CDO-FalloFinal.pdf': ('CDO', ''),
            '2021-CDV-FalloFinal.pdf': ('CDV', ''),
            '2021-CFO-Fallo Final.pdf': ('CFO', ''),
            '2021-CGC-Fallo Final.pdf': ('CGC', ''),
            '2021-CPA-FalloFinal.pdf': ('CPA', ''),
            '2021-CPC-FalloFinal.pdf': ('CPC', ''),
            '2021-CPS-FalloFinal.pdf': ('PDS', ''),
            '2021-CAL-FalloFinal.pdf': ('PAL', ''),
            '2021-PDT-FalloFinal.pdf': ('PDT', ''),
            '2021-CCA-FalloFinal.pdf': ('CCC', ''),
            '2021-CFN-FalloFinal.pdf': ('CPF', ''),
            '2021-CNM-FalloFinalJurado.pdf': ('NMA', ''),
            '2021-CFR-FalloFinalJurado.pdf': ('CFO', ''),
            '2021-CLC-FalloFinal.pdf': ('CDL', ''),
        },
        'rd_single_cols': {
            'EDI': [
                ('empresa', 0, 50),
                ('region', 50, 65),
                ('proyecto', 65, 105),
                ('monto', 105, 140),
            ],
            'EPA': [
                ('codigo', 0, 8),
                ('empresa', 8, 45),
                ('region', 45, 60),
                ('proyecto', 60, 100),
                ('responsable', 100, 120),
                ('monto', 120, 140),
            ],
            'EPI': [
                ('nombre', 0, 45),
                ('region', 45, 60),
                ('evento', 60, 110),
                ('monto', 110, 140),
            ],
        },
    },
    '2020': {
        'convocatoria_id': 2,
        'fallo_final_mapping': {
            '2020-CCE-FalloFinal.pdf': ('CCE', ''),
            '2020-CCM-FalloFinal.pdf': ('CCM', ''),
            '2020-CDE-FalloFinal.pdf': ('CPF', ''),
            '2020-CDO-FalloFInal.pdf': ('CDO', ''),
            '2020-CFO-FalloFinal_0.pdf': ('CFO', ''),
            '2020-CFR-FalloFinal.pdf': ('CFO', ''),
            '2020-CGC-FalloFinal.pdf': ('CGC', ''),
            '2020-CPC-Fallo final.pdf': ('CPC', ''),
            '2020-CPR-FalloFinal.pdf': ('EPA', ''),
            '2020 CPS FalloFinal.pdf': ('PDS', ''),
            '2020-CFN-FalloFinal.pdf': ('CPF', ''),
            '2020-CCA-FalloFinal.pdf': ('CCC', ''),
            '2020 - CGS - FalloFinal.pdf': ('CGS', ''),
            '2020-CNM-FalloFinal.pdf': ('NMA', ''),
            '2020-CPA-FalloFinalJurado.pdf': ('CPA', ''),
            '2020-CDI-FalloFinal.pdf': ('CDL', ''),
            '2020-CLC-FalloFinal.pdf': ('CDL', ''),
        },
        'rd_single_cols': {
            'EPI': [
                ('nombre', 0, 45),
                ('region', 45, 60),
                ('evento', 60, 110),
                ('monto', 110, 140),
            ],
        },
    },
    '2019': {
        'convocatoria_id': 1,
        'fallo_final_mapping': {
            '2019 Bicentenario -  Fallo final.pdf': ('CBI', ''),
            '2019 Experimental - Fallo final.pdf': ('CCE', ''),
            '2019 CDI - Fallo final del Jurado.pdf': ('CDL', ''),
            '2019 CFO - Fallo final jurado.pdf': ('CFO', ''),
            '2019 CFR - Fallo final del jurado.pdf': ('CFO', ''),
            '2019 Cortometraje -Fallo final.pdf': ('CPC', ''),
            '2019 CCO - Fallo final del jurado.pdf': ('CPC', ''),
            '2019 CDE - Fallo final.pdf': ('CPF', ''),
            '2019 Largo ficción - Fallo final.pdf': ('CPF', ''),
            '2019 CEA - Fallo final del jurado.pdf': ('CPF', ''),
            '2019 Nuevos medios - Fallo final.pdf': ('NMA', ''),
            '2019 Piloto serie - Fallo final.pdf': ('PDS', ''),
            '2019 Coproducción -Fallo final.pdf': ('CCM', ''),
            '2019 Documental-Fallo final.pdf': ('CDO', ''),
            '2019 Largo en construcción - Fallo final.pdf': ('CCC', ''),
            '2019 CGC - Fallo final.pdf': ('CGC', ''),
            '2019 Gestión de sala - Fallo final.pdf': ('CGS', ''),
            '2019 Preservación -Fallo final.pdf': ('EPA', ''),
            '2019 CPA - Fallo final del Jurado.pdf': ('CPA', ''),
        },
        'rd_single_cols': {},
    },
}

# Cache for concurso_anual lookups
CODES = {}

def get_code(codigo, convocatoria_id):
    key = (codigo, convocatoria_id)
    if key in CODES:
        return CODES[key]
    val = get_concurso_anual_id(codigo, convocatoria_id=convocatoria_id)
    if val:
        CODES[key] = val
    return val

def detect_table_columns(layout_lines, extra_keywords=None):
    """Detect column boundaries from header keywords plus alignment scan.
    Works for FalloFinal and multi-beneficiary RD table formats.
    Only considers keywords from lines that are actual table header rows
    (containing 2+ keyword matches), to avoid pollution from data lines.
    """
    keywords = list(FALLO_HEADER_KEYWORDS)
    if extra_keywords:
        keywords.extend(extra_keywords)
    
    # First pass: identify header lines (2+ keyword matches)
    header_line_set = set()
    for i, line in enumerate(layout_lines[:30]):
        count = 0
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', line):
                count += 1
        if count >= 2:
            header_line_set.add(i)
    
    # Expand to adjacent lines that have at least 1 keyword match
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
    
    # Fallback: if no header line found, use the first 30 lines (original behaviour)
    if not header_line_set:
        for i in range(min(30, len(layout_lines))):
            header_line_set.add(i)
    
    # Second pass: extract keyword positions only from identified header lines
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

    # empresa: 0 to first non-persona keyword
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
    director_col_name = 'director'
    for k in ('RESPONSABLE', 'DIRECTOR'):
        if k in headers_found:
            director_pos = headers_found[k]
            director_col_name = 'responsable' if k == 'RESPONSABLE' else 'director'
            break
    if director_pos is None:
        director_pos = 90

    categoria_pos = headers_found.get('CATEGORÍA', None)
    evento_pos = headers_found.get('EVENTO', None)
    obra_pos = headers_found.get('OBRA', None)
    institucion_pos = headers_found.get('INSTITUCIÓN', None) or headers_found.get('INSTITUCION', None)
    programa_pos = headers_found.get('PROGRAMA', None)

    def end_before(ref_pos, margin=2):
        if ref_pos:
            return max(region_pos + 10, ref_pos - margin)
        return ref_pos

    if institucion_pos and programa_pos:
        # FCA-style: PERSONA NATURAL | REGIÓN | INSTITUCIÓN EDUCATIVA | PROGRAMA DE FORMACIÓN
        # Handle reversed order (some PDFs put PROGRAMA before INSTITUCIÓN)
        first_col = min(institucion_pos, programa_pos)
        second_col = max(institucion_pos, programa_pos)
        col_defs.append(('region', region_pos, first_col))
        if institucion_pos < programa_pos:
            col_defs.append(('institucion', first_col, second_col))
            col_defs.append(('programa', second_col, director_pos))
        else:
            col_defs.append(('programa', first_col, second_col))
            col_defs.append(('institucion', second_col, director_pos))
    elif evento_pos:
        # Determine where evento column ends: use monto if available, else fallback
        evento_end = director_pos
        for ek in ('MONTO', 'OTORGADO'):
            if ek in headers_found:
                evento_end = max(evento_pos + 10, headers_found[ek] - 2)
                break
        if obra_pos:
            # EPI-style: PERSONA NATURAL | REGIÓN | OBRA VINCULADA | EVENTO INTERNACIONAL | MONTO
            col_defs.append(('region', region_pos, obra_pos))
            col_defs.append(('proyecto', obra_pos, evento_pos))
            col_defs.append(('evento', evento_pos, evento_end))
        else:
            # Simpler: PERSONA NATURAL | REGIÓN | EVENTO INTERNACIONAL | MONTO
            col_defs.append(('region', region_pos, evento_pos))
            col_defs.append(('evento', evento_pos, evento_end))
    elif has_titulo:
        titulo_pos = headers_found['TÍTULO' if 'TÍTULO' in headers_found else 'TITULO']
        p_start = max(0, titulo_pos - 2)
        p_end = end_before(categoria_pos or director_pos)
        d_start = end_before(director_pos, 2)
        col_defs.append(('region', region_pos, p_start))
        col_defs.append(('proyecto', p_start, p_end))
        col_defs.append((director_col_name, d_start, d_start + 22))
    elif has_proyecto and has_categoria:
        p_start = region_pos + 13
        p_end = end_before(categoria_pos)
        d_start = end_before(director_pos, 4)
        c_start = max(p_end, categoria_pos - 2)
        c_end = d_start - 2 if d_start and d_start > c_start else c_start + 15
        col_defs.append(('region', region_pos, p_start))
        col_defs.append(('proyecto', p_start, p_end))
        col_defs.append(('categoria', c_start, c_end))
        col_defs.append((director_col_name, d_start, d_start + 22))
    elif has_proyecto:
        if director_pos and director_pos < 95:
            d_start = max(region_pos + 18, director_pos - 6)
            col_defs.append(('region', region_pos, region_pos + 18))
            col_defs.append(('proyecto', region_pos + 18, d_start))
            col_defs.append((director_col_name, d_start, d_start + 28))
        else:
            col_defs.append(('region', region_pos, region_pos + 15))
            col_defs.append(('proyecto', region_pos + 15, director_pos or 90))
            col_defs.append((director_col_name, (director_pos or 90), (director_pos or 90) + 22))
    else:
        col_defs.append(('region', region_pos, region_pos + 20))
        col_defs.append(('proyecto', region_pos + 20, director_pos))
        col_defs.append((director_col_name, director_pos, director_pos + 22))

    # monto column
    monto_kw = None
    for k in ('MONTO', 'OTORGADO'):
        if k in headers_found:
            monto_kw = k
            break
    if monto_kw:
        m_start = max(0, headers_found[monto_kw] - 2)
        col_defs.append(('monto', m_start, m_start + 25))

    # Fill missing with fallback (skip director if evento is already defined — EPI has no director)
    defined = {c[0] for c in col_defs}
    needed = [('empresa', 0, 40), ('region', 40, 63), ('proyecto', 63, 90),
              ('monto', 110, 150)]
    if 'evento' not in defined:
        needed.append((director_col_name, 90, 110))
    for name, s, e in needed:
        if name not in defined:
            col_defs.append((name, s, e))
    col_defs.sort(key=lambda x: x[1])

    # Prevent overlap
    for i in range(len(col_defs) - 1):
        n, s, e = col_defs[i]
        ns = col_defs[i+1][1]
        if e > ns:
            col_defs[i] = (n, s, ns)

    return col_defs

def get_empresa_range(col_defs):
    for name, start, end in col_defs:
        if name == 'empresa':
            return start, end
    return 0, 40

def parse_fallo_beneficiaries(layout_a1, extra_header_kws=None, fixed_monto=None):
    lines = layout_a1.split('\n')
    col_defs = detect_table_columns(lines, extra_keywords=extra_header_kws)

    data_start = None
    first_empresa_line = None
    header_passed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        has_header_kw = any(kw in line for kw in FALLO_HEADER_KEYWORDS)
        if has_header_kw:
            header_passed = True
            continue
        if not header_passed:
            continue
        if any(kw in stripped for kw in ['DECLARAR', 'Declárese', 'Declarar', 'Consígnese',
                                           'Art.', 'copia auténtica', 'DESPACHO',
                                           'DIRECCIÓN GENERAL', 'Decenio', 'Año de la',
                                           'Regístrese', 'Comuníquese']):
            continue
        left_text = line[:20].strip()
        if not left_text or len(left_text) < 3:
            continue
        first_empresa_line = i
        break

    # Expand data_start backward to include preamble lines (responsible+monto
    # that appear before the first empresa line). Walk back from first_empresa_line
    # to the first blank line or header keyword line.
    if first_empresa_line is not None:
        data_start = first_empresa_line
        for j in range(first_empresa_line - 1, -1, -1):
            prev = lines[j]
            if not prev.strip():
                break  # blank line boundary
            # Don't go back past header keywords
            if any(kw in prev for kw in FALLO_HEADER_KEYWORDS):
                break
            data_start = j

    if data_start is None:
        return []

    emp_start, emp_end = get_empresa_range(col_defs)

    def line_has_ruc(line):
        return bool(re.search(r'\d{11}', line[emp_start:emp_end].replace(' ', '')))

    def line_has_dni(line):
        return bool(re.search(r'(?<!\d)\d{8}(?!\d)', line[emp_start:emp_end]))

    def is_page_header(line):
        stripped = line.strip()
        if any(kw in stripped for kw in ['DESPACHO', 'DIRECCIÓN GENERAL',
                                           'PATRIMONIO CULTURAL',
                                           'INDUSTRIAS CULTURALES']):
            return True
        # Year motto headers that leak into table data on page breaks
        # Spanish: "Decenio de...", "Año del..."
        # Quechua/Aymara: "Perú Suyuna Paya..."
        if re.match(r'^["\']?(?:Decenio|Año\s+del?\s+|Perú\s+Suyuna)', stripped, re.IGNORECASE):
            return True
        return False

    def is_page_footer(line):
        stripped = line.strip()
        if any(kw in stripped for kw in ['copia auténtica', 'Art. 25', '070-2013-PCM',
                                           'contrastadas', 'validadorDocumental']):
            return True
        # "clave:" verification codes from digital signature footer
        if re.match(r'^clave:\s*', stripped, re.IGNORECASE):
            return True
        return False

    def is_next_article(line):
        stripped = line.strip()
        return any(kw in stripped for kw in ['ARTÍCULO SEGUNDO', 'ARTICULO SEGUNDO',
                                               'Artículo Segundo', 'Regístrese', 'Comuníquese'])

    lines_copy = list(lines[data_start:])

    # First pass: split blocks at RUC lines (RUC line belongs to the block it ends)
    blocks = []
    current = []
    skip_until_empresa = False
    i = 0
    while i < len(lines_copy):
        line = lines_copy[i]
        stripped = line.strip()
        if is_next_article(line):
            if current:
                blocks.append(current)
            break
        if not stripped:
            i += 1
            continue
        if is_page_header(line) or is_page_footer(line):
            if current:
                blocks.append(current)
                current = []
            skip_until_empresa = True
            i += 1
            continue
        if skip_until_empresa:
            emp_text = line[emp_start:emp_end].strip()
            if not emp_text or len(emp_text) < 3:
                i += 1
                continue
            skip_until_empresa = False
        if line_has_ruc(line) or line_has_dni(line):
            current.append(line)
            if current:
                blocks.append(current)
            current = []
            # Peek ahead: merge director-only lines (no empresa text) into this block
            j = i + 1
            while j < len(lines_copy):
                next_line = lines_copy[j]
                ns = next_line.strip()
                if not ns:
                    j += 1
                    continue
                if is_page_header(next_line) or is_page_footer(next_line):
                    break  # don't cross page boundaries in peek-ahead
                if is_next_article(next_line):
                    break
                # If next line has no empresa text, it's director-only → add to previous block
                nxt_emp = next_line[emp_start:emp_end].strip()
                if nxt_emp and len(nxt_emp) >= 3:
                    break  # has company text → new entry starting
                # Don't merge monto preamble lines — they belong to the next entry
                if re.search(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', next_line):
                    break
                blocks[-1].append(next_line)
                j += 1
            i = j
        else:
            current.append(line)
            i += 1
    if current:
        blocks.append(current)

    # Check if we have ANY RUC or DNI numbers in the data at all
    all_data_lines = [l for block in blocks for l in block]
    has_any_ruc = any(line_has_ruc(l) for l in all_data_lines)
    has_any_dni = any(line_has_dni(l) for l in all_data_lines)

    def has_any_monto_in_block(block_lines, monto_col):
        """Check if any line in a block has a monto value in the monto column."""
        ms, me = monto_col
        for bl in block_lines:
            if len(bl) > ms:
                if re.search(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', bl[ms:me]):
                    return True
        return False

    if not has_any_ruc:
        # Fallback for FalloFinals without RUC (Persona Natural, 2022 and earlier):
        # Strategy depends on whether a MONTO column is detected.
        monto_col = None
        for c_name, cs, ce in col_defs:
            if c_name == 'monto':
                monto_col = (cs, ce)
                break

        if monto_col:
            # Check if any line actually has monto content in the monto column
            ms_check, me_check = monto_col
            has_monto_data = any(
                re.search(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', l[ms_check:me_check])
                for l in lines_copy if len(l) > ms_check
            )

        if monto_col and has_monto_data:
            # Monto-anchored block splitting with continuation support:
            # - Lines are collected into a block.
            # - When a line has monto content (S/...), the entry is "completed"
            #   but continuations (suffixes, director names) may follow.
            # - A new entry starts when a blank line or page break occurs
            #   AND the previous block has monto content.
            # - Also, a new entry starts when a line has BOTH empresa text
            #   (not suffix) AND region content, after the previous block
            #   has been completed.
            SUFFIX_SET = {'E.I.R.L.', 'EIRL', 'S.A.C.', 'S.A.C', 'SAC',
                          'S.A.', 'SA', 'S.R.L.', 'SRL', 'SOCiedad'}
            NON_STARTING_EMPRESA_WORDS = {'PRODUCCIONES'}
            def is_likely_suffix(text):
                u = text.upper().strip()
                if u in {s.upper() for s in SUFFIX_SET}:
                    return True
                if re.match(r'^[\s.,;:\-()/&]+$', text):
                    return True
                return False

            def _has_real_empresa(l):
                t = l[emp_start:emp_end].strip()
                return bool(t and t.upper().strip() not in REGION_NAMES_UPPER)

            blocks = []
            current = []
            block_has_monto = False
            monto_start, monto_end = monto_col
            for line in lines_copy:
                stripped = line.strip()
                if not stripped:
                    # Blank line: save current block and reset
                    # (always save, even without monto — prevents fragment merging)
                    if current and any(_has_real_empresa(l) for l in current if len(l) > emp_start):
                        blocks.append(current)
                    current = []
                    block_has_monto = False
                    continue
                if is_page_header(line) or is_page_footer(line):
                    if current:
                        if any(_has_real_empresa(l) for l in current if len(l) > emp_start):
                            blocks.append(current)
                        current = []
                        block_has_monto = False
                    continue
                if is_next_article(line):
                    if current:
                        if any(_has_real_empresa(l) for l in current if len(l) > emp_start):
                            blocks.append(current)
                    break

                # Check if this line starts a NEW entry after a completed block
                emp_text = line[emp_start:emp_end].strip() if len(line) > emp_start else ''
                # Detect region name bleeding into empresa column (column misalignment)
                if emp_text and emp_text.upper().strip() in REGION_NAMES_UPPER:
                    emp_text = ''
                # Skip known continuation words that never start a company name
                if emp_text and emp_text.upper().strip() in NON_STARTING_EMPRESA_WORDS:
                    emp_text = ''
                if emp_text and len(emp_text) >= 3 and not is_likely_suffix(emp_text):
                    # Has empresa text that could start a new entry
                    # Check if it also has region or proyecto (completing line of a new entry)
                    region_col = None
                    proy_col = None
                    for c_name, cs, ce in col_defs:
                        if c_name in ('region',):
                            region_col = (cs, ce)
                        if c_name in ('proyecto', 'evento', 'propuesta', 'proyecto_o_evento'):
                            proy_col = (cs, ce)
                    has_region = (region_col and len(line) > region_col[0] and
                                  line[region_col[0]:region_col[1]].strip() != '')
                    has_proy = (proy_col and len(line) > proy_col[0] and
                                line[proy_col[0]:proy_col[1]].strip() != '')

                    if block_has_monto and current and (has_region or has_proy):
                        # Check if THIS line also has monto content.
                        # If not, it's a continuation line (not a new entry),
                        # even if it has a legal suffix.
                        has_own_monto = (
                            len(line) > monto_start and
                            bool(re.search(r'(?:S/?\.?\s*)?[\d\s,]+[.,]\d{2}',
                                           line[monto_start:monto_end].strip()))
                        )
                        # Fallback: search whole line if column range doesn't match
                        # (handles 2021-CDO where S/ is outside the detected monto column)
                        if not has_own_monto:
                            has_own_monto = bool(re.search(r'(?:S/?\.?\s*)?[\d\s,]+[.,]\d{2}', line))
                        # Only split if empresa text contains a legal form suffix,
                        # AND the line has its own monto content
                        has_legal_suffix = bool(re.search(r'(?:S\.?\s*A\.?\s*C\.?|E\.?\s*I\.?\s*R\.?\s*L\.?|S\.?\s*R\.?\s*L\.?|S\.?\s*R\.?L\.?)\s*$', emp_text, re.IGNORECASE))
                        if has_own_monto:
                            # Also check accumulated empresa text for suffix (multi-line
                            # company names like "ARMADILLO PRODUCCIONES S.A.C." split across
                            # lines: 'ARMADILLO', 'PRODUCCIONES', 'S.A.C.').
                            if not has_legal_suffix:
                                acc_emp = ' '.join(
                                    l[emp_start:emp_end].strip()
                                    for l in current if len(l) > emp_start
                                ).strip()
                                if acc_emp:
                                    acc_with_current = acc_emp + ' ' + emp_text
                                    has_legal_suffix = bool(re.search(r'(?:S\.?\s*A\.?\s*C\.?|E\.?\s*I\.?\s*R\.?\s*L\.?|S\.?\s*R\.?\s*L\.?)\s*$', acc_with_current, re.IGNORECASE))
                            # Split on empresa+region+monto even without suffix
                            # (handles 2021-CDO multi-line table where each entry's
                            #  company fragment, region, and monto share one line).
                            if not has_legal_suffix and (has_region or has_proy) and block_has_monto:
                                if any(_has_real_empresa(l) for l in current if len(l) > emp_start):
                                    blocks.append(current)
                                    current = []
                                    block_has_monto = False
                            if has_legal_suffix and has_own_monto:
                                # Only split if current block already has empresa content.
                                # If current only has responsible+monto preamble lines,
                                # keep them together with the new empresa line
                                # (they belong to the same entry).
                                if any(_has_real_empresa(l) for l in current if len(l) > emp_start):
                                    blocks.append(current)
                                    current = []
                                    block_has_monto = False
                                # else: no split — preamble lines stay with this entry
                    elif block_has_monto and current and not has_region and not has_proy:
                        # Line has empresa text but no region/proyecto — could be the
                        # first line of a new entry after a suffix-only continuation.
                        # Check if the most recent empresa line in current was a legal
                        # suffix (handles multi-line tables like 2021-CDO where company
                        # names with suffix like 'S.A.C.' end an entry, and the next
                        # left-aligned word starts a new entry).
                        last_emp_text = ''
                        for l in reversed(current):
                            if len(l) > emp_start and l[emp_start:emp_end].strip():
                                last_emp_text = l[emp_start:emp_end].strip()
                                break
                        if last_emp_text:
                            prev_is_suffix = bool(re.search(r'(?:S\.?\s*A\.?\s*C\.?|E\.?\s*I\.?\s*R\.?\s*L\.?|S\.?\s*R\.?\s*L\.?)\s*$', last_emp_text, re.IGNORECASE))
                            # Also split when accumulated empresa has ≤ 2 words
                            # (company name is likely complete, next empresa starts new entry).
                            # Handles 2021-CDO where entries lack legal suffixes
                            # (e.g. SANS SOLEIL followed by SERENDIPIA).
                            acc_words = ' '.join(
                                l[emp_start:emp_end].strip()
                                for l in current if len(l) > emp_start
                            ).strip().split()
                            short_name = len(acc_words) <= 2
                            if prev_is_suffix or short_name:
                                if any(_has_real_empresa(l) for l in current if len(l) > emp_start):
                                    blocks.append(current)
                                    current = []
                                    block_has_monto = False
                    elif current and not block_has_monto:
                        # No monto on any data line (e.g., 2019-style table).
                        # Detect new entries by checking if the accumulated empresa
                        # text ends with a known legal suffix (E.I.R.L., S.A.C., etc.).
                        acc_emp = ' '.join(
                            l[emp_start:emp_end].strip()
                            for l in current if len(l) > emp_start
                        ).strip()
                        if acc_emp and re.search(r'(?:S\.?\s*A\.?\s*C\.?|E\.?\s*I\.?\s*R\.?\s*L\.?|S\.?\s*R\.?\s*L\.?)\s*$', acc_emp, re.IGNORECASE):
                            if any(_has_real_empresa(l) for l in current if len(l) > emp_start):
                                blocks.append(current)
                                current = []
                                block_has_monto = False

                current.append(line)

                # Check if THIS line has monto content — marks entry as completed
                if not block_has_monto and len(line) > monto_start:
                    monto_val = line[monto_start:monto_end].strip()
                    if re.search(r'(?:S/?\.?\s*)?[\d\s,]+[.,]\d{2}', monto_val):
                        block_has_monto = True
                # Fallback: whole-line search for monto (handles misaligned columns)
                if not block_has_monto and re.search(r'S/?\.?\s*[\d\s,]+[.,]\d{2}', line):
                    block_has_monto = True

            if current:
                if any(_has_real_empresa(l) for l in current if len(l) > emp_start):
                    blocks.append(current)
        else:
            # No MONTO column, or no actual monto data in lines:
            # Group consecutive non-blank lines into entries, splitting at
            # blank lines and page header/footer artifacts.
            # Each group becomes one beneficiary (handles 2019-style tables
            # where the empresa column contains fragments of names/companies).
            blocks = []
            current = []
            for line in lines_copy:
                stripped = line.strip()
                if not stripped:
                    # Blank line: finalize current block if it has empresa content
                    if current and any(l[:emp_start+1].strip() or
                                       (emp_start < len(l) and l[emp_start:emp_end].strip())
                                       for l in current if l.strip()):
                        blocks.append(current)
                    current = []
                    continue
                if is_next_article(line):
                    if current:
                        blocks.append(current)
                    break
                if is_page_header(line) or is_page_footer(line):
                    if current:
                        blocks.append(current)
                        current = []
                    continue
                # Detect new entries within a block when no monto column:
                # accumulated empresa name ending with legal suffix signals
                # the previous entry is complete; following empresa text
                # starts a new entry.
                if current and len(line) > emp_start:
                    new_emp = line[emp_start:emp_end].strip()
                    if new_emp and len(new_emp) >= 3 and new_emp.upper() not in REGION_NAMES_UPPER:
                        acc_emp = ' '.join(
                            l[emp_start:emp_end].strip()
                            for l in current if len(l) > emp_start
                        ).strip()
                        if acc_emp and re.search(r'(?:S\.?\s*A\.?\s*C\.?|E\.?\s*I\.?\s*R\.?\s*L\.?|S\.?\s*R\.?\s*L\.?)\s*$', acc_emp, re.IGNORECASE):
                            if any(l[:emp_start+1].strip() or
                                   (emp_start < len(l) and l[emp_start:emp_end].strip())
                                   for l in current if l.strip()):
                                blocks.append(current)
                                current = []
                current.append(line)
            if current:
                if any(l[:emp_start+1].strip() or
                       (emp_start < len(l) and l[emp_start:emp_end].strip())
                       for l in current if l.strip()):
                    blocks.append(current)

    beneficiaries = []
    for block in blocks:
        if not block:
            continue
        block_text = ' '.join(block)
        # In RUC-less fallback mode, skip the RUC check; in RUC mode require it
        if has_any_ruc and not any(line_has_ruc(l) for l in block) \
           and not any(line_has_dni(l) for l in block):
            continue

        b = {}
        for col_name, col_start, col_end in col_defs:
            text = ' '.join(line[col_start:col_end].strip() for line in block if line[col_start:col_end].strip())
            if text:
                b[col_name] = text

        if not b:
            continue

        empresa_text = b.get('empresa', '')

        # Skip page artifacts and section headers
        emp_stripped = empresa_text.strip().upper()
        skip_prefixes = ['CLAVE:', 'CATEGORÍA', 'CATEGORIA', 'PERSONA JURÍDICA', 'PERSONA NATURAL', '(DNI)']
        if any(emp_stripped.startswith(p) for p in skip_prefixes):
            continue
        # Skip entries where empresa is just a RUC in parentheses (RUC-only artifact line)
        if re.match(r'^\(\d{11}\)$', empresa_text.strip()):
            continue
        # Skip blocks that are entirely from page header/footer content
        if not empresa_text.strip() and all(
            is_page_footer(l) or is_page_header(l) or not l.strip()
            for l in block):
            continue

        ruc_match = re.search(r'(\d{11})', empresa_text.replace(' ', ''))
        if ruc_match:
            b['ruc'] = ruc_match.group(1)
        else:
            ruc_match2 = re.search(r'\((\d{11})\)', block_text)
            if ruc_match2:
                b['ruc'] = ruc_match2.group(1)
            else:
                b['ruc'] = ''

        dni_match = re.search(r'(?<!\d)(\d{8})(?!\d)', empresa_text)
        if not dni_match:
            dni_match = re.search(r'\((\d{8})\)', block_text)
        if not dni_match:
            dni_match = re.search(r'(?<!\d)(\d{8})(?!\d)', block_text)

        if ruc_match or ruc_match2:
            b['tipo_persona'] = 'juridica'
        elif dni_match:
            b['tipo_persona'] = 'natural'
            b['dni'] = dni_match.group(1)
        elif has_any_dni and not has_any_ruc:
            b['tipo_persona'] = 'natural'
        else:
            b['tipo_persona'] = 'juridica'

        monto_text = b.get('monto', '')
        am_match = re.search(r'(?:S/?\.?\s*)?([\d\s,]+[.,]\d{2})', monto_text)
        # Also try whole block text — the monto column may only contain
        # the numeric tail (e.g. '000,00') when S/ falls in an adjacent col.
        # Prefer the longer match (more complete monto value).
        am_match2 = re.search(r'S/?\.?\s*([\d\s,]+[.,]\d{2})', block_text)
        if am_match2 and (not am_match or
                          len(am_match2.group(1).replace(' ', '')) >
                          len(am_match.group(1).replace(' ', ''))):
            am_match = am_match2
        if am_match:
            am_str = am_match.group(1).replace(' ', '')
            try:
                b['monto'] = _parse_amount_str(am_str)
            except ValueError:
                b['monto'] = fixed_monto or 0
        else:
            b['monto'] = fixed_monto or 0

        company = empresa_text
        company = re.sub(r'\(?\d{11}\)?', '', company).strip()
        company = re.sub(r'\(?\d{8}\)?', '', company).strip()
        company = re.sub(r'\(DNI\)', '', company, flags=re.IGNORECASE).strip()
        company = re.sub(r'^[\s,;:.\-]+|[\s,;:.\-]+$', '', company)
        company = re.sub(r'\s+', ' ', company).strip()
        b['razon_social'] = company

        region_text = b.get('region', '')
        region_text_clean = re.sub(r'[^A-ZÁÉÍÓÚÑa-záéíóúñ\s]', '', region_text).strip()
        region_text = region_text_clean if len(region_text_clean) > 2 else ''

        # Clean "(REGIÓN)" suffix from region
        region_text = re.sub(r'\s*\(?\s*REGI[OÓ]N\s*\)?\s*$', '', region_text, flags=re.IGNORECASE).strip()

        region_text = resolve_region(region_text)

        # If region_text is still not a valid known region, clear it so fallback can find it
        if region_text and region_text.upper() not in REGION_NAMES_UPPER:
            region_text = ''

        # Fallback: find known region name in empresa column or full block text
        if not region_text or len(region_text) < 3:
            search_text = (empresa_text + ' ' + block_text).upper()
            for r in sorted(REGIONS, key=len, reverse=True):
                ru = r.upper()
                if re.search(r'\b' + re.escape(ru) + r'\b', search_text):
                    region_text = r
                    # Remove region name from company if it leaked in (whole word only)
                    company = re.sub(r'\b' + re.escape(r) + r'\b', '', company, flags=re.IGNORECASE).strip()
                    company = re.sub(r'\s+', ' ', company).strip()
                    b['razon_social'] = company
                    break

        # Remove known region names from end of company name (whole word)
        search_company = company.upper()
        for r in sorted(REGIONS, key=len, reverse=True):
            ru = r.upper()
            if re.search(r'\b' + re.escape(ru) + r'\s*$', search_company):
                company = re.sub(r'\s*' + re.escape(r) + r'\s*$', '', company, flags=re.IGNORECASE).strip()
                company = re.sub(r'\s+', ' ', company).strip()
                if not region_text or len(region_text) < 3:
                    region_text = r
                break
            if len(r) >= 6:
                for trunc_len in [4, 5, 6]:
                    ru_trunc = ru[:trunc_len]
                    if re.search(r'\b' + re.escape(ru_trunc) + r'\s*$', search_company):
                        maybe = search_company[:-trunc_len].strip()
                        if maybe and len(maybe) > 3:
                            company = re.sub(r'\s*' + re.escape(ru_trunc) + r'\s*$', '', company, flags=re.IGNORECASE).strip()
                            company = re.sub(r'\s+', ' ', company).strip()
                            if not region_text or len(region_text) < 3:
                                region_text = r
                            break
                else:
                    continue
                break

        # Final cleanup: strip non-alpha leading/trailing chars from company name
        company = re.sub(r'^[\s,;:.\-()\[\]{}<>/&]+|[\s,;:.\-()\[\]{}<>/&]+$', '', company).strip()
        company = re.sub(r'\s+', ' ', company).strip()
        b['region'] = region_text
        b['razon_social'] = company

        if b.get('tipo_persona') == 'natural':
            name = company
            if ',' in name:
                parts = name.split(',', 1)
                apellidos = parts[0].strip()
                nombres = parts[1].strip()
            else:
                words = name.split()
                if len(words) >= 2:
                    nombres = ' '.join(words[:-1])
                    apellidos = words[-1]
                elif len(words) == 1:
                    nombres = words[0]
                    apellidos = ''
                else:
                    nombres = ''
                    apellidos = ''
            b['nombres'] = nombres
            b['apellidos'] = apellidos

        beneficiaries.append(b)

    return beneficiaries

def parse_rd_beneficiaries(layout_lines, col_defs, category, fixed_monto=None):
    lines = layout_lines

    HEADER_KWS = ['CÓDIGO', 'CODIGO', 'PERSONA', 'JURÍDICA', '(RUC)', 'REGIÓN', 'REGION',
                  'PROYECTO', 'RESPONSABLE', '(DNI)', 'OBRA', 'VINCULADA', 'VINCULADO',
                  'PROYECTO', 'POSTULACION', 'DEL', 'MONTO', 'ESTÍMULO', 'ESTIMULO',
                  'NATURAL', 'EVENTO', 'INTERNACIONAL']
    PREAMBLE_KWS = ['DECLARAR', 'Declárese', 'Declarar', 'Consígnese', 'beneficiaria', 'beneficiario', 'siguiente']

    PAGE_SKIP_KWS = ['copia auténtica', 'Art. 25', '070-2013-PCM', 'contrastadas',
                      'validadorDocumental', 'Decenio', 'Año del', 'Regístrese',
                      'Comuníquese', 'DIRECCIÓN GENERAL', 'DESPACHO',
                      'PATRIMONIO CULTURAL', 'INDUSTRIAS CULTURALES',
                      'Suyuna', 't\'aqwaqtawi', 'maranaka',
                      'Igualdad de Oportunidades', 'Bicentenario del Perú']

    def is_header_line(line):
        if any(kw in line for kw in HEADER_KWS):
            if '(RUC N°' in line or '(DNI N°' in line:
                return False
            return True
        return False

    def is_page_skip_line(line):
        stripped = line.strip()
        return any(kw in stripped for kw in PAGE_SKIP_KWS)

    def has_real_data(line):
        for col_name, cs, ce in col_defs:
            if col_name == 'monto':
                continue
            if len(line) > cs and line[cs:ce].strip():
                # Require empresa/nombre column to have content (header continuation
                # lines like "LA" in EPI lack empresa data)
                if col_name in ('empresa', 'nombre', 'persona'):
                    return True
        return False

    header_passed = False
    data_start = None
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if re.search(r'Persona\s+(Natural|Jur[íi]dica)\s*:', stripped):
            header_passed = True
            i += 1
            continue
        if not header_passed:
            i += 1
            continue
        if any(kw in stripped for kw in PREAMBLE_KWS):
            i += 1
            continue
        if is_header_line(line):
            i += 1
            continue
        if is_page_skip_line(line):
            # Skip the entire page header/footer block until a line with empresa text
            i += 1
            while i < len(lines):
                nxt = lines[i]
                ns = nxt.strip()
                if not ns:
                    i += 1
                    continue
                if has_real_data(nxt):
                    # Found a data line
                    break
                if not is_page_skip_line(nxt):
                    # If it's not a page element but also not data, still skip
                    # Only stop skipping if we find data
                    pass
                i += 1
            continue
        if has_real_data(line):
            data_start = i
            break
        i += 1

    if data_start is None:
        return []

    lines = layout_lines[data_start:]

    def is_end_section(line):
        stripped = line.strip()
        if any(kw in stripped for kw in ['ARTÍCULO SEGUNDO', 'ARTICULO SEGUNDO',
                                          'Artículo Segundo', 'Artículo segundo']):
            return True
        if any(kw in stripped for kw in ['copia auténtica', 'Art. 25', '070-2013-PCM',
                                          'contrastadas', 'Decenio', 'Año del Bicentenario']):
            return True
        return False

    blocks = []
    current = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if is_end_section(line):
            if current:
                blocks.append(current)
                current = []
            break
        current.append(line)
    if current:
        blocks.append(current)

    beneficiaries = []
    for block in blocks:
        if not block:
            continue
        b = {}
        for col_name, col_start, col_end in col_defs:
            parts = []
            for line in block:
                if len(line) > col_start:
                    val = line[col_start:col_end].strip()
                    if val:
                        parts.append(val)
            if parts:
                b[col_name] = ' '.join(parts)

        if not b:
            continue

        block_text = ' '.join(block)

        ruc_match = re.search(r'(?:RUC\s*N[°º]\s*)?(\d{11})', block_text)
        dni_match = re.search(r'(?:DNI\s*N[°º]\s*)?(\d{8})(?!\d)', block_text)

        if ruc_match:
            b['tipo_persona'] = 'juridica'
            b['ruc'] = ruc_match.group(1)
        elif dni_match:
            b['tipo_persona'] = 'natural'
            b['dni'] = dni_match.group(1)
        else:
            # No RUC/DNI found — infer from category or leave as juridica
            # EPI is almost always Persona Natural; EDI/EPA/others are juridica
            empresa_text = b.get('empresa', b.get('nombre', ''))
            if not empresa_text or len(empresa_text.strip()) < 2:
                continue  # no usable data at all
            b['tipo_persona'] = 'natural' if category == 'EPI' else 'juridica'
            if b['tipo_persona'] == 'juridica':
                b['ruc'] = ''
            else:
                b['dni'] = ''

        empresa_text = b.get('empresa', b.get('nombre', ''))
        company = re.sub(r'\(?\s*(?:RUC|DNI)\s*N[°º]?\s*\d+\)?', '', empresa_text).strip()
        if category == 'EPI':
            # For EPI, treat as natural person name: split into nombres/apellidos
            words = company.split()
            if len(words) >= 2:
                b['nombres'] = ' '.join(words[:-1])
                b['apellidos'] = words[-1]
            elif len(words) == 1:
                b['nombres'] = words[0]
                b['apellidos'] = ''
            else:
                b['nombres'] = ''
                b['apellidos'] = ''
            b['razon_social'] = company
        else:
            company = re.sub(r'\s+', ' ', company).strip()
            b['razon_social'] = company

        region_text = b.get('region', '')
        region_text = re.sub(r'[^A-ZÁÉÍÓÚÑa-záéíóúñ\s]', '', region_text).strip()

        def resolve_region(name):
            if not name or len(name) < 3:
                return ''
            name_u = name.upper()
            for r in sorted(REGIONS, key=len, reverse=True):
                ru = r.upper()
                if name_u == ru or (len(name) >= 4 and ru.startswith(name_u)):
                    return r
                if len(ru) >= 6 and len(name_u) >= 4 and name_u in ru:
                    return r
            return name

        region_text = resolve_region(region_text)
        if not region_text or len(region_text) < 3:
            search_text = (empresa_text + ' ' + block_text).upper()
            for r in sorted(REGIONS, key=len, reverse=True):
                ru = r.upper()
                if re.search(r'\b' + re.escape(ru) + r'\b', search_text):
                    region_text = r
                    company = re.sub(r'\b' + re.escape(r) + r'\b', '', company, flags=re.IGNORECASE).strip()
                    company = re.sub(r'\s+', ' ', company).strip()
                    b['razon_social'] = company
                    break

        # Final cleanup: strip non-alpha leading/trailing chars
        company = re.sub(r'^[\s,;:.\-()\[\]{}<>/&]+|[\s,;:.\-()\[\]{}<>/&]+$', '', company).strip()
        company = re.sub(r'\s+', ' ', company).strip()
        b['razon_social'] = company
        b['region'] = region_text

        proyecto_text = b.get('proyecto', b.get('obra', ''))
        proyecto_text = re.sub(r'\s+', ' ', proyecto_text).strip()
        # Strip leading bleed words that appear from column boundary shifts
        proyecto_text = re.sub(r'^(POS|LA POS|POS LA|PROYECTO|VINCULADA|VINCULADO|OBRA)\s+', '', proyecto_text, flags=re.IGNORECASE).strip()
        b['proyecto'] = proyecto_text

        evento_text = b.get('evento', '')
        evento_text = re.sub(r'\s+', ' ', evento_text).strip()
        if evento_text:
            # Strip leading bleed words from column boundary shifts
            evento_text = re.sub(r'^(TULACIÓN|TULACION|VINCULADO|VINCULADA|INTERNACIONAL|LA|EVENTO)\s+', '', evento_text, flags=re.IGNORECASE).strip()
            b['evento'] = evento_text

        monto_text = b.get('monto', '')
        am_match = re.search(r'S/?\.?\s*([\d\s,]+[.,]\d{2})', block_text)
        if not am_match:
            am_match = re.search(r'(?:S/?\.?\s*)?([\d\s,]+[.,]\d{2})', monto_text)
        if am_match:
            try:
                b['monto'] = _parse_amount_str(am_match.group(1).replace(' ', ''))
            except ValueError:
                b['monto'] = fixed_monto or 0
        else:
            b['monto'] = fixed_monto or 0

        b['razon_social'] = re.sub(r'\s+', ' ', b['razon_social']).strip()
        beneficiaries.append(b)

    return beneficiaries


def parse_fallo(pdf_url, anio, config):
    pdf_name = re.sub(r'[^a-zA-Z0-9]', '_', pdf_url.split('/')[-1])[:80]
    pdf_path = os.path.join(TMP_DIR, pdf_name)
    txt_layout_path = pdf_path + "_layout.txt"
    if not os.path.exists(pdf_path):
        try:
            subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, pdf_url], check=True, timeout=45)
        except Exception as e:
            return None, f"download: {e}"
    try:
        subprocess.run(['pdftotext', '-layout', pdf_path, txt_layout_path], check=True, timeout=30)
        with open(txt_layout_path) as f:
            layout_text = f.read()
    except Exception as e:
        for f in [pdf_path, txt_layout_path]:
            try: os.unlink(f)
            except: pass
        return None, str(e)

    # NFC normalize to handle combining accents (e.g. a + U+0301 → á)
    layout_text = unicodedata.normalize('NFC', layout_text)

    rd_num = extract_rd_num(layout_text)
    fecha = extract_fecha(layout_text)

    a1_match = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO|Artículo\s)', layout_text, re.DOTALL)
    if not a1_match:
        a1_match = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|ART[ÍI]CULO SEGUNDO|Artículo\s|ART[ÍI]CULO\s)', layout_text, re.DOTALL)

    if not a1_match:
        for f in [pdf_path, txt_layout_path]:
            try: os.unlink(f)
            except: pass
        return None, "No ARTÍCULO PRIMERO found"

    a1 = a1_match.group(1)

    modalidad = ''
    mod_match = re.search(r"modalidad\s+de\s+['\"]?([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)['\"]?", a1)
    if mod_match:
        modalidad = mod_match.group(1).strip()

    # Extract fixed per-beneficiary monto from full PDF text (fallback when
    # individual monto extraction fails for some entries).
    fixed_monto = None
    fm = re.search(r'ascendentes\s+a\s+S/?\.?\s*([\d\s,]+[.,]\d{2})', layout_text, re.IGNORECASE)
    if not fm:
        fm = re.search(r'monto\s+de\s+cada\s+est[ií]mulo\s+asciende\s+a\s+S/?\.?\s*([\d\s,]+[.,]\d{2})', layout_text, re.IGNORECASE)
    if not fm:
        fm = re.search(r'monto\s+de\s+cada\s+est[ií]mulo\s+econ[óo]mico\s+corresponder[áa]\s+a\s+S/?\.?\s*([\d\s,]+[.,]\d{2})', layout_text, re.IGNORECASE)
    if not fm:
        fm = re.search(r'S/?\.?\s*([\d\s,]+[.,]\d{2})\s*\([^)]*\)\s*cada\s+uno', layout_text, re.IGNORECASE)
    if not fm:
        fm = re.search(r'asciende\s+a\s+S/?\.?\s*([\d\s,]+[.,]\d{2})', layout_text, re.IGNORECASE)
    if fm:
        try:
            fixed_monto = _parse_amount_str(re.sub(r'\s+', '', fm.group(1)))
        except ValueError:
            fixed_monto = None

    # Preprocess: merge monto values split across lines (e.g. "S/ 20" + "000,00")
    a1 = _merge_split_montos(a1)

    beneficiaries = parse_fallo_beneficiaries(a1, fixed_monto=fixed_monto)

    # Fallback: use pdfminer-based extraction when standard parser fails
    if not beneficiaries:
        beneficiaries = _parse_fallo_block_fallback(pdf_path, layout_text)

    for f in [pdf_path, txt_layout_path]:
        try: os.unlink(f)
        except: pass

    return {
        'rd_num': rd_num,
        'fecha': fecha,
        'modalidad_text': modalidad,
        'url_pdf': pdf_url,
        'beneficiaries': beneficiaries,
    }, None


def _merge_split_montos(a1_text):
    """Merge monto values split across lines in layout text.
    Handles patterns like 'S/ 20' on one line and '000,00' on a later line
    by combining them and placing the full monto on the nearest preceding
    line with empresa text. Does NOT clear the original lines to avoid
    creating blank lines that break block grouping."""
    lines = a1_text.split('\n')
    find_partial = re.compile(r'S/?\.?\s*(\d[\d\s,]*)$')
    cont_digits = re.compile(r'^([\d,]+[.,]\d{2})\s*$')
    emp_re = re.compile(r'[A-ZÁÉÍÓÚÑ]{3,}')

    for i in range(len(lines)):
        if len(lines[i]) <= 117:
            continue
        monto_col = lines[i][117:].strip()
        pm = find_partial.match(monto_col)
        if not pm:
            continue
        if re.search(r'[.,]\d{2}\s*$', monto_col):
            continue
        prefix = pm.group(1)
        for j in range(i + 1, min(i + 15, len(lines))):
            if len(lines[j]) <= 117:
                continue
            nm = lines[j][117:].strip()
            cm = cont_digits.match(nm)
            if cm:
                merged = 'S/ ' + prefix + cm.group(1)
                # Place merged monto on nearest preceding line with empresa text
                target = i
                for k in range(i, -1, -1):
                    emp = lines[k][:53].strip() if len(lines[k]) > 53 else ''
                    if emp_re.match(emp):
                        target = k
                        break
                # Put merged monto on target line, overwriting if needed
                if len(lines[target]) > 117:
                    lines[target] = lines[target][:117] + merged
                else:
                    lines[target] += ' ' * (117 - len(lines[target])) + merged
                # Don't clear original lines to preserve block continuity
                break
    return '\n'.join(lines)


def _parse_fallo_beneficiaries_paragraph(flow_text):
    """Parse beneficiaries from non-layout (flow) PDF text.
    Works by finding the Artículo Primero section, splitting paragraphs
    (separated by blank lines), and grouping 5 consecutive paragraphs
    per entry: persona, region, obra, director, monto."""
    a1_match = re.search(r'Artículo Primero\.-\s*(.*?)(?:Artículo Segundo\.-|Artículo)', flow_text, re.DOTALL)
    if not a1_match:
        a1_match = re.search(r'ART[ÍI]CULO PRIMERO[\.\s\-]+(.*?)(?:ART[ÍI]CULO SEGUNDO)', flow_text, re.DOTALL)
    if not a1_match:
        return []

    a1 = a1_match.group(1)

    # Clean page artifacts
    a1 = re.sub(r'(?s)Esta es una copia auténtica.*?clave:\s*\w+\s*', '', a1)
    a1 = re.sub(r'(?s)\f?\s*DESPACHO.*?ARTES\s*', '', a1)
    a1 = re.sub(r'\s*"Decenio de la Igualdad[^"]*"\s*', '', a1)
    a1 = re.sub(r'\s*"Año de la[^"]*"\s*', '', a1)

    paragraphs = re.split(r'\n\s*\n+', a1)
    paragraphs = [re.sub(r'\s+', ' ', p.strip()).strip() for p in paragraphs if p.strip()]

    if len(paragraphs) <= 5:
        return []

    # Skip header paragraphs (they match known patterns)
    body = []
    for p in paragraphs:
        upper = p.upper()
        if upper in ('PERSONA NATURAL', 'REGIÓN', 'TÍTULO DE LA OBRA',
                     'DIRECTOR(ES/AS ) DE LA OBRA', 'MONTO DEL PREMIO',
                     'PERSONA', 'NATURAL', 'REGIÓN', 'TÍTULO DE LA',
                     'OBRA', 'DIRECTOR(ES/AS', ') DE LA OBRA',
                     'MONTO', 'DEL', 'PREMIO'):
            continue
        if re.match(r'^[A-ZÁÉÍÓÚÑ\s/]+$', upper) and len(p) < 50 and not re.search(r'[a-záéíóú]', p):
            # Could be a header fragment; skip if it looks like column header
            continue
        body.append(p)

    if len(body) < 5:
        return []

    beneficiaries = []
    monto_re = re.compile(r'S/?\.?\s*([\d\s,]+[.,]\d{2})')

    # Try grouping into 5-paragraph entries (persona, region, obra, director, monto)
    for i in range(0, len(body) - 4, 5):
        chunk = body[i:i + 5]
        # Check that the last paragraph has a monto value
        monto_match = monto_re.search(chunk[4]) if len(chunk) == 5 else None
        if not monto_match:
            continue
        # Extract monto
        try:
            monto_float = _parse_amount_str(monto_match.group(1).replace(' ', ''))
        except ValueError:
            monto_float = 0.0

        empresa = chunk[0].rstrip(',')
        empresa = re.sub(r'\s+', ' ', empresa).strip()
        empresa = re.sub(r',\s*(?=[A-ZÁÉÍÓÚÑ])', ' ', empresa)

        ruc_match = re.search(r'(\d{11})', empresa.replace(' ', ''))
        dni_match = re.search(r'(?<!\d)(\d{8})(?!\d)', empresa)
        if not dni_match:
            a1_clean = re.sub(r'\s+', ' ', a1)
            dni_match = re.search(r'\((\d{8})\)', a1_clean)
            if not dni_match:
                dni_match = re.search(r'(?<!\d)(\d{8})(?!\d)', a1_clean)

        if ruc_match:
            tipo_persona = 'juridica'
        elif dni_match:
            tipo_persona = 'natural'
        else:
            tipo_persona = 'juridica'

        company = empresa
        company = re.sub(r'\(?\d{11}\)?', '', company).strip()
        company = re.sub(r'\(?\d{8}\)?', '', company).strip()
        company = re.sub(r'\(DNI\)', '', company, flags=re.IGNORECASE).strip()
        company = re.sub(r'^[\s,;:.\-]+|[\s,;:.\-]+$', '', company)
        company = re.sub(r'\s+', ' ', company).strip()

        nombres = ''
        apellidos = ''
        if tipo_persona == 'natural':
            if ',' in company:
                parts = company.split(',', 1)
                apellidos = parts[0].strip()
                nombres = parts[1].strip()
            else:
                words = company.split()
                if len(words) >= 2:
                    nombres = ' '.join(words[:-1])
                    apellidos = words[-1]
                elif len(words) == 1:
                    nombres = words[0]
                    apellidos = ''
                else:
                    nombres = ''
                    apellidos = ''

        region = chunk[1] if len(chunk) > 1 else ''
        proyecto = chunk[2] if len(chunk) > 2 else ''
        responsable = re.sub(r'\s+', ' ', chunk[3]).strip() if len(chunk) > 3 else ''

        beneficiaries.append({
            'razon_social': company,
            'ruc': ruc_match.group(1) if ruc_match else '',
            'dni': dni_match.group(1) if dni_match else '',
            'tipo_persona': tipo_persona,
            'nombres': nombres,
            'apellidos': apellidos,
            'proyecto': proyecto,
            'responsable': responsable,
            'monto': monto_float,
            'region': region,
        })

    return beneficiaries


def _parse_fallo_block_fallback(pdf_path, layout_text):
    """Parse beneficiaries from PDF using pdfminer for accurate
    position-based table extraction. Used as fallback when the
    standard layout-text parser fails for atypical table formats."""
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextBoxHorizontal, LAParams
    except ImportError:
        return []

    laparams = LAParams(detect_vertical=False, all_texts=True)
    pages = list(extract_pages(pdf_path, laparams=laparams))

    monto_re = re.compile(r'S/?\.?\s*([\d\s,]+[.,]\d{2})')
    beneficiaries = []
    seen_montos = set()

    for pi, page in enumerate(pages):
        boxes = []
        for element in page:
            if isinstance(element, LTTextBoxHorizontal):
                t = element.get_text().strip()
                if t:
                    bbox = element.bbox
                    boxes.append({
                        'text': t,
                        'x0': bbox[0],
                        'x1': bbox[2],
                        'y0': bbox[1],
                        'y1': bbox[3],
                    })

        if not boxes:
            continue

        # Fixed column ranges for standard Fallo table layout
        col_ranges_typed = [
            ('empresa', 80, 200),
            ('region', 200, 260),
            ('proyecto', 260, 360),
            ('responsable', 360, 475),
            ('monto', 475, 530),
        ]

        def pos_col(x0, x1):
            for name, xmin, xmax in col_ranges_typed:
                if x0 >= xmin and x1 <= xmax:
                    return name
            return None

        monto_boxes = []
        for b in boxes:
            col = pos_col(b['x0'], b['x1'])
            if col == 'monto':
                text_clean = b['text'].replace('\n', ' ')
                mm = monto_re.match(text_clean)
                if mm:
                    monto_boxes.append(b)

        for mb in monto_boxes:
            key = (mb['y0'], mb['y1'])
            if key in seen_montos:
                continue
            seen_montos.add(key)

            entry = {}
            for b in boxes:
                if b is mb:
                    continue
                col = pos_col(b['x0'], b['x1'])
                if not col:
                    continue
                y_overlap = min(b['y1'], mb['y1']) - max(b['y0'], mb['y0'])
                if y_overlap > 0:
                    t = b['text'].replace('\n', ' ').strip()
                    if col not in entry:
                        entry[col] = t

            # Use the current monto box's text as the entry's monto
            entry['monto'] = mb['text'].replace('\n', ' ').strip()

            empresa = entry.get('empresa', '')
            if not empresa or len(empresa) < 3:
                continue

            empresa = re.sub(r'\s+', ' ', empresa).strip()
            empresa = re.sub(r',\s*(?=[A-ZÁÉÍÓÚÑ])', ' ', empresa)

            monto_text = entry.get('monto', '')
            mm = monto_re.match(monto_text.replace('\n', ' '))
            if not mm:
                continue
            monto_val = mm.group(1)

            try:
                monto_float = _parse_amount_str(monto_val.replace(' ', '').replace('\n', ''))
            except ValueError:
                monto_float = 0.0

            ruc_match = re.search(r'(\d{11})', empresa.replace(' ', ''))
            dni_match = re.search(r'(?<!\d)(\d{8})(?!\d)', empresa)
            if not dni_match:
                block_text = ' '.join(b['text'] for b in boxes if b.get('text'))
                dni_match = re.search(r'\((\d{8})\)', block_text)
                if not dni_match:
                    dni_match = re.search(r'(?<!\d)(\d{8})(?!\d)', block_text)

            if ruc_match:
                tipo_persona = 'juridica'
            elif dni_match:
                tipo_persona = 'natural'
            else:
                tipo_persona = 'juridica'

            company = empresa
            company = re.sub(r'\(?\d{11}\)?', '', company).strip()
            company = re.sub(r'\(?\d{8}\)?', '', company).strip()
            company = re.sub(r'^[\s,;:.\-]+|[\s,;:.\-]+$', '', company)
            company = re.sub(r'\s+', ' ', company).strip()

            nombres = ''
            apellidos = ''
            if tipo_persona == 'natural':
                if ',' in company:
                    parts = company.split(',', 1)
                    apellidos = parts[0].strip()
                    nombres = parts[1].strip()
                else:
                    words = company.split()
                    if len(words) >= 2:
                        nombres = ' '.join(words[:-1])
                        apellidos = words[-1]
                    elif len(words) == 1:
                        nombres = words[0]
                        apellidos = ''
                    else:
                        nombres = ''
                        apellidos = ''

            beneficiaries.append({
                'razon_social': company,
                'ruc': ruc_match.group(1) if ruc_match else '',
                'dni': dni_match.group(1) if dni_match else '',
                'tipo_persona': tipo_persona,
                'nombres': nombres,
                'apellidos': apellidos,
                'region': entry.get('region', ''),
                'proyecto': entry.get('proyecto', '') or entry.get('evento', ''),
                'responsable': entry.get('responsable', ''),
                'monto': monto_float,
            })

    return beneficiaries


def parse_rd(pdf_url, category, anio, config):
    pdf_name = re.sub(r'[^a-zA-Z0-9]', '_', pdf_url.split('/')[-1])[:80]
    pdf_path = os.path.join(TMP_DIR, pdf_name)
    txt_path = pdf_path + "_layout.txt"
    if not os.path.exists(pdf_path):
        try:
            subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, pdf_url], check=True, timeout=45)
        except Exception as e:
            return None, f"download: {e}"
    try:
        subprocess.run(['pdftotext', '-layout', pdf_path, txt_path], check=True, timeout=30)
        with open(txt_path) as f:
            layout_text = f.read()
    except Exception as e:
        return None, str(e)
    finally:
        for f in [pdf_path, txt_path]:
            try: os.unlink(f)
            except: pass

    # NFC normalize to handle combining accents (e.g. a + U+0301 → á)
    layout_text = unicodedata.normalize('NFC', layout_text)

    rd_num = extract_rd_num(layout_text)
    fecha = extract_fecha(layout_text)

    idx = layout_text.find('RESUELVE:')
    if idx < 0:
        return None, "No RESUELVE section found"

    section = layout_text[idx:]

    a1_match = re.search(
        r'(?:Artículo|ART[ÍI]CULO)\s+(?:Primero|PRIMERO)\.\s*[–\-—]?\s*'
        r'(?:DECLARAR|Decl[áa]rese|DECL[ÁA]RESE|Declarar|Cons[íi]gnese|CONS[ÍI]GNESE|DECLARO)'
        r'.+?(?=\n\s*(?:Artículo|ART[ÍI]CULO)\s+(?:Segundo|SEGUNDO)\.)',
        section, re.DOTALL | re.IGNORECASE
    )
    if not a1_match:
        # Fallback: search for Aritculo Primero .- Declárese with possible page break
        a1_match = re.search(
            r'Artículo Primero[\.\s\-–—]+.+?(?=Artículo Segundo)',
            section, re.DOTALL
        )
    if not a1_match:
        return None, "No ARTÍCULO PRIMERO section found in RESUELVE"

    a1 = a1_match.group(0)
    a1_lines = a1.split('\n')

    # Skip non-award lists: "aptas" (eligible) or "finalistas" (not awarded beneficiaries)
    if re.search(r'(?:como|proyectos)\s+(?:aptas?|finalistas)\s+para', a1, re.IGNORECASE) \
       or re.search(r'finalistas\s+(?:del|para)', a1[:300], re.IGNORECASE):
        return {
            'rd_num': rd_num,
            'fecha': fecha,
            'modalidad_text': '',
            'url_pdf': pdf_url,
            'beneficiaries': [],
        }, None

    # Extract fixed per-beneficiary monto from full PDF text (fallback)
    fixed_monto = None
    fm = re.search(r'ascendentes\s+a\s+S/?\.?\s*([\d\s,]+[.,]\d{2})', layout_text, re.IGNORECASE)
    if not fm:
        fm = re.search(r'monto\s+de\s+cada\s+est[ií]mulo\s+asciende\s+a\s+S/?\.?\s*([\d\s,]+[.,]\d{2})', layout_text, re.IGNORECASE)
    if not fm:
        fm = re.search(r'monto\s+de\s+cada\s+est[ií]mulo\s+econ[óo]mico\s+corresponder[áa]\s+a\s+S/?\.?\s*([\d\s,]+[.,]\d{2})', layout_text, re.IGNORECASE)
    if not fm:
        fm = re.search(r'S/?\.?\s*([\d\s,]+[.,]\d{2})\s*\([^)]*\)\s*cada\s+uno', layout_text, re.IGNORECASE)
    if fm:
        try:
            fixed_monto = _parse_amount_str(re.sub(r'\s+', '', fm.group(1)))
        except ValueError:
            fixed_monto = None

    # Determine format: single vs multi-beneficiary
    single_cols_config = config.get('rd_single_cols', {}).get(category)
    if single_cols_config:
        # Single-entry RD format: detect columns dynamically from table header
        # Use detect_table_columns to compute column boundaries from actual PDF layout
        dynamic_cols = detect_table_columns(a1_lines, extra_keywords=[category])
        if not dynamic_cols or len(dynamic_cols) < 3:
            dynamic_cols = single_cols_config  # fallback to hard-coded
        beneficiaries = parse_rd_beneficiaries(a1_lines, dynamic_cols, category, fixed_monto=fixed_monto)
    else:
        # Use table-based (FalloFinal-style) parsing for multi-beneficiary RDs
        beneficiaries = parse_fallo_beneficiaries(a1, extra_header_kws=[category], fixed_monto=fixed_monto)

    modalidad = ''
    mod_match = re.search(r"modalidad\s+de\s+['\"]?([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)['\"]?", a1)
    if mod_match:
        modalidad = mod_match.group(1).strip()

    return {
        'rd_num': rd_num,
        'fecha': fecha,
        'modalidad_text': modalidad,
        'url_pdf': pdf_url,
        'beneficiaries': beneficiaries,
    }, None


def is_valid_person_name(name):
    """Check if a string looks like a real person name (not OCR garbage)."""
    name = name.strip()
    # Too short
    if len(name) < 6 or len(name) > 60:
        return False
    # Must have at least 2 words
    words = name.split()
    if len(words) < 2:
        return False
    # Reject if all-uppercase with > 2 words (OCR artifact / boilerplate)
    if len(words) > 2 and name == name.upper():
        return False
    # Reject if contains keywords indicating non-person text
    reject_keywords = [
        'copia auténtica', 'documento electrónico', 'archivado por',
        'ministerio de cultura', 'artículo', 'disposición complementaria',
        'despacho', 'viceministerial', 'patrimonio cultural',
        'industrias culturales', 'dirección general', 'resolución directoral',
        'expediente', 'sello digital', 'fecha de descarga',
        'sistema de gestión documentaria', 'código de verificación',
    ]
    name_lower = name.lower()
    for kw in reject_keywords:
        if kw in name_lower:
            return False
    return True


def parse_jurado_text(text, pdf_url=''):
    """Extract jurado members from acta_evaluacion text (OCR or native)."""
    miembros = []

    def add_miembro(nombre, cargo):
        nombre = re.sub(r'\s+', ' ', nombre).strip()
        nombre = re.sub(r'\s*\([^)]*\)\s*', '', nombre).strip()
        if is_valid_person_name(nombre):
            miembros.append((nombre, cargo))

    # Normalise line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Flatten: collapse intra-line wrapping for pattern 1 (nosotros)
    flat = re.sub(r'(?<!\.)\n(?!\n)', ' ', text)
    flat = re.sub(r'\s+', ' ', flat)

    # ── Pattern 1: "nosotros: Name1, Name2 y Name3; designados por …" (Acta de Evaluación) ──
    m = re.search(
        r'nosotros\s*:\s*(.+?)\s*(?:;)?\s*designados?\s+por\s+(?:[Rr]esoluci[oó]n\s+)?[Dd]irectoral',
        flat, re.IGNORECASE
    )
    if m:
        names_part = m.group(1).strip()
        # Remove common OCR noise
        names_part = re.sub(r'[/*\"#]+\s*\d*\s*', ' ', names_part)
        parts = re.split(r'\s+y\s+', names_part, maxsplit=1)
        for p in parts:
            for n in re.split(r'\s*,\s*', p):
                n = n.strip().rstrip(';.,')
                if n:
                    add_miembro(n, 'miembro del Jurado')
        if miembros:
            return miembros

    # ── Pattern 3: "… citada resolución: Name, DNI, role; Name, DNI, role" (Acta multianual) ──
    # Names appear after the last colon following a "designados por el artículo" clause
    # Each entry is semicolon-separated: "Name, identificado con DNI N° XXXX, role"
    res_colon = re.search(
        r'(?:citada\s+resoluci[óo]n|designados?\s+por\s+el\s+art[íi]culo)\s*:\s*(.+)',
        flat, re.IGNORECASE
    )
    if res_colon:
        after = res_colon.group(1).strip()
        # Split on semicolons
        entries = re.split(r'\s*;\s*', after)
        for entry in entries:
            entry = entry.strip().rstrip('.')
            if not entry or len(entry) < 10:
                continue
            # Remove "identificado con DNI N° ... / DNI N° ... / identificado con ..."
            cleaned = re.sub(r',?\s*identificad[oa]\s+con\s+DNI\s+N[°º]\s*\d+', '', entry, flags=re.IGNORECASE)
            cleaned = re.sub(r',?\s*DNI\s+N[°º]\s*\d+', '', cleaned, flags=re.IGNORECASE)
            # Split on first comma to get name
            parts = cleaned.split(',', 1)
            name = parts[0].strip().rstrip(';.,')
            role = parts[1].strip().rstrip(';.,') if len(parts) >= 2 else 'miembro del Jurado'
            add_miembro(name, role)
        if miembros:
            return miembros

    # ── Pattern 2: "ARTÍCULO PRIMERO … DESIGNAR/Desígnese" (RD Designación) ──
    # Find the article block in original line-oriented text
    lines = text.split('\n')
    # Concatenate until we find Artículo Segundo or end
    art_lines = []
    in_art = False
    for line in lines:
        if re.search(r'ART[ÍI]CULO\s+PRIMERO', line, re.IGNORECASE) and re.search(r'(?:DESIGNAR|DESÍGNESE|designar|desígnese)', line, re.IGNORECASE):
            in_art = True
        if in_art:
            if re.search(r'ART[ÍI]CULO\s+SEGUNDO', line, re.IGNORECASE):
                break
            art_lines.append(line)
    block = '\n'.join(art_lines)

    if block.strip():
        # Find the colon after "siguientes personas"
        colon_match = re.search(r'siguientes?\s+personas?\s*:', block, re.IGNORECASE)
        if colon_match:
            after = block[colon_match.end():]
            # Join continuation lines: non-bullet lines that start with spaces
            after_lines = after.split('\n')
            joined = []
            for line in after_lines:
                is_continuation = (line.startswith(' ') or line.startswith('\t')) and not re.match(r'^\s*[—–\-−•*\d.]', line)
                if joined and is_continuation:
                    joined[-1] += ' ' + line.strip()
                else:
                    joined.append(line.strip())
            for line in joined:
                line = line.strip()
                # Remove bullet markers: -, –, −, •, *
                line = re.sub(r'^[—–\-−•*\d.]+', '', line).strip()
                # Remove trailing punctuation
                line = line.rstrip(';.,')
                if not line or len(line) < 10:
                    continue
                if re.search(r'ART[ÍI]CULO', line, re.IGNORECASE):
                    break
                # Must start with uppercase letter
                if not re.match(r'^[A-ZÁÉÍÓÚÑ]', line):
                    continue
                # Split on first comma (name, role)
                parts = line.split(',', 1)
                name = parts[0].strip()
                role = parts[1].strip().rstrip(';.,') if len(parts) >= 2 else 'miembro del Jurado'
                # Remove trailing 'y' connector
                role = re.sub(r'\s+y\s*$', '', role).strip()
                add_miembro(name, role)

    return miembros

def parse_jurado(url, code, anio, config):
    """Download and parse a jurado PDF, returning {beneficiaries: [{nombre:, apellidos:, cargo:}]}."""
    fname = urllib.parse.unquote(url.split('/')[-1])
    local = os.path.join(TMP_DIR, fname)
    txt_path = local + '.txt'

    # Use cached PDF if available
    if not os.path.exists(local):
        try:
            subprocess.run(['curl', '-sLk', '--max-time', '15', '--connect-timeout', '10', '-o', local, url], check=True, timeout=25)
        except Exception as e:
            return None, f"download: {e}"

    # Try pdftotext first
    subprocess.run(['pdftotext', '-layout', local, txt_path],
                   capture_output=True, timeout=30)
    if os.path.exists(txt_path):
        with open(txt_path) as f:
            text = f.read()
    else:
        text = ''

    ocr_used = False
    if len(text) < 100:
        # Fall back to OCR
        env = os.environ.copy()
        env['TESSDATA_PREFIX'] = os.path.expanduser('~/.local/share/tessdata')
        try:
            subprocess.run(['pdftoppm', '-f', '1', '-l', '2', '-png', '-r', '200',
                           local, local + '_page'], capture_output=True, timeout=60)
            for i in range(1, 3):
                page_img = f'{local}_page-{i}.png'
                if not os.path.exists(page_img):
                    continue
                page_txt = f'{local}_page{i}.txt'
                subprocess.run(['tesseract', page_img, page_txt.replace('.txt', ''),
                               '-l', 'spa'], capture_output=True, env=env, timeout=60)
                if os.path.exists(page_txt):
                    with open(page_txt) as f:
                        text += f.read() + '\n'
            ocr_used = True
        except Exception as e:
            pass

    if not text.strip():
        return None, "no text extracted"

    miembros = parse_jurado_text(text, pdf_url=url)
    if not miembros:
        return None, "no jurado members found"

    # Build structured result
    result = {
        'url_pdf': url,
        'fecha': '',
        'beneficiaries': []
    }
    seen = set()
    for name, cargo in miembros:
        key = name.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        nombres, apellidos = split_name(name)
        result['beneficiaries'].append({
            'tipo_persona': 'natural',
            'nombres': nombres,
            'apellidos': apellidos,
            'cargo': cargo,
        })

    return result, None if result['beneficiaries'] else ("no beneficiaries", None)

def generate_jurado_sql(result, concurso_codigo, modalidad_nombre, convocatoria_id):
    """Generate SQL to insert jurado members."""
    ca_id = get_code(concurso_codigo, convocatoria_id)
    if not ca_id:
        return f"\n-- ERROR: concurso {concurso_codigo} not found for convocatoria_id {convocatoria_id}\n"

    url_pdf = result.get('url_pdf', '')
    mod_id = get_modalidad(ca_id, modalidad_nombre) if modalidad_nombre else None

    sql = f"\n-- Jurado para {concurso_codigo} convocatoria {convocatoria_id}\n"
    for b in result.get('beneficiaries', []):
        nombres = b.get('nombres', '')
        apellidos = b.get('apellidos', '')
        cargo = b.get('cargo', 'miembro del Jurado')

        if not nombres or len(nombres) < 1:
            continue

        # Insert persona (natural, sin DNI)
        sql += f"""INSERT INTO persona (tipo, nombres, apellidos, dni)
SELECT 'natural', {q(nombres)}, {q(apellidos)}, ''
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND nombres={q(nombres)} AND apellidos={q(apellidos)} AND (dni IS NULL OR dni = ''));\n"""

        # Insert jurado
        mod_col = ", modalidad_id" if mod_id else ""
        mod_val = f", {mod_id}" if mod_id else ""
        sql += f"""INSERT OR IGNORE INTO jurado (concurso_anual_id{mod_col}, persona_id, cargo)
SELECT {ca_id}{mod_val}, p.id, {q(cargo)}
FROM persona p
WHERE p.tipo='natural' AND p.nombres={q(nombres)} AND p.apellidos={q(apellidos)} AND (p.dni IS NULL OR p.dni = '');\n"""

    return sql

def generate_sql(result, concurso_codigo, modalidad_nombre, convocatoria_id, resolucion_tipo='fallo_final'):
    ca_id = get_code(concurso_codigo, convocatoria_id)
    if not ca_id:
        return f"\n-- ERROR: concurso {concurso_codigo} not found for convocatoria_id {convocatoria_id}\n"

    url_pdf = result.get('url_pdf', '')
    rd_num = result.get('rd_num', '')
    fecha = result.get('fecha', '')

    conv_id = convocatoria_id
    sql = f"\n-- Convocatoria {convocatoria_id} {concurso_codigo}/{modalidad_nombre}: {rd_num}\n"
    sql += f"""INSERT INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf)
SELECT {ca_id}, {q(rd_num)}, {q(fecha)}, {q(resolucion_tipo)}, {q(url_pdf)}
WHERE NOT EXISTS (SELECT 1 FROM resolucion WHERE url_pdf = {q(url_pdf)});\n"""

    mod_id = get_modalidad(ca_id, modalidad_nombre) if modalidad_nombre else None

    for i, b in enumerate(result.get('beneficiaries', [])):
        monto = b.get('monto', 0)
        if monto == 0:
            sql += f"\n-- SKIP {i}: monto=0 (parsing artifact)\n"
            continue
        tipo_persona = b.get('tipo_persona', 'juridica')
        ruc = b.get('ruc', '')
        dni = b.get('dni', '')
        razon_social = b.get('razon_social', '')
        nombres = b.get('nombres', '')
        apellidos = b.get('apellidos', '')
        proyecto = b.get('proyecto', '')
        region = b.get('region', '')
        # monto already checked above (monto=0 entries are skipped)
        ident_extra = ''

        # Heuristic: reclasificar jurídicas sin RUC que parecen personas naturales
        if tipo_persona == 'juridica' and not ruc and not dni:
            legal_suffixes = {'S.A.C.', 'E.I.R.L.', 'S.R.L.', 'S.A.', 'SAC', 'EIRL', 'SRL',
                              'SOCIEDAD', 'STUDIO', 'PRODUCCIONES', 'PRODUCTORA',
                              'FILM', 'CINE', 'MEDIA', 'LABORATORIO', 'ASOCIACION',
                              'ASOCIACIÓN', 'COMUNICACION', 'COMUNICACIÓN'}
            has_legal_suffix = any(s.upper() in razon_social.upper() for s in legal_suffixes)
            looks_like_natural = False
            if ',' in razon_social and not has_legal_suffix:
                looks_like_natural = True
            elif not has_legal_suffix and razon_social:
                words = razon_social.split()
                if len(words) <= 4 and len(razon_social) >= 5 and not re.search(r'\d', razon_social):
                    looks_like_natural = True
            if looks_like_natural:
                tipo_persona = 'natural'
                if ',' in razon_social:
                    parts = razon_social.split(',', 1)
                    apellidos = parts[0].strip()
                    nombres = parts[1].strip()
                else:
                    words = razon_social.split()
                    if len(words) >= 2:
                        nombres = ' '.join(words[:-1])
                        apellidos = words[-1]
                    elif len(words) == 1:
                        nombres = words[0]
                        apellidos = ''
                    else:
                        nombres = ''
                        apellidos = ''

        if tipo_persona == 'juridica':
            if ruc:
                sql += f"""INSERT INTO persona (tipo, razon_social, ruc, region)
SELECT 'juridica', {q(razon_social)}, {q(ruc)}, {q(region)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='juridica' AND ruc={q(ruc)});\n"""
                ident_col = 'ruc'
                ident_val = ruc
            else:
                # RUC-less juridical (older FalloFinals): use razon_social + empty ruc for dedup
                # Use empty string '' (NOT NULL) to satisfy CHECK constraint
                if not razon_social or len(razon_social) < 3:
                    sql += f"\n-- SKIP {i}: invalid juridica ({razon_social})\n"
                    continue
                sql += f"""INSERT INTO persona (tipo, razon_social, ruc, region)
SELECT 'juridica', {q(razon_social)}, '', {q(region)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='juridica' AND razon_social={q(razon_social)} AND (ruc IS NULL OR ruc = ''));\n"""
                ident_col = 'razon_social'
                ident_val = razon_social
                # Need personas joined by razon_social (with NULL or empty ruc)
                ident_extra = ' AND (ruc IS NULL OR ruc = \'\')'
        else:
            if not dni:
                # DNI-less natural (older EPI RDs): use nombres+apellidos for dedup
                if not nombres or len(nombres) < 2:
                    sql += f"\n-- SKIP {i}: invalid natural ({nombres} {apellidos})\n"
                    continue
                sql += f"""INSERT INTO persona (tipo, nombres, apellidos, dni, region)
SELECT 'natural', {q(nombres)}, {q(apellidos)}, '', {q(region)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND nombres={q(nombres)} AND apellidos={q(apellidos)} AND (dni IS NULL OR dni = ''));\n"""
                ident_col = 'nombres'
                ident_val = nombres
                ident_extra = f' AND apellidos={q(apellidos)} AND (dni IS NULL OR dni = \'\')'
            else:
                sql += f"""INSERT INTO persona (tipo, nombres, apellidos, dni, region)
SELECT 'natural', {q(nombres)}, {q(apellidos)}, {q(dni)}, {q(region)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND dni={q(dni)});\n"""
                ident_col = 'dni'
                ident_val = dni
                ident_extra = ''

        mod_val = f", {mod_id}" if mod_id else ""
        mod_col = ", modalidad_id" if mod_id else ""
        cat_col = ", categoria" if b.get('categoria') else ""
        cat_val = f", {q(b['categoria'])}" if b.get('categoria') else ""

        if proyecto:
            sql += f"""INSERT OR IGNORE INTO obra (titulo) VALUES ({q(proyecto)});\n"""
            sql += f"""INSERT INTO proyecto (concurso_anual_id{mod_col}, persona_beneficiaria_id, obra_id, monto_otorgado{cat_col})
SELECT {ca_id}{mod_val},
       (SELECT id FROM persona WHERE {ident_col}={q(ident_val)}{ident_extra} LIMIT 1),
       (SELECT id FROM obra WHERE titulo = {q(proyecto)} LIMIT 1),
       {monto}{cat_val}
WHERE NOT EXISTS (SELECT 1 FROM proyecto WHERE concurso_anual_id={ca_id} AND persona_beneficiaria_id=(SELECT id FROM persona WHERE {ident_col}={q(ident_val)}{ident_extra} LIMIT 1));\n"""
        else:
            sql += f"""INSERT INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado{cat_col})
SELECT {ca_id},
       (SELECT id FROM persona WHERE {ident_col}={q(ident_val)}{ident_extra} LIMIT 1),
       NULL,
       {monto}{cat_val}
WHERE NOT EXISTS (SELECT 1 FROM proyecto WHERE concurso_anual_id={ca_id} AND persona_beneficiaria_id=(SELECT id FROM persona WHERE {ident_col}={q(ident_val)}{ident_extra} LIMIT 1));\n"""

        sql += f"""INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id)
SELECT po.id, r.id FROM proyecto po, resolucion r
WHERE po.concurso_anual_id = {ca_id} AND po.persona_beneficiaria_id = (SELECT id FROM persona WHERE {ident_col}={q(ident_val)}{ident_extra})
  AND r.url_pdf = {q(url_pdf)};\n"""

        # Insert responsable as proyecto_integrante for juridica beneficiaries
        # Try both 'responsable' and 'director' column names
        responsable = b.get('responsable', b.get('director', ''))
        if tipo_persona == 'juridica' and responsable:
            dni_resp_match = re.search(r'(\d{8})', responsable)
            # Clean responsable name: remove DNI, parens, "DNI N°" / "DNI" labels
            resp_name = re.sub(r'\d{8}', '', responsable)
            resp_name = re.sub(r'[()]', '', resp_name)
            resp_name = re.sub(r'DNI\s*N?[°º]?\s*', '', resp_name, flags=re.IGNORECASE)
            resp_name = resp_name.strip().rstrip(',')
            resp_name = re.sub(r'\s+', ' ', resp_name).strip()
            # Strip trailing marginal letter(s) likely from column boundary bleed
            resp_name = re.sub(r'\s+[A-Z]{1,2}$', '', resp_name).strip()

            if dni_resp_match:
                dni_resp = dni_resp_match.group(1)
                if ',' in resp_name:
                    parts = resp_name.split(',', 1)
                    resp_apellidos = parts[0].strip()
                    resp_nombres = parts[1].strip()
                else:
                    resp_nombres = resp_name
                    resp_apellidos = ''

                sql += f"""INSERT INTO persona (tipo, nombres, apellidos, dni)
SELECT 'natural', {q(resp_nombres)}, {q(resp_apellidos)}, {q(dni_resp)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND dni={q(dni_resp)});\n"""

                sql += f"""INSERT OR IGNORE INTO proyecto_integrante (proyecto_id, persona_id, rol)
SELECT po.id, p.id, 'responsable'
FROM proyecto po, persona p
WHERE po.concurso_anual_id = {ca_id}
  AND po.persona_beneficiaria_id = (SELECT id FROM persona WHERE {ident_col}={q(ident_val)}{ident_extra})
  AND p.dni = {q(dni_resp)};\n"""
            elif resp_name and len(resp_name) >= 5:
                # Responsable sin DNI: insertar igual, dedup por nombre
                words = resp_name.split()
                if ',' in resp_name:
                    parts = resp_name.split(',', 1)
                    resp_apellidos = parts[0].strip()
                    resp_nombres = parts[1].strip()
                elif len(words) >= 2:
                    resp_nombres = ' '.join(words[:-1])
                    resp_apellidos = words[-1]
                else:
                    resp_nombres = resp_name
                    resp_apellidos = ''
                sql += f"""INSERT INTO persona (tipo, nombres, apellidos, dni)
SELECT 'natural', {q(resp_nombres)}, {q(resp_apellidos)}, ''
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND nombres={q(resp_nombres)} AND apellidos={q(resp_apellidos)} AND (dni IS NULL OR dni = ''));\n"""
                sql += f"""INSERT OR IGNORE INTO proyecto_integrante (proyecto_id, persona_id, rol)
SELECT po.id, p.id, 'responsable'
FROM proyecto po, persona p
WHERE po.concurso_anual_id = {ca_id}
  AND po.persona_beneficiaria_id = (SELECT id FROM persona WHERE {ident_col}={q(ident_val)}{ident_extra})
  AND p.nombres = {q(resp_nombres)} AND (p.apellidos = {q(resp_apellidos)} OR (p.apellidos IS NULL AND {q(resp_apellidos)} = ''))
  AND (p.dni IS NULL OR p.dni = '');\n"""

        # ---- Evento internacional (EPI) ----
        evento_text = b.get('evento', '')
        if evento_text:
            # Parse "Event Name (Country)" or "Event Name - Description (Country)"
            pais = ''
            nombre_evento = evento_text
            country_match = re.search(r'\(([^)]+)\)\s*$', evento_text)
            if country_match:
                pais = country_match.group(1).strip()
                nombre_evento = evento_text[:country_match.start()].strip()
            # Further clean: remove trailing dashes, extra spaces
            nombre_evento = re.sub(r'\s*[–\-—]\s*$', '', nombre_evento).strip()
            if nombre_evento and pais:
                sql += f"""INSERT INTO evento_internacional (nombre, pais, modalidad, tipo_evento)
SELECT {q(nombre_evento)}, {q(pais)}, 'presencial', 'festival'
WHERE NOT EXISTS (SELECT 1 FROM evento_internacional WHERE nombre={q(nombre_evento)} AND pais={q(pais)});\n"""
                sql += f"""INSERT OR IGNORE INTO proyecto_evento (proyecto_id, evento_internacional_id)
SELECT po.id, e.id
FROM proyecto po, evento_internacional e
WHERE po.concurso_anual_id = {ca_id}
  AND po.persona_beneficiaria_id = (SELECT id FROM persona WHERE {ident_col}={q(ident_val)}{ident_extra})
  AND e.nombre = {q(nombre_evento)} AND e.pais = {q(pais)};\n"""

    return sql

def match_filename(url, mapping):
    """Extract filename from URL and map to (code, modalidad) using year-specific mapping."""
    fname = urllib.parse.unquote(url.split('/')[-1])
    return mapping.get(fname, (None, None))

def is_rd_pdf(url):
    fname = urllib.parse.unquote(url.split('/')[-1])
    return bool(re.search(r'-RD\d+', fname))

def main():
    dry_run = '--run' not in sys.argv
    jurado_only = '--jurado-only' in sys.argv
    skip_jurado = '--skip-jurado' in sys.argv
    debug_rd = False

    sql = """-- DAFO beneficiaries (all years)
BEGIN TRANSACTION;

"""

    if jurado_only:
        sql += """-- Clearing jurado table before re-inserting
DELETE FROM jurado WHERE concurso_anual_id IN (SELECT id FROM concurso_anual WHERE convocatoria_id <= 6);

"""
    else:
        sql += """-- Clear proyecto-level data for years 2019-2024 (convocatoria_id 1-6)
-- before re-inserting. Seed data for 2025 (convocatoria_id 7) preserved.
DELETE FROM proyecto_integrante WHERE proyecto_id IN (SELECT id FROM proyecto WHERE concurso_anual_id IN (SELECT id FROM concurso_anual WHERE convocatoria_id <= 6));
DELETE FROM proyecto_evento WHERE proyecto_id IN (SELECT id FROM proyecto WHERE concurso_anual_id IN (SELECT id FROM concurso_anual WHERE convocatoria_id <= 6));
DELETE FROM proyecto_resolucion WHERE proyecto_id IN (SELECT id FROM proyecto WHERE concurso_anual_id IN (SELECT id FROM concurso_anual WHERE convocatoria_id <= 6));
DELETE FROM proyecto WHERE concurso_anual_id IN (SELECT id FROM concurso_anual WHERE convocatoria_id <= 6);
DELETE FROM resolucion WHERE concurso_anual_id IN (SELECT id FROM concurso_anual WHERE convocatoria_id <= 6);

"""

    total = 0
    errors = 0
    processed_urls = set()

    for anio in sorted(YEAR_CONFIG.keys(), reverse=True):
        config = YEAR_CONFIG[anio]
        convocatoria_id = config['convocatoria_id']
        fallo_mapping = config.get('fallo_final_mapping', {})
        rd_single_cols = config.get('rd_single_cols', {})

        if anio not in PDF_MAP:
            print(f"\n--- Year {anio}: no PDFs in map ---", file=sys.stderr)
            continue

        year_pdfs = PDF_MAP[anio]

        print(f"\n{'='*60}", file=sys.stderr)
        print(f"=== Processing year {anio} (convocatoria_id={convocatoria_id}) ===", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        if not jurado_only:
            # ---- FalloFinal PDFs ----
            fallos = []
            for code, info in year_pdfs.items():
                for p in info['pdfs']:
                    if p['category'] in ('fallo_final',):
                        db_code, modalidad = match_filename(p['url'], fallo_mapping)
                        if db_code and p['url'] not in processed_urls:
                            fallos.append((p['url'], db_code, modalidad))
                            processed_urls.add(p['url'])

            print(f"Found {len(fallos)} unique FalloFinal PDFs for {anio}", file=sys.stderr)

            for url, db_code, modalidad in sorted(fallos):
                fname = urllib.parse.unquote(url.split('/')[-1])
                print(f"\nProcessing {fname} -> {db_code}/{modalidad}...", file=sys.stderr)
                result, err = parse_fallo(url, anio, config)
                if result and result.get('beneficiaries'):
                    sql += generate_sql(result, db_code, modalidad, convocatoria_id, resolucion_tipo='fallo_final')
                    n = len(result['beneficiaries'])
                    total += n
                    print(f"  OK: {n} beneficiaries", file=sys.stderr)
                elif result:
                    print(f"  No beneficiaries found in PDF", file=sys.stderr)
                else:
                    print(f"  ERROR: {err}", file=sys.stderr)
                    errors += 1

        # ---- Jurado (acta_evaluacion / acta PDFs) ----
        if not skip_jurado:
            jurado_count = 0
            for code, info in year_pdfs.items():
                for p in info['pdfs']:
                    if p['category'] not in ('acta_evaluacion', 'acta'):
                        continue
                    if p['url'] in processed_urls:
                        continue
                    # Try to extract modalidad from filename if present
                    modalidad = ''
                    fname = urllib.parse.unquote(p['url'].split('/')[-1])
                    for known_map_key, (mapped_code, mapped_modalidad) in fallo_mapping.items():
                        if mapped_code == code and fname.startswith(known_map_key[:10]):
                            modalidad = mapped_modalidad
                            break

                    processed_urls.add(p['url'])
                    print(f"\nProcessing jurado {fname} -> {code}...", file=sys.stderr)
                    result, err = parse_jurado(p['url'], code, anio, config)
                    if result and result.get('beneficiaries'):
                        sql += generate_jurado_sql(result, code, modalidad, convocatoria_id)
                        n = len(result['beneficiaries'])
                        jurado_count += n
                        print(f"  OK: {n} miembros de jurado", file=sys.stderr)
                    elif result:
                        print(f"  No jurado members found", file=sys.stderr)
                    else:
                        print(f"  SKIP: {err}", file=sys.stderr)

            print(f"Total jurado members for {anio}: {jurado_count}", file=sys.stderr)

        if jurado_only:
            # Skip RD sections when running jurado-only
            continue

        # ---- Single-entry RD PDFs (EDI, EPA, EPI) ----
        for code in rd_single_cols:
            if code not in year_pdfs:
                continue
            if debug_rd:
                print(f"  {code}: scanning {len(year_pdfs[code]['pdfs'])} PDFs", file=sys.stderr)
            for p in year_pdfs[code]['pdfs']:
                if p['category'] == 'other' and is_rd_pdf(p['url']) and p['url'] not in processed_urls:
                    fname = urllib.parse.unquote(p['url'].split('/')[-1])
                    print(f"\nProcessing {fname} -> {code} (single RD)...", file=sys.stderr)
                    result, err = parse_rd(p['url'], code, anio, config)
                    if result and result.get('beneficiaries'):
                        sql += generate_sql(result, code, '', convocatoria_id, resolucion_tipo='resolucion_beneficiario')
                        n = len(result['beneficiaries'])
                        total += n
                        processed_urls.add(p['url'])
                        print(f"  OK: {n} beneficiaries", file=sys.stderr)
                    elif result:
                        print(f"  No beneficiaries found in RD", file=sys.stderr)
                    else:
                        print(f"  ERROR: {err}", file=sys.stderr)
                        errors += 1

        # ---- Multi-beneficiary RD PDFs (all other codes not in rd_single_cols) ----
        for code, info in year_pdfs.items():
            if code in rd_single_cols:
                continue
            for p in info['pdfs']:
                if p['category'] == 'other' and is_rd_pdf(p['url']) and p['url'] not in processed_urls:
                    fname = urllib.parse.unquote(p['url'].split('/')[-1])
                    print(f"\nProcessing {fname} -> {code} (multi RD)...", file=sys.stderr)
                    result, err = parse_rd(p['url'], code, anio, config)
                    if result and result.get('beneficiaries'):
                        sql += generate_sql(result, code, '', convocatoria_id, resolucion_tipo='resolucion_beneficiario')
                        n = len(result['beneficiaries'])
                        total += n
                        processed_urls.add(p['url'])
                        print(f"  OK: {n} beneficiaries", file=sys.stderr)
                    elif result:
                        print(f"  No beneficiaries found in RD", file=sys.stderr)
                    else:
                        print(f"  ERROR: {err}", file=sys.stderr)
                        errors += 1

    # ---- Summary ----
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Total: {total} beneficiaries across all years", file=sys.stderr)
    print(f"Errors: {errors}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    sql += "\nCOMMIT;\n"

    if dry_run:
        print(sql)
    else:
        print(f"Writing to DB...", file=sys.stderr)
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(sql)
        print("Done.", file=sys.stderr)

if __name__ == '__main__':
    main()
