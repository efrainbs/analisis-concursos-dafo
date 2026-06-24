#!/usr/bin/env python3
"""
Extract beneficiary data from DAFO resolution PDFs.
Outputs SQL INSERT statements for the concursos_dafo.db database.

Usage:
  python3 extract_beneficiaries.py              # dry run (prints SQL)
  python3 extract_beneficiaries.py --run        # loads into DB
"""

import subprocess, re, sys, os, sqlite3

from dafo_common import (
    _parse_amount_str, extract_rd_num, extract_fecha, q,
    get_concurso_anual_id, get_modalidad_id,
    REGIONS, DB_PATH, TMP_DIR
)

os.makedirs(TMP_DIR, exist_ok=True)

PDF_BASE = "https://estimuloseconomicos.cultura.gob.pe"
DOC4_BASE = f"{PDF_BASE}/sites/default/files/concursos/archivos/doc-4/"

CONCURSO_IDS = {}

def get_concurso_id(codigo):
    if codigo in CONCURSO_IDS:
        return CONCURSO_IDS[codigo]
    val = get_concurso_anual_id(codigo, anio=2025)
    if val:
        CONCURSO_IDS[codigo] = val
    return val

def download_and_extract(url):
    safe = re.sub(r'[^a-zA-Z0-9]', '_', url.split('/')[-1])[:100]
    pdf_path = os.path.join(TMP_DIR, safe)
    txt_path = pdf_path + '.txt'
    layout_path = pdf_path + '_layout.txt'
    if os.path.exists(txt_path) and os.path.exists(layout_path):
        with open(txt_path, 'r', errors='replace') as f:
            flow_text = f.read()
        with open(layout_path, 'r', errors='replace') as f:
            layout_text = f.read()
        return flow_text, layout_text
    subprocess.run(['curl', '-sLk', '-o', pdf_path, url], check=True, timeout=30)
    subprocess.run(['pdftotext', pdf_path, txt_path], check=True, timeout=30)
    subprocess.run(['pdftotext', '-layout', pdf_path, layout_path], check=True, timeout=30)
    with open(txt_path, 'r', errors='replace') as f:
        flow_text = f.read()
    with open(layout_path, 'r', errors='replace') as f:
        layout_text = f.read()
    return flow_text, layout_text

def extract_region(text_block):
    upper = text_block.upper()
    for r in REGIONS:
        if r in upper:
            return r.capitalize() if r not in ['JUNÍN','JUNIN'] else ('Junín' if r[0]=='J' else r)
    return ''

STOP_WORDS_NATURAL = {
    'PERSONA', 'NATURAL', '(DNI)', 'DNI', 'REGIÓN', 'REGION',
    'PROYECTO', 'OBRA', 'VINCULADO', 'VINCULADA',
    'PROYECTO', 'EVENTO', 'INTERNACIONAL',
    'MONTO', 'ESTÍMULO', 'ESTÍMUL',
    'CARNET', 'EXTRANJERÍA', 'EXTRANJERIA',
}

COUNTRIES = ['Argentina','Bolivia','Brasil','Canadá','Chile','Colombia','Costa Rica',
             'Cuba','Ecuador','España','Estados Unidos','Francia','México','Panamá',
             'Paraguay','Perú','Portugal','Reino Unido','República Dominicana','Suiza',
             'Uruguay','Venezuela','Alemania','Italia','Países Bajos']

HEADERS = {'REGIÓN','REGION','EVENTO INTERNACIONAL','VINCULADO A LA','PROYECTO',
           'MONTO DEL','ESTÍMULO','OBRA VINCULADA','A LA','PROYECTO VINCULADO'}


def parse_epi_like(text, pdf_url):
    """Parse individual resolution PDFs (EPI, EDI, EPA)."""
    
    rd_num = extract_rd_num(text)
    fecha = extract_fecha(text)
    
    a1_match = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|Artículo\s)', text, re.DOTALL)
    if not a1_match:
        return None
    a1 = a1_match.group(1)
    
    # Detect type: the words may be on same line or split across lines
    a1_joined = a1.replace('\n', ' ')
    is_natural = bool(re.search(r'PERSONA\s+NATURAL', a1_joined))
    is_juridica = bool(re.search(r'PERSONA\s+JUR[ÍI]DICA', a1_joined))
    
    # Amount (handle both comma and dot as decimal separator)
    amount = 0
    am_match = re.search(r'S/[\.\s]*([\d\s\n]+[.,]\d{2})', a1)
    if am_match:
        am_str = am_match.group(1).replace('\n', '').replace(' ', '')
        try:
            amount = _parse_amount_str(am_str)
        except ValueError:
            amount = 0
    
    result = {
        'rd_num': rd_num, 'fecha': fecha, 'monto': amount,
        'region': '', 'url_pdf': pdf_url,
        'tipo': 'natural' if is_natural else 'juridica',
    }
    
    if is_natural:
        result.update(_parse_natural(a1))
    else:
        result.update(_parse_juridica(a1))
    
    return result


def _find_region(text):
    for r in REGIONS:
        if r in text.upper():
            return r.capitalize()
    return ''


def _non_header(lines):
    """Yield non-blank, non-header lines."""
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s in HEADERS:
            continue
        yield s


