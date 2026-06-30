#!/usr/bin/env python3
"""Extract beneficiary regions from FalloFinal PDFs and update persona.region."""
import sqlite3, subprocess, re, unicodedata, os, sys
from pathlib import Path

DB = Path.home() / "Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
CACHE_DIR = Path("/tmp/dafo_pdf_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64)"

KNOWN_REGIONS = [
    "AMAZONAS", "ANCASH", "APURIMAC", "APURÍMAC", "AREQUIPA", "AYACUCHO",
    "CAJAMARCA", "CALLAO", "CUSCO", "HUANCAVELICA", "HUANUCO", "HUÁNUCO",
    "ICA", "JUNIN", "JUNÍN", "LA LIBERTAD", "LAMBAYEQUE", "LIMA", "LORETO",
    "MADRE DE DIOS", "MOQUEGUA", "PASCO", "PIURA", "PUNO", "SAN MARTIN",
    "SAN MARTÍN", "TACNA", "TUMBES", "UCAYALI",
    "LIMA METROPOLITANA",
]

def normalize(s):
    return unicodedata.normalize("NFC", s)

def strip_accents(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")

REGION_PATTERNS = {strip_accents(r.upper()): r for r in sorted(KNOWN_REGIONS, key=len, reverse=True)}

# Secondary keys for multi-word regions that may span lines in -layout output
# (e.g. "LA\nLIBERTAD" won't match "LA LIBERTAD" in the text)
# Also for truncated words: "LIBERTA" + "\n" + "D" = "LIBERTAD"
REGION_PARTIALS = {
    'LIBERTAD': 'LA LIBERTAD',
    'LIBERTA': 'LA LIBERTAD',
    'LAMBAYEQU': 'LAMBAYEQUE',
    'MADRE': 'MADRE DE DIOS',
    'MARTIN': 'SAN MARTIN',
    'METROPOLITANA': 'LIMA METROPOLITANA',
    'HUANUCO': 'HUANUCO',
    'AYACUCHO': 'AYACUCHO',
}

# Province-level names that uniquely identify a department/region
# (used when the PDF shows province instead of department)
PROVINCE_TO_REGION = {
    'HUAURA': 'LIMA',
    'HUAROCHIRI': 'LIMA',
    'CAÑETE': 'LIMA',
    'BARRANCA': 'LIMA',
    'CALLA': 'CALLAO',  # "CALLA" + "O" over multiple lines = CALLAO
}

def _clean_name_for_search(name):
    """Clean a beneficiary name to generate search variants."""
    s = strip_accents(name.upper().strip())
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\[.*?\]', '', s)
    s = re.sub(r'CCI[^A-Z]*\d+', '', s)
    s = re.sub(r'DNI[^A-Z]*\d+', '', s)
    s = re.sub(r'\bLAMB\b', '', s)
    s = re.sub(r'\bLAM\b', '', s)
    s = re.sub(r'\s+L\s+', ' ', s)
    s = re.sub(r'\s+L$', '', s)
    s = re.sub(r'\bE\.I\.R\.L\b', '', s)
    s = re.sub(r'\bEIRL\b', '', s)
    s = re.sub(r'\bS\.A\.C\b', '', s)
    s = re.sub(r'\bSAC\b', '', s)
    s = re.sub(r'\bS\.R\.L\b', '', s)
    s = re.sub(r'\bSRL\b', '', s)
    s = re.sub(r'\bS\.AC\b', '', s)
    s = re.sub(r'[^A-Z\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    words = [w for w in s.split() if len(w) >= 3]
    return ' '.join(words), words

def _region_from_table(layout_text):
    """Extract a {beneficiary_key: region} map from a table with REGIÓN header."""
    text = normalize(layout_text)
    lines = text.split('\n')

    region_header_idx = -1
    region_col = -1
    name_col = -1
    for i, line in enumerate(lines):
        lu = strip_accents(line.upper())
        m = re.search(r'\bREGI[ÓO]N\b', lu)
        if m:
            region_header_idx = i
            region_col = m.start()
            nm = re.search(r'\bNATURAL\b|\bJUR[DÍI]DICA\b', lu)
            if nm and nm.start() < region_col:
                name_col = nm.start()
            break
    if region_col == -1:
        return {}

    # For single-beneficiary PDFs (EPI-style individual RDs), find ALL region
    # candidates in the table section and return the most likely one.
    # First, scan the table area for any known region name.
    result = {}
    current_name = []
    found_region = None

    for i in range(region_header_idx + 1, min(len(lines), region_header_idx + 60)):
        line = lines[i]
        lu = strip_accents(line.upper())
        stripped = line.strip()

        if not stripped:
            continue
        if re.match(r'^\s*(ART[CÍI]CULO|FIRMADO|DESPACHO|DIRECCI[ÓO]N|DECENIO)', lu):
            break

        # Collect name parts (left of region column)
        if name_col >= 0 and len(line) > name_col and len(line) > region_col:
            nv = line[:region_col].strip()
            if nv and len(nv) >= 2:
                nv_clean = re.sub(r'\(?\d{5,}.*', '', nv).strip()
                if nv_clean and len(nv_clean) >= 2:
                    current_name.append(strip_accents(nv_clean.upper()))

        # Check for region at column position
        if region_col < len(line):
            rv = line[region_col:region_col + 25].strip()
            rvu = strip_accents(rv.upper())
            rvu = re.sub(r'[^A-Z\s]', '', rvu).strip()
            if len(rvu) >= 4:
                for key, original in REGION_PATTERNS.items():
                    if rvu == key or rvu.startswith(key) or key.startswith(rvu):
                        found_region = original.title()
                        # Also need name from lines above within same table row
                        name_parts = []
                        for j in range(max(0, i - 8), i + 1):
                            nl = lines[j]
                            if name_col >= 0 and len(nl) > name_col:
                                nv = nl[:region_col].strip()
                                if nv and len(nv) >= 2:
                                    nv_clean = re.sub(r'\(?\d{5,}.*', '', nv).strip()
                                    if nv_clean and len(nv_clean) >= 2:
                                        name_parts.append(strip_accents(nv_clean.upper()))
                        if name_parts:
                            key_name = ' '.join(name_parts)
                            result[key_name] = found_region
                        break

    # Fallback: search for region names in the table section (from REGIÓN header
    # to end of table), handling multi-word regions that span lines.
    if not result:
        search_start = max(0, region_header_idx - 3)
        lower_text = '\n'.join(lines[search_start:])
        lower_upper = strip_accents(lower_text.upper())
        skip_words = {'AYACUCHO', 'JUNIN', 'JUNÍN'}
        found_regions = []
        for key, original in REGION_PATTERNS.items():
            if key in skip_words:
                continue
            if re.search(rf'(?<![A-Z]){re.escape(key)}(?![A-Z])', lower_upper):
                found_regions.append((key, original.title()))
        if len(found_regions) == 1:
            region = found_regions[0][1]
            # Verify it's not part of the table header (by checking position)
            result['_single_beneficiary'] = region
        elif len(found_regions) > 1:
            # Multiple regions found - take the one closest to the beneficiary name
            # that's not a common false positive
            for key, original in found_regions:
                pass
            # For now, skip if ambiguous

    return result

def _search_text_for_region(text_upper, text, known_regions):
    """Search entire text for known regions, excluding boilerplate false positives.
    Checks full names, partial keys (for line-split words), and province-level names."""
    skip_words = {'AYACUCHO', 'JUNIN', 'JUNÍN'}
    found = []

    # 1) Full region names
    for key, original in known_regions:
        if key in skip_words:
            continue
        if re.search(rf'(?<![A-Z]){re.escape(key)}(?![A-Z])', text_upper):
            found.append((key, original.title()))

    # 2) Partial keys (truncated/multi-line words)
    if not found:
        for partial_key, full_original in REGION_PARTIALS.items():
            full_key = strip_accents(full_original.upper())
            if full_key in skip_words:
                continue
            if re.search(rf'(?<![A-Z]){re.escape(partial_key)}(?![A-Z])', text_upper):
                found.append((full_key, full_original.title()))

    # 3) Province-level names (only if still nothing found)
    if not found:
        for province, region in PROVINCE_TO_REGION.items():
            if re.search(rf'(?<![A-Z]){re.escape(province)}(?![A-Z])', text_upper):
                found.append((region, region.title()))
    return found

def _find_region_in_pdf_text(layout_text, beneficiary_name):
    text = normalize(layout_text)
    text_upper = strip_accents(text.upper())
    known_regions_list = list(REGION_PATTERNS.items())

    # Try table extraction first
    table_map = _region_from_table(layout_text)
    if table_map:
        if '_single_beneficiary' in table_map:
            return table_map['_single_beneficiary']
        _, name_words = _clean_name_for_search(beneficiary_name)
        for key, region in table_map.items():
            key_clean, _ = _clean_name_for_search(key)
            for w in name_words:
                if len(w) >= 4 and w in key_clean:
                    return region

    cleaned, words = _clean_name_for_search(beneficiary_name)

    # Search strategies: try full cleaned name, then shorter variants
    strategies = [cleaned]
    for n in [1, 2, 3]:
        if len(words) >= n:
            s = ' '.join(words[:n])
            if len(s) >= 4 and s not in strategies:
                strategies.append(s)
    if len(words) >= 2:
        strategies.append(words[-1])

    # Check if beneficiary name appears ANYWHERE in the PDF
    name_found = False
    for strategy in strategies:
        if text_upper.find(strategy) != -1:
            name_found = True
            break

    if not name_found:
        return None

    # For single-beneficiary PDFs (name found), search the entire document
    # for region names (avoiding boilerplate false positives)
    all_regions = _search_text_for_region(text_upper, text, known_regions_list)
    if len(all_regions) == 1:
        return all_regions[0][1]
    elif len(all_regions) > 1:
        # Multiple regions found - check which is nearest to the beneficiary name
        ben_idx = text_upper.find(cleaned) if cleaned in text_upper else text_upper.find(words[0])
        if ben_idx >= 0:
            best_region = None
            best_dist = float('inf')
            for key, region in all_regions:
                r_pos = text_upper.find(key)
                dist = abs(r_pos - ben_idx)
                if dist < best_dist:
                    best_dist = dist
                    best_region = region
            return best_region

    # Fallback: narrow search around beneficiary name
    for strategy in strategies:
        idx = text_upper.find(strategy)
        if idx != -1:
            context = text[max(0, idx - 400):idx + 600]
            region = _find_region_nearby(context)
            if region:
                return region

    return None

def _find_region_nearby(text_sample):
    s = strip_accents(normalize(text_sample).upper())
    s = re.sub(r'[^A-Z\s]', ' ', s)
    # Full region names
    for key, original in REGION_PATTERNS.items():
        if re.search(rf'(?<![A-Z]){re.escape(key)}(?![A-Z])', s):
            return original.title()
    # Partial keys for line-split words
    for partial_key, full_original in REGION_PARTIALS.items():
        full_key = strip_accents(full_original.upper())
        if re.search(rf'(?<![A-Z]){re.escape(partial_key)}(?![A-Z])', s):
            return full_original.title()
    # Province-level names
    for province, region in PROVINCE_TO_REGION.items():
        if re.search(rf'(?<![A-Z]){re.escape(province)}(?![A-Z])', s):
            return region.title()
    return None

def extract_region_from_pdf(url_pdf, beneficiary_name):
    cache_path = CACHE_DIR / f"{hash(url_pdf)}.txt"
    if cache_path.exists():
        with open(cache_path) as f:
            layout_text = f.read()
    else:
        pdf_path = CACHE_DIR / f"{hash(url_pdf)}.pdf"
        try:
            subprocess.run(
                ['curl', '-sLk', '--max-time', '30', '-A', USER_AGENT, '-o', str(pdf_path), url_pdf],
                check=True, timeout=45, capture_output=True
            )
        except Exception:
            return None
        try:
            subprocess.run(
                ['pdftotext', '-layout', str(pdf_path), str(cache_path)],
                check=True, timeout=30, capture_output=True
            )
            with open(cache_path) as f:
                layout_text = f.read()
        except Exception:
            return None
        finally:
            if pdf_path.exists():
                pdf_path.unlink()

    return _find_region_in_pdf_text(layout_text, beneficiary_name)

def get_persona_key(pe):
    if pe['tipo'] == 'juridica':
        return pe['razon_social']
    return f"{pe['nombres'] or ''} {pe['apellidos'] or ''}".strip()

def main():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT pe.id, pe.tipo, pe.nombres, pe.apellidos, pe.razon_social
        FROM persona pe
        JOIN proyecto p ON p.persona_beneficiaria_id = pe.id
        JOIN proyecto_resolucion pr ON pr.proyecto_id = p.id
        JOIN resolucion r ON pr.resolucion_id = r.id
        WHERE (pe.region IS NULL OR pe.region = '' OR pe.region = 'SIN DATO')
          AND r.url_pdf IS NOT NULL
        ORDER BY pe.id
    """)

    rows = cur.fetchall()
    print(f"Beneficiarios sin región: {len(rows)}")

    updated = 0
    errors = 0

    for row in rows:
        key = get_persona_key(row)
        if not key:
            errors += 1
            continue

        cur.execute("""
            SELECT DISTINCT r.url_pdf FROM resolucion r
            JOIN proyecto_resolucion pr ON pr.resolucion_id = r.id
            JOIN proyecto p ON pr.proyecto_id = p.id
            WHERE p.persona_beneficiaria_id = ? AND r.url_pdf IS NOT NULL
        """, (row['id'],))
        pdfs = cur.fetchall()

        region = None
        for pdf_row in pdfs:
            url = pdf_row['url_pdf']
            region = extract_region_from_pdf(url, key)
            if region:
                break

        if region:
            cur.execute("UPDATE persona SET region = ? WHERE id = ?", (region.upper(), row['id']))
            conn.commit()
            updated += 1
            print(f"  ✓ {key[:55]:55s} → {region}")
        else:
            errors += 1
            print(f"  ✗ {key[:55]:55s} → no se encontró región")

    print(f"\nResumen: {updated} actualizados, {errors} sin región")
    conn.close()

if __name__ == "__main__":
    main()
