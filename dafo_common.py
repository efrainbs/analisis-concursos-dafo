#!/usr/bin/env python3
"""
Shared utilities for DAFO extraction pipelines.
"""

import os
import re
import sqlite3

DB_PATH = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")
TMP_DIR = "/tmp/dafo_pdfs"

REGIONS = ['LIMA', 'CALLAO', 'AREQUIPA', 'CUSCO', 'LA LIBERTAD', 'PUNO', 'LAMBAYEQUE',
           'PIURA', 'CAJAMARCA', 'JUNÍN', 'JUNIN', 'SAN MARTÍN', 'SAN MARTIN', 'LORETO',
           'AYACUCHO', 'HUÁNUCO', 'HUANUCO', 'ANCASH', 'TACNA', 'ICA', 'MADRE DE DIOS',
           'PASCO', 'AMAZONAS', 'MOQUEGUA', 'TUMBES', 'UCAYALI', 'APURÍMAC', 'APURIMAC',
           'HUANCAVELICA']

REGION_NAMES_UPPER = {r.upper() for r in REGIONS if len(r) >= 3}

FALLO_HEADER_KEYWORDS = ['PERSONA', 'JURÍDICA', '(RUC)', 'REGIÓN', 'TITULO', 'TÍTULO', 'PROYECTO',
                         'CATEGORÍA', 'DIRECTOR', 'RESPONSABLE', 'MONTO', 'OTORGADO',
                         'INSTITUCIÓN', 'INSTITUCION', 'EDUCATIVA', 'PROGRAMA', 'FORMACIÓN',
                         'EVENTO', 'INTERNACIONAL', 'OBRA', 'VINCULADA', 'VINCULADO',
                         'CÓDIGO', 'CODIGO', 'CÓD.', 'COD.', 'NATURAL']


def _parse_amount_str(am_str):
    """Parse amount string handling Peruvian (1.234,56) and International (1,234.56) formats."""
    am_str = am_str.replace(' ', '')
    if ',' in am_str and '.' in am_str:
        if am_str.rfind(',') > am_str.rfind('.'):
            am_str = am_str.replace('.', '').replace(',', '.')
        else:
            am_str = am_str.replace(',', '')
    elif ',' in am_str:
        am_str = am_str.replace(',', '.')
    return float(am_str)


def extract_rd_num(text):
    m = re.search(r'RESOLUCION DIRECTORAL N[°º]\s*([\d\-A-Z/]+)', text)
    return m.group(1).strip() if m else ''


def extract_fecha(text):
    m = re.search(r'San Borja,\s*(\d+)\s+de\s+(\w+)\s+del\s+(\d{4})', text)
    if m:
        meses = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05',
                 'junio': '06', 'julio': '07', 'agosto': '08', 'septiembre': '09',
                 'setiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
        mes = meses.get(m.group(2).lower(), '01')
        return f"{m.group(3)}-{mes}-{m.group(1).zfill(2)}"
    return ''


def q(s):
    """Quote a string for SQL (legacy). Prefer parameterized queries."""
    if s is None:
        return 'NULL'
    if s == '':
        return "''"
    return "'" + str(s).replace("'", "''") + "'"


def get_concurso_anual_id(codigo, convocatoria_id=None, anio=None):
    """Look up concurso_anual.id by line code and year."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if convocatoria_id:
        c.execute("""
            SELECT ca.id FROM concurso_anual ca
            JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
            WHERE lc.codigo = ? AND ca.convocatoria_id = ?
        """, (codigo, convocatoria_id))
    elif anio:
        c.execute("""
            SELECT ca.id FROM concurso_anual ca
            JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
            JOIN convocatoria cv ON ca.convocatoria_id = cv.id
            WHERE lc.codigo = ? AND cv.anio = ?
        """, (codigo, anio))
    else:
        conn.close()
        return None
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_modalidad_id(concurso_anual_id, nombre):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM modalidad WHERE concurso_anual_id = ? AND nombre = ?",
              (concurso_anual_id, nombre))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def resolve_region(name):
    """Resolve a (possibly truncated) region name to its canonical form."""
    if not name or len(name) < 3:
        return ''
    name_u = name.upper()
    for r in sorted(REGIONS, key=len, reverse=True):
        ru = r.upper()
        if name_u == ru or (len(name) >= 4 and ru.startswith(name_u)):
            return r
        if len(ru) >= 6 and len(name_u) >= 4 and name_u in ru:
            return r
    return ''


def find_region(text):
    """Find the first known region name in text."""
    upper = text.upper()
    for r in sorted(REGIONS, key=len, reverse=True):
        if r.upper() in upper:
            return r
    return ''


def split_name(full_name):
    """Split a full name into (nombres, apellidos) heuristically.
    Handles comma-separated (Apellidos, Nombres) and standard Peruvian format
    (Nombres ApellidoPaterno ApellidoMaterno).
    """
    name = full_name.strip()
    if not name:
        return ('', '')
    name = name.rstrip(';.,')
    if ',' in name:
        ap, nom = name.split(',', 1)
        return (nom.strip(), ap.strip())
    parts = name.split()
    if len(parts) <= 2:
        if len(parts) == 1:
            return (parts[0], '')
        return (parts[0], parts[1])
    if len(parts) >= 4:
        nombres = ' '.join(parts[:-2])
        apellidos = ' '.join(parts[-2:])
    else:
        nombres = ' '.join(parts[:-1])
        apellidos = parts[-1]
    return (nombres, apellidos)