def _parse_natural(a1):
    """Parse a persona natural resolution."""
    result = {'proyecto': '', 'evento': '', 'pais': ''}
    
    raw_lines = a1.split('\n')
    
    # Find ID line (DNI, Carnet de Extranjería, or parenthesized)
    dni_line_idx = None
    for i, line in enumerate(raw_lines):
        s = line.strip()
        if re.search(r'(?:DNI|Carnet de Extranjería)\s+N[°º]?\s*\d+', line, re.IGNORECASE):
            dni_line_idx = i
            break
        # Parenthesized DNI: "(46808580)"
        if re.match(r'^\(\d{8}\)$', s):
            dni_line_idx = i
            break
    # Handle split across lines (e.g., "DNI Nº\n46435117" or "Carnet de Extranjería\nNº 000883096")
    if dni_line_idx is None:
        for i, line in enumerate(raw_lines[:-1]):
            s = line.strip()
            if re.search(r'Carnet de Extranjer[íi]a', s, re.IGNORECASE):
                if re.search(r'N[°º]?\s*\d{7,}', raw_lines[i+1], re.IGNORECASE):
                    dni_line_idx = i
                    break
            if re.search(r'DNI\s+N[°º]?', s, re.IGNORECASE):
                if re.search(r'\d{8}', raw_lines[i+1]):
                    dni_line_idx = i
                    break
    
    # Collect name lines: look backwards from DNI N, stopping at blank or stop word
    name_parts = []
    if dni_line_idx is not None:
        for j in range(dni_line_idx - 1, -1, -1):
            s = raw_lines[j].strip()
            if not s:
                break
            words = set(s.upper().replace(',','').replace('(','').replace(')','').split())
            if words & STOP_WORDS_NATURAL:
                break
            name_parts.insert(0, s)
    
    # Also try the forward approach if backward didn't capture enough
    if not name_parts:
        # Find (DNI) line and look forward
        for i, line in enumerate(raw_lines):
            if '(DNI)' in line:
                for j in range(i + 1, min(i + 15, len(raw_lines))):
                    s = raw_lines[j].strip()
                    if not s:
                        continue
                    if re.search(r'DNI\s+N[°º]?', s):
                        break
                    if s.upper() in ('REGIÓN','REGION'):
                        continue
                    if s in HEADERS:
                        continue
                    name_parts.append(s)
                break
    
    full_name = ' '.join(name_parts)
    full_name = full_name.replace(',', '').strip()
    
    # Split names (Peruvian: nombres apellido_paterno apellido_materno)
    parts = full_name.split()
    if len(parts) >= 3:
        result['nombres'] = ' '.join(parts[:-2])
        result['apellidos'] = ' '.join(parts[-2:])
    elif len(parts) == 2:
        result['nombres'] = parts[0]
        result['apellidos'] = parts[1]
    else:
        result['nombres'] = full_name
        result['apellidos'] = ''
    
    # DNI from the ID line (handle split across lines and parenthesized)
    result['dni'] = ''
    if dni_line_idx is not None:
        s = raw_lines[dni_line_idx].strip()
        # Parenthesized DNI: "(46808580)"
        if re.match(r'^\(\d{8}\)$', s):
            result['dni'] = s[1:-1]
        else:
            full_id_line = s + ' ' + (raw_lines[dni_line_idx+1] if dni_line_idx+1 < len(raw_lines) else '')
            dn_match = re.search(r'(\d{8,9})', full_id_line)
            if dn_match:
                result['dni'] = dn_match.group(1)
    
    # Region: find in the text
    result['region'] = _find_region(a1)
    
    # Extract project/event from data region between DNI and S/.
    paragraphs = re.split(r'\n\s*\n', a1)
    data_paragraphs = []
    # Full column header phrases (uppercase-only comparison)
    header_phrases = [
        'REGIÓN', 'REGION',
        'PROYECTO U OBRA VINCULADA A LA PROYECTO',
        'PROYECTO VINCULADO A LA PROYECTO',
        'OBRA VINCULADA A LA PROYECTO',
        'EVENTO INTERNACIONAL VINCULADO A LA PROYECTO',
        'MONTO DEL ESTÍMULO', 'MONTO DEL ESTÍMUL O',
        'PERSONA NATURAL', 'PERSONA JURÍDICA', 'PERSONA JURIDICA',
        '(DNI)', '(RUC)',
    ]
    for p in paragraphs:
        text = p.strip()
        if not text:
            continue
        text_clean = text.replace('\n', ' ').strip()
        upper = ' '.join(text_clean.upper().split())  # normalize whitespace
        if 'DECLARAR' in upper:
            continue
        if re.search(r'DNI\s+N[°º]?\s*\d{8}', text, re.IGNORECASE) or re.match(r'^\(\d{8}\)$', text):
            continue
        if re.match(r'^[\d\s,./()-]+$', text_clean):
            continue
        # Skip if this paragraph is a known column header
        is_header = False
        for hp in header_phrases:
            hp_norm = ' '.join(hp.upper().split())
            if upper == hp_norm or upper.startswith(hp_norm) or hp_norm.startswith(upper):
                is_header = True
                break
        if is_header:
            continue
        
        data_paragraphs.append(text_clean)
    
    if data_paragraphs:
        for i, p in enumerate(data_paragraphs):
            r = _find_region(p)
            if r:
                result['region'] = r
                if len(data_paragraphs) >= i + 2:
                    result['proyecto'] = data_paragraphs[i + 1]
                    result['evento'] = data_paragraphs[i + 1]
                if len(data_paragraphs) >= i + 3:
                    result['evento'] = data_paragraphs[i + 2]
                break
        else:
            result['proyecto'] = data_paragraphs[0]
            result['evento'] = data_paragraphs[0]
            if len(data_paragraphs) >= 2:
                result['evento'] = data_paragraphs[1]
    
    # Fallback: if proyecto still empty, use evento
    if not result['proyecto'] and result['evento']:
        result['proyecto'] = result['evento']
    
    # Country
    
    # Country
    for c in COUNTRIES:
        if c.upper() in a1.upper():
            result['pais'] = c
            break
    
    return result


def _is_header_line(s):
    """Check if a line is a header or structural element."""
    if not s:
        return True
    s_up = s.upper().strip()
    if s_up in HEADERS:
        return True
    if s_up in ('PERSONA JURÍDICA', 'PERSONA JURIDICA', 'PERSONA NATURAL', '(RUC)', '(DNI)'):
        return True
    if re.match(r'^(REGI[OÓ]N|REGION|PROYECTO|OBRA|EVENTO|MONTO|RESPONSABLE|VINCULAD)', s_up):
        return True
    if s_up in ('LA', 'A LA', 'DE LA', 'U', 'O', 'N', 'D'):
        return True
    if re.match(r'^[\)]?\s*$', s_up):
        return True
    return False


def _parse_juridica(a1):
    """Parse a persona jurídica resolution."""
    result = {'proyecto': ''}
    
    ruc_match = re.search(r'RUC\s*(?:N[°º]?\s*)?(\d{11})', a1)
    result['ruc'] = ruc_match.group(1) if ruc_match else ''
    
    raw_lines = a1.split('\n')
    
    # Find RUC N line (either "RUC N°..." or parenthesized "(20535915742)")
    ruc_line_idx = None
    for i, line in enumerate(raw_lines):
        s = line.strip()
        if re.search(r'RUC\s*(?:N[°º])', s):
            ruc_line_idx = i
            break
        # Also handle parenthesized RUC: "(20535915742)"
        if re.match(r'^\(\d{11}\)$', s):
            ruc_line_idx = i
            # Extract the RUC number
            result['ruc'] = s[1:-1]
    # Also check for RUC on next line after parenthesized
    if ruc_line_idx is None:
        for i, line in enumerate(raw_lines):
            if re.search(r'RUC', line, re.IGNORECASE):
                # Could be just "RUC" before a number
                for j in range(i, min(i+3, len(raw_lines))):
                    ruc_m = re.search(r'(\d{11})', raw_lines[j])
                    if ruc_m:
                        result['ruc'] = ruc_m.group(1)
                        ruc_line_idx = j
                        break
                if ruc_line_idx is not None:
                    break
    
    # Razón social: collect all non-blank, non-header lines BEFORE RUC N
    result['razon_social'] = result.get('ruc', '')
    if ruc_line_idx is not None:
        rs_parts = []
        for i in range(ruc_line_idx - 1, -1, -1):
            s = raw_lines[i].strip()
            if not s:
                break  # blank line = end of name block
            if _is_header_line(s):
                continue
            if 'S/' in s:
                continue  # data row, not name
            rs_parts.insert(0, s)
        if rs_parts:
            result['razon_social'] = ' '.join(rs_parts)
    
    result['region'] = _find_region(a1)
    
    # After RUC N: collect data lines (skipping headers and blanks)
    data_after = []
    if ruc_line_idx is not None:
        for line in raw_lines[ruc_line_idx + 1:]:
            s = line.strip()
            if not s:
                continue
            if _is_header_line(s):
                continue
            data_after.append(s)
    
    # Data: check both before and after RUC N
    project = ''
    
    # Collect all non-header lines before RUC N that contain S/ (EDI format)
    data_before = []
    if ruc_line_idx is not None:
        for i in range(ruc_line_idx - 1, -1, -1):
            s = raw_lines[i].strip()
            if not s:
                continue
            if _is_header_line(s):
                continue
            if re.search(r'S/', s):
                data_before.insert(0, s)
                break
    
    # For data_before: parse "REGION  PROJECT  S/ AMOUNT"
    if data_before:
        row = data_before[0]
        row_text = re.sub(r'S/[\.\s]*[\d\s\n]+\,\d{2}', '', row).strip()
        for r in sorted(REGIONS, key=len, reverse=True):
            if r.upper() in row_text.upper():
                row_text = row_text.upper().replace(r.upper(), '', 1).strip()
                break
        row_text = re.sub(r'\s+', ' ', row_text).strip()
        if row_text:
            project = row_text
    
    # Fall back to paragraph-based approach (EPA/EDI formats after RUC N)
    if not project and ruc_line_idx is not None:
        paragraphs = []
        current = []
        for line in raw_lines[ruc_line_idx + 1:]:
            s = line.strip()
            if not s:
                if current:
                    paragraphs.append(current)
                    current = []
                continue
            if _is_header_line(s):
                continue
            current.append(s)
        if current:
            paragraphs.append(current)
        
        # Skip the first paragraph (region), rest are project and responsable
        if len(paragraphs) >= 2:
            # Find responsable paragraph (has DNI)
            resp_idx = None
            for i, para in enumerate(paragraphs):
                if any(re.search(r'\(DNI\s', p) for p in para):
                    resp_idx = i
                    break
            
            if resp_idx is not None and resp_idx >= 2:
                # Project is paragraph between region (0) and responsable
                proj_text = ' '.join(paragraphs[resp_idx - 1])
                # Remove any stray region names
                for r in sorted(REGIONS, key=len, reverse=True):
                    if r.upper() in proj_text.upper():
                        proj_text = proj_text.upper().replace(r.upper(), '', 1).strip()
                project = re.sub(r'\s+', ' ', proj_text).strip()
            elif resp_idx is None:
                # No responsable: skip first paragraph (region), rest is project
                para_texts = [' '.join(p) for p in paragraphs[1:]]
                para_text = ' '.join(para_texts)
                # Remove S/ lines
                para_text = re.sub(r'S/[\.\s]*[\d\s]+\,\d{2}', '', para_text)
                for r in sorted(REGIONS, key=len, reverse=True):
                    if r.upper() in para_text.upper():
                        para_text = para_text.upper().replace(r.upper(), '', 1).strip()
                project = re.sub(r'\s+', ' ', para_text).strip()
    
    result['proyecto'] = project
    
    # Responsable (DNI)
    result['resp_dni'] = ''
    result['resp_nombres'] = ''
    for i, line in enumerate(raw_lines):
        s = line.strip()
        dn_match = re.search(r'\(DNI\s*(?:N[°º]?\s*)?(\d{8})\)', s)
        if dn_match:
            result['resp_dni'] = dn_match.group(1)
            name_parts = []
            for j in range(i - 1, max(i - 6, -1), -1):
                prev = raw_lines[j].strip()
                if not prev:
                    break
                if _is_header_line(prev):
                    continue
                if re.search(r'^S/', prev):
                    continue
                for r in REGIONS:
                    if r.upper() == prev.upper():
                        continue
                if prev == '(DNI)' or prev == '(RUC)':
                    continue
                name_parts.insert(0, prev)
            if name_parts:
                result['resp_nombres'] = ' '.join(name_parts)
            break
    
    return result


def _extract_project_from_row(row):
    """Extract project name from a columnar data row like 'AREQUIPA  Nanito  S/ 100 000,00'."""
    # Remove the S/ amount
    row_text = re.sub(r'S/[\.\s]*[\d\s]+\,\d{2}', '', row).strip()
    # Remove region name
    for r in sorted(REGIONS, key=len, reverse=True):
        if r in row_text.upper():
            idx = row_text.upper().index(r)
            row_text = row_text[:idx] + row_text[idx + len(r):]
            break
    # Clean up
    row_text = re.sub(r'\s+', ' ', row_text).strip()
    return row_text

FALLO_HEADER_KEYWORDS = ['PERSONA', 'JURÍDICA', '(RUC)', 'REGIÓN', 'PROYECTO',
                         'CATEGORÍ', 'RESPONSAB', 'DIRECTOR', 'MONTO', 'OTORGADO']

FALLO_COLUMN_RANGES = {
    'empresa':   (0, 22),
    'region':    (22, 40),
    'proyecto':  (40, 65),
    'categoria': (65, 82),
    'responsable': (82, 108),
    'director':  (108, 126),
    'monto':     (126, 160),
}


def detect_fallo_columns(layout_lines):
    """Detect column boundaries from header lines in a Fallo Final PDF layout."""
    # Scan header lines for keywords (only in first 30 lines to avoid data false matches)
    headers_found = {}
    for line in layout_lines[:30]:
        for kw in FALLO_HEADER_KEYWORDS:
            # Match as whole word with word boundaries
            pattern = r'\b' + re.escape(kw) + r'\b'
            m = re.search(pattern, line)
            if m:
                idx = m.start()
                if kw not in headers_found or idx < headers_found[kw]:
                    headers_found[kw] = idx
    
    if not headers_found:
        return list(FALLO_COLUMN_RANGES.items())
    
    # Sort found headers by position
    sorted_kws = sorted(headers_found.items(), key=lambda x: x[1])
    
    col_defs = []
    
    # Column 1: empresa — from left edge to first non-persona keyword
    c1_start = 0
    c1_end = None
    for kw, pos in sorted_kws:
        if kw not in ('PERSONA', 'JURÍDICA', '(RUC)'):
            c1_end = pos
            break
    if c1_end is None:
        c1_end = 22
    col_defs.append(('empresa', c1_start, c1_end))
    
    # Column 2: region — look for REGIÓN
    if 'REGIÓN' in headers_found:
        c2_start = headers_found['REGIÓN']
        # Find next column after REGIÓN
        c2_end = None
        for kw, pos in sorted_kws:
            if kw != 'REGIÓN' and pos > c2_start and kw not in ('PERSONA', 'JURÍDICA', '(RUC)'):
                c2_end = pos
                break
        if c2_end is None:
            c2_end = c2_start + 18
        col_defs.append(('region', c2_start, c2_end))
    
    # Column 3: proyecto — look for PROYECTO
    proj_positions = sorted([v for k, v in headers_found.items() if k == 'PROYECTO'])
    if proj_positions:
        c3_start = proj_positions[0]
        c3_end = None
        for kw, pos in sorted_kws:
            if kw not in ('PERSONA', 'JURÍDICA', '(RUC)', 'PROYECTO', 'REGIÓN') and pos > c3_start:
                c3_end = pos
                break
        if c3_end is None:
            c3_end = c3_start + 25
        col_defs.append(('proyecto', c3_start, c3_end))
    
    # Column 4: categoria
    if 'CATEGORÍ' in headers_found:
        c4_start = headers_found['CATEGORÍ']
        c4_end = None
        for kw, pos in sorted_kws:
            if kw not in ('PERSONA', 'JURÍDICA', '(RUC)', 'PROYECTO', 'REGIÓN', 'CATEGORÍ') and pos > c4_start:
                c4_end = pos
                break
        if c4_end is None:
            c4_end = c4_start + 18
        col_defs.append(('categoria', c4_start, c4_end))
    
    # Column 5: responsable
    resp_start = None
    if 'RESPONSAB' in headers_found:
        resp_start = headers_found['RESPONSAB']
    elif 'DIRECTOR' in headers_found:
        # Only DIRECTOR present — use it for responsable
        resp_start = headers_found['DIRECTOR']
    
    if resp_start is not None:
        resp_end = None
        for kw, pos in sorted_kws:
            if kw not in ('PERSONA', 'JURÍDICA', '(RUC)', 'PROYECTO', 'REGIÓN', 'CATEGORÍ', 'RESPONSAB', 'DIRECTOR') and pos > resp_start:
                resp_end = pos
                break
        if resp_end is None:
            resp_end = resp_start + 25
        col_defs.append(('responsable', resp_start, resp_end))
    
    # Column 6: director (only if DIRECTOR appears and is separate from RESPONSABLE)
    if 'DIRECTOR' in headers_found and 'RESPONSAB' in headers_found:
        c6_start = headers_found['DIRECTOR']
        c6_end = None
        for kw, pos in sorted_kws:
            if kw not in ('PERSONA', 'JURÍDICA', '(RUC)', 'PROYECTO', 'REGIÓN', 'CATEGORÍ', 'RESPONSAB', 'DIRECTOR') and pos > c6_start:
                c6_end = pos
                break
        if c6_end is None:
            c6_end = c6_start + 20
        col_defs.append(('director', c6_start, c6_end))
    elif 'DIRECTOR' in headers_found and 'RESPONSAB' not in headers_found:
        # Single responsable/director column — add as director too
        col_defs.append(('director', resp_start, resp_end))
    
    # Column 7: monto
    if 'MONTO' in headers_found:
        c7_start = headers_found['MONTO']
        c7_end = c7_start + 25
        col_defs.append(('monto', c7_start, c7_end))
    elif 'OTORGADO' in headers_found:
        c7_start = headers_found['OTORGADO']
        c7_end = c7_start + 25
        col_defs.append(('monto', c7_start, c7_end))
    
    if len(col_defs) >= 3:
        return col_defs
    
    return list(FALLO_COLUMN_RANGES.items())


def extract_column_text(col_start, col_end, lines_block):
    """Extract text within a column range from a block of layout lines."""
    parts = []
    for line in lines_block:
        if col_start >= len(line):
            continue
        chunk = line[col_start:col_end].strip()
        if chunk:
            parts.append(chunk)
    text = ' '.join(parts)
    # Remove duplicates (same word may appear in multiple lines at same position)
    # Simple approach: join all and let caller clean
    return text.strip()


def parse_fallo_beneficiaries(layout_a1, pdf_url, concurso_codigo):
    """Parse Fallo Final beneficiaries from layout-formatted Article 1 text."""
    lines = layout_a1.split('\n')
    
    # Detect columns from headers
    col_defs = detect_fallo_columns(lines)
    
    # Find the first line that looks like a data line (not preamble, not header)
    # A data line has a company name at the left edge and doesn't contain header keywords
    data_start = None
    header_passed = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Check if we've gone through the header region
        has_header_kw = any(kw in line for kw in FALLO_HEADER_KEYWORDS)
        if has_header_kw:
            header_passed = True
            continue
        if not header_passed:
            continue
        # Skip lines that are clearly preamble or footer
        if any(kw in stripped for kw in ['DECLARAR', 'Art.', 'copia auténtica', 'DESPACHO',
                                           'DIRECCIÓN GENERAL', 'Decenio', 'Año de la',
                                           'Regístrese', 'Comuníquese']):
            continue
        # Skip lines that don't have meaningful content at position 0-15
        left_text = line[:20].strip()
        if not left_text:
            continue
        if len(left_text) < 3:
            continue
        # This looks like a data line
        data_start = i
        break
    
    if data_start is None:
        return []
    
    # Split into blocks separated by blank lines from data_start onwards
    # Stop when we hit footer lines
    blocks = []
    current = []
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        # Stop at footer
        if any(kw in stripped for kw in ['Art.', 'copia auténtica', 'DESPACHO',
                                           'DIRECCIÓN GENERAL', 'Decenio', 'Año de la',
                                           'Regístrese', 'Comuníquese']):
            if current:
                blocks.append(current)
            break
        current.append(line)
    if current:
        blocks.append(current)
    
    # Parse each block
    beneficiaries = []
    for block in blocks:
        # Check if this block has company-like content (look for RUC, DNI, or left-edge text)
        block_text = ' '.join(block)
        has_ruc = bool(re.search(r'\d{11}', block_text.replace(' ', '')))
        has_dni = bool(re.search(r'(?<!\d)\d{8}(?!\d)', block_text))
        col_text = extract_column_text(0, 25, block)
        if not has_ruc and not has_dni and not col_text:
            continue  # Skip blocks that look like footer artifacts
        
        b = {}
        for col_name, col_start, col_end in col_defs:
            text = extract_column_text(col_start, col_end, block)
            if text:
                b[col_name] = text
        
        if not b:
            continue
        
        # Extract RUC from empresa field
        empresa_text = b.get('empresa', '')
        ruc_match = re.search(r'(\d{11})', empresa_text.replace(' ', ''))
        if ruc_match:
            b['ruc'] = ruc_match.group(1)
        else:
            # Maybe RUC is in a separate block before this one? Check for parenthesized RUC
            # in the block
            ruc_match2 = re.search(r'\((\d{11})\)', block_text)
            if ruc_match2:
                b['ruc'] = ruc_match2.group(1)
            else:
                b['ruc'] = ''

        # Extract DNI (for natural persons)
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
        else:
            b['tipo_persona'] = 'juridica'
        
        # Extract amount from monto field
        monto_text = b.get('monto', '')
        am_match = re.search(r'(?:S/?\.?\s*)?([\d\s,]+[.,]\d{2})', monto_text)
        if am_match:
            try:
                b['monto'] = _parse_amount_str(am_match.group(1).replace(' ', ''))
            except ValueError:
                b['monto'] = 0
        else:
            b['monto'] = 0
        
        # Clean company name
        company = empresa_text
        # Remove RUC and DNI from company name
        company = re.sub(r'\(?\d{11}\)?', '', company).strip()
        company = re.sub(r'\(?\d{8}\)?', '', company).strip()
        company = re.sub(r'\(DNI\)', '', company, flags=re.IGNORECASE).strip()
        # Clean punctuation at edges
        company = re.sub(r'^[\s,;:.\-]+|[\s,;:.\-]+$', '', company)
        company = re.sub(r'\s+', ' ', company).strip()
        b['razon_social'] = company

        if b.get('tipo_persona') == 'natural':
            name = company
            if ',' in name:
                parts = name.split(',', 1)
                b['apellidos'] = parts[0].strip()
                b['nombres'] = parts[1].strip()
            else:
                words = name.split()
                if len(words) >= 2:
                    b['nombres'] = ' '.join(words[:-1])
                    b['apellidos'] = words[-1]
                elif len(words) == 1:
                    b['nombres'] = words[0]
                    b['apellidos'] = ''
                else:
                    b['nombres'] = ''
                    b['apellidos'] = ''
        
        beneficiaries.append(b)
    
    return beneficiaries


def parse_fallo(text, layout_text, pdf_url, concurso_codigo):
    """Parse Fallo Final PDF (multiple beneficiaries in table format)."""
    rd_num = extract_rd_num(text)
    fecha = extract_fecha(text)
    
    a1_match = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|Artículo\s)', layout_text, re.DOTALL)
    if not a1_match:
        a1_match = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|Artículo\s)', text, re.DOTALL)
    
    if not a1_match:
        return None
    a1 = a1_match.group(1)
    
    # Detect modality
    modalidad = ''
    mod_match = re.search(r"modalidad\s+de\s+['\"]?([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)['\"]?", a1)
    if mod_match:
        modalidad = mod_match.group(1).strip()
    
    # Parse beneficiaries from layout
    beneficiaries = parse_fallo_beneficiaries(a1, pdf_url, concurso_codigo)
    
    return {
        'rd_num': rd_num,
        'fecha': fecha,
        'modalidad': modalidad,
        'url_pdf': pdf_url,
        'beneficiaries': beneficiaries,
    }
def generate_inserts(data, concurso_codigo):
    """Generate SQL INSERT statements."""
    ca_id = get_concurso_id(concurso_codigo)
    if not ca_id:
        return f"-- ERROR: concurso {concurso_codigo} not found\n"
    
    name = data.get('nombres','') or data.get('razon_social','') or 'unknown'
    sql = f"\n-- {concurso_codigo}: {name}\n"
    
    if data.get('tipo') == 'natural':
        dni_val = data.get('dni', '')
        sql += f"INSERT INTO persona (tipo, nombres, apellidos, dni, region)\n"
        sql += f"SELECT 'natural', {q(data['nombres'])}, {q(data.get('apellidos',''))}, {q(dni_val)}, {q(data.get('region',''))}\n"
        sql += f"WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND dni={q(dni_val)});\n"
        lookup = f"dni = {q(dni_val)}"
    else:
        if data.get('ruc'):
            ruc_val = data.get('ruc', '')
            sql += f"INSERT INTO persona (tipo, razon_social, ruc, region)\n"
            sql += f"SELECT 'juridica', {q(data.get('razon_social',''))}, {q(ruc_val)}, {q(data.get('region',''))}\n"
            sql += f"WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='juridica' AND ruc={q(ruc_val)});\n"
            lookup = f"ruc = {q(ruc_val)}"
        else:
            return f"-- SKIP {concurso_codigo}: no RUC\n"
    
    proyecto = data.get('proyecto', '').strip()
    if proyecto:
        sql += f"INSERT OR IGNORE INTO obra (titulo) VALUES ({q(proyecto)});\n"
        sql += f"""INSERT INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
SELECT {ca_id}, p.id, ob.id, {data.get('monto', 0)}
FROM persona p, obra ob
WHERE p.{lookup} AND ob.titulo = {q(proyecto)}
AND NOT EXISTS (SELECT 1 FROM proyecto WHERE concurso_anual_id={ca_id} AND persona_beneficiaria_id=p.id);\n"""
    else:
        sql += f"""INSERT INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
SELECT {ca_id}, p.id, NULL, {data.get('monto', 0)}
FROM persona p
WHERE p.{lookup}
AND NOT EXISTS (SELECT 1 FROM proyecto WHERE concurso_anual_id={ca_id} AND persona_beneficiaria_id=p.id);\n"""
    
    sql += f"""INSERT INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf)
SELECT {ca_id}, {q(data.get('rd_num',''))}, {q(data.get('fecha',''))}, 'resolucion_beneficiario', {q(data.get('url_pdf',''))}
WHERE NOT EXISTS (SELECT 1 FROM resolucion WHERE url_pdf = {q(data.get('url_pdf',''))});\n"""
    
    sql += f"""INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id)
SELECT po.id, r.id FROM proyecto po, resolucion r
WHERE po.concurso_anual_id = {ca_id} AND po.persona_beneficiaria_id = (SELECT id FROM persona WHERE {lookup})
  AND r.url_pdf = {q(data.get('url_pdf',''))};\n"""
    
    # Handle responsable (for juridica with a responsible person)
    if data.get('resp_dni'):
        resp_nombres = data.get('resp_nombres', '')
        parts = resp_nombres.split()
        resp_nom = ' '.join(parts[:-2]) if len(parts) >= 3 else (parts[0] if parts else '')
        resp_ape = ' '.join(parts[-2:]) if len(parts) >= 3 else (' '.join(parts[1:]) if len(parts) >= 2 else '')
        
        resp_dni_val = data.get('resp_dni', '')
        sql += f"INSERT INTO persona (tipo, nombres, apellidos, dni) SELECT 'natural', {q(resp_nom)}, {q(resp_ape)}, {q(resp_dni_val)} WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND dni={q(resp_dni_val)});\n"
        sql += f"""INSERT OR IGNORE INTO proyecto_integrante (proyecto_id, persona_id, rol)
SELECT po.id, p.id, 'responsable' FROM proyecto po, persona p
WHERE po.persona_beneficiaria_id = (SELECT id FROM persona WHERE {lookup})
  AND p.dni = {q(data.get('resp_dni',''))}
  AND NOT EXISTS (SELECT 1 FROM proyecto_integrante WHERE proyecto_id = po.id AND persona_id = p.id);\n"""
    
    return sql

def generate_fallo_inserts(result, concurso_codigo):
    """Generate SQL for a Fallo Final PDF with multiple beneficiaries."""
    ca_id = get_concurso_id(concurso_codigo)
    if not ca_id:
        return f"-- ERROR: concurso {concurso_codigo} not found\n"
    
    url_pdf = result.get('url_pdf', '')
    rd_num = result.get('rd_num', '')
    fecha = result.get('fecha', '')
    
    sql = f"\n-- Fallo Final {concurso_codigo}: {rd_num}\n"
    # Insert resolution once
    sql += f"""INSERT INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf)
SELECT {ca_id}, {q(rd_num)}, {q(fecha)}, 'fallo_final', {q(url_pdf)}
WHERE NOT EXISTS (SELECT 1 FROM resolucion WHERE url_pdf = {q(url_pdf)});\n"""
    
    beneficiaries = result.get('beneficiaries', [])
    for i, b in enumerate(beneficiaries):
        tipo_persona = b.get('tipo_persona', 'juridica')
        ruc = b.get('ruc', '')
        dni = b.get('dni', '')
        nombres = b.get('nombres', '')
        apellidos = b.get('apellidos', '')
        razon_social = b.get('razon_social', '')
        proyecto = b.get('proyecto', '')
        region = b.get('region', '')
        monto = b.get('monto', 0)

        # Heuristic: reclasificar jurídicas sin RUC que parecen personas naturales
        if tipo_persona != 'natural' and not ruc and not dni:
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

        if tipo_persona == 'natural':
            if not nombres and not apellidos:
                sql += f"\n-- SKIP beneficiary {i}: natural sin nombre\n"
                continue
            if dni:
                sql += f"""INSERT INTO persona (tipo, nombres, apellidos, dni, region)
SELECT 'natural', {q(nombres)}, {q(apellidos)}, {q(dni)}, {q(region)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND dni={q(dni)});\n"""
                lookup = f"dni = {q(dni)}"
            else:
                # DNI-less natural: dedup by nombres+apellidos
                sql += f"""INSERT INTO persona (tipo, nombres, apellidos, dni, region)
SELECT 'natural', {q(nombres)}, {q(apellidos)}, '', {q(region)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND nombres={q(nombres)} AND apellidos={q(apellidos)} AND (dni IS NULL OR dni = ''));\n"""
                lookup = f"nombres = {q(nombres)} AND apellidos = {q(apellidos)} AND (dni IS NULL OR dni = '')"
        else:
            if ruc:
                sql += f"""INSERT INTO persona (tipo, razon_social, ruc, region)
SELECT 'juridica', {q(razon_social)}, {q(ruc)}, {q(region)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='juridica' AND ruc={q(ruc)});\n"""
                lookup = f"ruc = {q(ruc)}"
            else:
                # RUC-less juridica: dedup by razon_social
                if not razon_social or len(razon_social) < 3:
                    sql += f"\n-- SKIP beneficiary {i}: invalid juridica ({razon_social})\n"
                    continue
                sql += f"""INSERT INTO persona (tipo, razon_social, ruc, region)
SELECT 'juridica', {q(razon_social)}, '', {q(region)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='juridica' AND razon_social={q(razon_social)} AND (ruc IS NULL OR ruc = ''));\n"""
                lookup = f"razon_social = {q(razon_social)} AND (ruc IS NULL OR ruc = '')"
        
        # Proyecto (if present)
        if proyecto:
            sql += f"""INSERT OR IGNORE INTO obra (titulo) VALUES ({q(proyecto)});\n"""
            sql += f"""INSERT INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
SELECT {ca_id}, p.id, ob.id, {monto}
FROM persona p, obra ob
WHERE p.{lookup} AND ob.titulo = {q(proyecto)}
AND NOT EXISTS (SELECT 1 FROM proyecto WHERE concurso_anual_id={ca_id} AND persona_beneficiaria_id=p.id);\n"""
        else:
            sql += f"""INSERT INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado)
SELECT {ca_id}, p.id, NULL, {monto}
FROM persona p
WHERE p.{lookup}
AND NOT EXISTS (SELECT 1 FROM proyecto WHERE concurso_anual_id={ca_id} AND persona_beneficiaria_id=p.id);\n"""

        # Link postulación ↔ resolución
        sql += f"""INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id)
SELECT po.id, r.id FROM proyecto po, resolucion r
WHERE po.concurso_anual_id = {ca_id} AND po.persona_beneficiaria_id = (SELECT id FROM persona WHERE {lookup})
  AND r.url_pdf = {q(url_pdf)};\n"""

        # Responsable (persona natural linked to this postulación)
        responsable = b.get('responsable', '')
        if tipo_persona != 'natural' and responsable:
            # The responsable field may contain both name and DNI
            resp_dni_match = re.search(r'\(?\d{8}\)?', responsable)
            resp_dni = resp_dni_match.group(0).strip('()') if resp_dni_match else ''
            
            # Clean name: remove DNI, remove special chars
            resp_nombre = re.sub(r'\(?\d{8}\)?', '', responsable).strip(' ,')
            resp_nombre = re.sub(r'\s+', ' ', resp_nombre).strip()
            
            if resp_dni and resp_nombre and len(resp_nombre) >= 5:
                # Name parsing (last word(s) are surnames)
                parts = resp_nombre.split()
                if len(parts) >= 3:
                    resp_nom = ' '.join(parts[:-2])
                    resp_ape = ' '.join(parts[-2:])
                elif len(parts) >= 2:
                    resp_nom = parts[0]
                    resp_ape = parts[-1]
                else:
                    resp_nom = resp_nombre
                    resp_ape = ''
                
                if resp_nom and resp_ape:
                    sql += f"""INSERT INTO persona (tipo, nombres, apellidos, dni)
SELECT 'natural', {q(resp_nom)}, {q(resp_ape)}, {q(resp_dni)}
WHERE NOT EXISTS (SELECT 1 FROM persona WHERE tipo='natural' AND dni={q(resp_dni)});\n"""
                    sql += f"""INSERT OR IGNORE INTO proyecto_integrante (proyecto_id, persona_id, rol)
SELECT po.id, p.id, 'responsable' FROM proyecto po, persona p
WHERE po.concurso_anual_id = {ca_id} AND po.persona_beneficiaria_id = (SELECT id FROM persona WHERE {lookup})
  AND p.dni = {q(resp_dni)};\n"""

    return sql


# ============================================================
# PDF URLS
# ============================================================

EPI_FILES = [
    "2025-EPI-RD000611-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD000613-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000622-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000633-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000647-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000657-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000707-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000722-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000736-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000759-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000760-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000761-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000791-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000792-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000793-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000794-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000795-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000796-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000825-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000829-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000855-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000880-2025-DGIA-VMPCIC.pdf.pdf",
    "2025-EPI-RD000879-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD000918-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD000919-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD000938-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD000961-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD000979-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD000980-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD000981-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD000982-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD001004-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EPI-RD001054-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD001042-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD001078-2025-DGIA-VMPCIC.pdf",
    "2025-EPI-RD001123-2025-DGIA-VMPCIC.pdf",
]

EDI_FILES = [
    "2025-EDI-000549-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-000548-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-000547-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-RD000557-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-RD000586-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-RD000634-2025-DGIA-VMPCIC-MC.pdf",
    "2025-EDI-RD000675-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-RD000676-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-RD000688-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-RD000689-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-RD000690-2025-DGIA-VMPCIC.pdf",
    "2025-EDI-RD000885-2025-DGIA-VMPCIC.pdf",
]

EPA_FILES = [
    "2025-EPA-RD001073-2025-DGIA-VMPCIC.pdf",
    "2025-EPA-RD001078-2025-DGIA-VMPCIC.pdf",
    "2025-EPA-RD001122-2025-DGIA-VMPCIC.pdf",
    "2025-EPA-RD001124-2025-DGIA-VMPCIC.pdf",
    "2025-EPA-RD001125-2025-DGIA-VMPCIC.pdf",
    "2025-EPA-RD001126-2025-DGIA-VMPCIC.pdf",
]

FALLO_FILES = {
    'CPF': [
        ('Desarrollo', '2025-CPF-D-FalloFinal.pdf'),
        ('Nuevos realizadores', '2025-CPF-P-NR-FalloFinal.pdf'),
        ('Regiones', '2025-CPF-P-R-Beneficiarios.pdf'),
        ('Tercer largometraje a más', '2025-CPF-TL-FalloFinal.pdf'),
    ],
    'CDO': [
        ('Producción', '2025-CDO-P-FalloFinal.pdf'),
        ('Desarrollo', '2025-CDO-D-FalloFinal.pdf'),
    ],
    'CPC': [
        ('Segunda obra a más', '2025-CPC-2da-FalloFinal.pdf'),
        ('Ópera prima', '2025-CPC-OP-FalloFinal_0.pdf'),
    ],
    'CPA': [
        ('Cortometrajes', '2025-CPA-C-FalloFinal.pdf'),
        ('Desarrollo, Preproducción, Producción, Desarrollo de series', '2025-CPA-P-PP-DS-D-FalloFinal.pdf'),
    ],
    'CDV': [
        ('', '2025-CDV-FalloFinal.pdf'),
    ],
    'CGC': [
        ('Festivales, encuentros y muestras', '2025-CGC-FEM-Beneficiarios.pdf'),
        ('Fortalecimiento de capacidades', '2025-CGC-FC-FalloFinal.pdf'),
    ],
    'CIC': [('', '2025-CIC-FalloFinal.pdf')],
    'CCC': [('', '2025-CCC-FalloFinalJurado.pdf')],
    'CCM': [('', '2025-CCM-FalloFinal.pdf')],
    'CDC': [('', '2025-CDC-FalloFinal.pdf')],
    'CGS': [('', '2025-CGS-FalloFinal.pdf')],
    'CFO': [('', '2025-CFO-ActadeEvaluación.pdf')],
    'CIN': [('', '2025-CIN-FalloFinal.pdf')],
    'CCE': [('', '2025-CCE-FalloFinal.pdf')],
}

def process_pdf_list(files, codigo, parser_func, concurso_codigo):
    sql = ""
    count = 0
    for fname in files:
        url = DOC4_BASE + fname
        try:
            flow_text, _ = download_and_extract(url)
            data = parser_func(flow_text, url)
            if data:
                sql += generate_inserts(data, concurso_codigo)
                count += 1
            else:
                sql += f"\n-- PARSE FAILED: {fname}\n"
        except Exception as e:
            sql += f"\n-- ERROR {fname}: {e}\n"
    return sql, count

def main():
    dry_run = '--run' not in sys.argv
    
    if not dry_run:
        # Verify DB exists
        if not os.path.exists(DB_PATH):
            print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
            sys.exit(1)
    
    sql = """-- Generated beneficiary data
BEGIN TRANSACTION;

"""
    total = 0
    errors = 0
    
    # Process EPI (individual resolutions)
    print("Processing EPI...", file=sys.stderr)
    epi_sql, epi_count = process_pdf_list(EPI_FILES, 'EPI', parse_epi_like, 'EPI')
    sql += epi_sql
    total += epi_count
    print(f"  => {epi_count} beneficiaries", file=sys.stderr)
    
    # Process EDI (individual resolutions)
    print("Processing EDI...", file=sys.stderr)
    edi_sql, edi_count = process_pdf_list(EDI_FILES, 'EDI', parse_epi_like, 'EDI')
    sql += edi_sql
    total += edi_count
    print(f"  => {edi_count} beneficiaries", file=sys.stderr)
    
    # Process EPA (individual resolutions)
    print("Processing EPA...", file=sys.stderr)
    epa_sql, epa_count = process_pdf_list(EPA_FILES, 'EPA', parse_epi_like, 'EPA')
    sql += epa_sql
    total += epa_count
    print(f"  => {epa_count} beneficiaries", file=sys.stderr)
    
    # Process Fallo Final PDFs (parse beneficiaries from table layout)
    print("Processing Fallo Final PDFs...", file=sys.stderr)
    fallo_total = 0
    for codigo, modalidades in FALLO_FILES.items():
        for modalidad, fname in modalidades:
            url = DOC4_BASE + fname
            try:
                flow_text, layout_text = download_and_extract(url)
                result = parse_fallo(flow_text, layout_text, url, codigo)
                if result and result.get('beneficiaries'):
                    sql += generate_fallo_inserts(result, codigo)
                    n = len(result['beneficiaries'])
                    fallo_total += n
                    print(f"  {fname}: {n} beneficiaries", file=sys.stderr)
                elif result:
                    sql += f"\n-- Fallo (no beneficiaries): {fname}\n"
                else:
                    sql += f"\n-- PARSE FAILED (fallo): {fname}\n"
            except Exception as e:
                sql += f"\n-- ERROR {fname}: {e}\n"
    total += fallo_total
    
    sql += "\nCOMMIT;\n"
    
    print(f"\nTotal: {total} beneficiaries, {errors} errors", file=sys.stderr)
    
    if dry_run:
        print(sql)
    else:
        sql_path = os.path.join(TMP_DIR, '_import.sql')
        with open(sql_path, 'w') as f:
            f.write(sql)
        subprocess.run(['sqlite3', DB_PATH], input=f".read {sql_path}\n", text=True)
        print(f"Data loaded into {DB_PATH}", file=sys.stderr)
        os.unlink(sql_path)

if __name__ == '__main__':
    main()
