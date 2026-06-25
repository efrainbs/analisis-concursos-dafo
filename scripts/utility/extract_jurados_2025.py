#!/usr/bin/env python3
"""
Extract jurado (jury) data from 2025 FalloFinal PDFs and insert into DB.

Usage:
    python scripts/utility/extract_jurados_2025.py [--dry-run]
"""

import os, re, sqlite3, subprocess, sys, unicodedata, hashlib
from collections import defaultdict

DB = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")
CACHE = "/tmp/jurado_pdfs_2025"
DRY_RUN = "--dry-run" in sys.argv

os.makedirs(CACHE, exist_ok=True)

FILENAME_MAP = {
    "2025-CPF-D-FalloFinal.pdf":         (14, 1),
    "2025-CPF-P-NR-FalloFinal.pdf":      (14, 2),
    "2025-CPF-P-R-Beneficiarios.pdf":    (14, 3),
    "2025-CPF-TL-FalloFinal.pdf":        (14, 4),
    "2025-CDO-P-FalloFinal.pdf":         (5, 6),
    "2025-CDO-D-FalloFinal.pdf":         (5, 5),
    "2025-CPC-2da-FalloFinal.pdf":       (13, 8),
    "2025-CPC-OP-FalloFinal_0.pdf":      (13, 7),
    "2025-CPA-C-FalloFinal.pdf":         (12, 9),
    "2025-CPA-P-PP-DS-D-FalloFinal.pdf": (12, 170),
    "2025-CDV-FalloFinal.pdf":           (6, None),
    "2025-CGC-FC-FalloFinal.pdf":        (8, 17),
    "2025-CGC-FEM-Beneficiarios.pdf":    (8, 16),
    "2025-CIC-FalloFinal.pdf":           (10, None),
    "2025-CCC-FalloFinalJurado.pdf":     (1, None),
    "2025-CCM-FalloFinal.pdf":           (3, None),
    "2025-CDC-FalloFinal.pdf":           (4, None),
    "2025-CGS-FalloFinal.pdf":           (9, None),
    "2025-CIN-FalloFinal.pdf":           (11, None),
    "2025-CCE-FalloFinal.pdf":           (2, None),
    "RD000780-2025-DGIA-VMPCIC-MC.pdf":  (7, None),
}


def get_pdf_text(url):
    h = hashlib.md5(url.encode()).hexdigest()
    txt = os.path.join(CACHE, f"{h}.txt")
    if os.path.exists(txt):
        with open(txt, encoding="utf-8") as f:
            return unicodedata.normalize("NFC", f.read())
    pdf = os.path.join(CACHE, f"{h}.pdf")
    subprocess.run(
        ["curl", "-sLk", "--max-time", "45", "-o", pdf, url],
        capture_output=True, timeout=50
    )
    if not os.path.exists(pdf) or os.path.getsize(pdf) < 1000:
        return ""
    r = subprocess.run(
        ["pdftotext", "-layout", pdf, "-"],
        capture_output=True, text=True, timeout=30
    )
    t = unicodedata.normalize("NFC", r.stdout)
    with open(txt, "w", encoding="utf-8") as f:
        f.write(t)
    return t


def _remove_header_lines(text):
    lines = text.split("\n")
    clean = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if re.match(r"^Firmado digitalmente por", s):
            continue
        if "FAU" in s and any(x in s for x in ["soft", "Cargo:", "Motivo:", "Fecha:"]):
            continue
        if "copia auténtica imprimible" in s.lower():
            continue
        if "validadorDocumental" in s:
            continue
        if "DESPACHO VICEMINISTERIAL" in s:
            continue
        if "DIRECCIÓN GENERAL DE" in s or "DIRECCION GENERAL DE" in s:
            continue
        if "PATRIMONIO CULTURAL" in s or "INDUSTRIAS CULTURALES" in s:
            continue
        if re.match(r'^["\'](?:Decenio|Año)', s):
            continue
        if "San Borja" in s and "del" in s:
            continue
        if "RESOLUCION DIRECTORAL" in s:
            continue
        if re.match(r"^\d{1,3}$", s):
            continue
        clean.append(s)
    return "\n".join(clean)


def collapse_text(text):
    """Collapse multi-line text into a single line by removing leading whitespace."""
    lines = text.split("\n")
    collapsed = " ".join(line.strip() for line in lines if line.strip())
    collapsed = re.sub(r"\s+", " ", collapsed)
    return collapsed


def find_jurado_paragraph(text):
    text = _remove_header_lines(text)
    start_idx = text.find("designa como miembros del Jurado")
    if start_idx == -1:
        return None

    after_designa = text[start_idx:]

    m = re.search(
        r"\ba\s+(?=[A-ZÑÁÉÍÓÚÜ][a-zñáéíóúü]+\s+[A-ZÑÁÉÍÓÚÜa-zñáéíóúü]+,\s*[a-z])",
        after_designa
    )
    if not m:
        m = re.search(r"\ba\s+(?=[A-ZÑÁÉÍÓÚÜ])", after_designa)
    if not m:
        return None

    jurado_start = m.end()

    end_m = re.search(
        r"(?:\n\s*Que,\s|\n\s*SE RESUELVE|\n\s*Artículo|\n\s*RESOLUCIÓN|\n\s*VISTO|\n\s*Considerando)",
        after_designa[jurado_start:]
    )
    if end_m:
        jurado_text = after_designa[jurado_start:jurado_start + end_m.start()]
    else:
        jurado_text = after_designa[jurado_start:].split("\n\n")[0] if "\n\n" in after_designa[jurado_start:] else after_designa[jurado_start:]

    jurado_text = re.sub(r"^[\s'\"“”‘’;,]+", "", jurado_text)
    jurado_text = collapse_text(jurado_text)

    return jurado_text.strip().rstrip(".;,")


def fix_merged_names(text):
    """Fix PDF extraction where names merge without space: 'MoryMaría' -> 'Mory María'"""
    text = re.sub(r"([a-zñáéíóúü])([A-ZÑÁÉÍÓÚÜ])", r"\1 \2", text)
    return text

# Manual fixes for known PDF extraction artifacts (merged names across lines)
MANUAL_NAME_SPLITS = {
    "Raúl Alberto Ortíz Mory María Inés Seijas Cao": [
        "Raúl Alberto Ortíz Mory",
        "María Inés Seijas Cao",
    ],
}


def parse_jurados(jurado_text):
    jurado_text = fix_merged_names(jurado_text)

    parts = [p.strip() for p in re.split(r";\s+", jurado_text) if p.strip()]

    results = []
    for part in parts:
        part = re.sub(r"^[yY]\s*,\s*", "", part).strip()
        if not part:
            continue

        part = re.sub(r"^[yY]\s+(?=[A-Z])", "", part).strip()
        if not part:
            continue

        sub_parts = [part]
        for sp in list(sub_parts):
            idx = sub_parts.index(sp)
            m = re.search(r",\s+y\s+(?=[A-ZÑÁÉÍÓÚÜ][a-zñáéíóúüé])", sp)
            if m:
                first = sp[:m.start()].strip()
                second = sp[m.end():].strip()
                sub_parts[idx:idx + 1] = [first, second]

        for sp in sub_parts:
            sp = sp.strip().rstrip(".;,")
            if not sp:
                continue

            comma_idx = sp.find(", ")
            if comma_idx > 0:
                name = sp[:comma_idx].strip()
                cargo = sp[comma_idx + 2:].strip()
            else:
                name = sp
                cargo = ""
            if not name:
                continue

            # Apply manual name splits for known merged-name artifacts
            if name in MANUAL_NAME_SPLITS:
                for n in MANUAL_NAME_SPLITS[name]:
                    results.append((n, cargo))
                continue

            results.append((name, cargo))

    return results


def split_name(full_name):
    name = full_name.strip().rstrip(";.,")
    if not name:
        return ("", "")
    if "," in name:
        ap, nom = name.split(",", 1)
        return (nom.strip(), ap.strip())
    parts = name.split()
    if len(parts) <= 2:
        if len(parts) == 1:
            return (parts[0], "")
        return (parts[0], parts[1])
    if len(parts) >= 4:
        return (" ".join(parts[:-2]), " ".join(parts[-2:]))
    return (" ".join(parts[:-1]), parts[-1])


def find_or_create_persona(conn, name, cargo=""):
    cur = conn.cursor()
    nombres, apellidos = split_name(name)

    if apellidos:
        cur.execute(
            "SELECT id FROM persona WHERE tipo='natural' AND nombres = ? AND apellidos = ?",
            (nombres, apellidos)
        )
    else:
        cur.execute(
            "SELECT id FROM persona WHERE tipo='natural' AND nombres = ?",
            (nombres,)
        )
    row = cur.fetchone()
    if row:
        return row[0]

    name_parts = name.split()
    if len(name_parts) >= 2 and len(name) >= 8:
        first_prefix = name_parts[0][:4]
        last_suffix = name_parts[-1][:4]
        cur.execute(
            "SELECT id, nombres, apellidos FROM persona WHERE tipo='natural' AND nombres LIKE ? AND apellidos LIKE ?",
            (f"{first_prefix}%", f"%{last_suffix}")
        )
        rows = cur.fetchall()
        matched = [r for r in rows
                   if r["nombres"].lower().startswith(first_prefix.lower())
                   and r["apellidos"].lower().endswith(last_suffix.lower())]
        if len(matched) == 1:
            return matched[0]["id"]

    if DRY_RUN:
        return None

    cur.execute(
        "INSERT INTO persona (tipo, nombres, apellidos, region) VALUES ('natural', ?, ?, '')",
        (nombres, apellidos)
    )
    conn.commit()
    return cur.lastrowid


def process_pdf(url, concurso_anual_id, modalidad_id, line_code, filename):
    print(f"  PDF: {filename}")
    text = get_pdf_text(url)
    if not text:
        print(f"    [ERROR] Could not download PDF")
        return []

    jurado_text = find_jurado_paragraph(text)
    if not jurado_text:
        print(f"    [WARN] No jurado paragraph found")
        return []

    jurados = parse_jurados(jurado_text)
    if not jurados:
        print(f"    [WARN] Could not parse jurados from text")
        return []

    print(f"    Found {len(jurados)} jurado members")
    for name, cargo in jurados:
        print(f"      {name:42s} → {cargo}")

    return [(concurso_anual_id, modalidad_id, name, cargo) for name, cargo in jurados]


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if DRY_RUN:
        print("=" * 60)
        print("DRY RUN MODE — no changes will be made")
        print("=" * 60)

    cur.execute("""
        SELECT r.id, r.numero, r.url_pdf, ca.id as concurso_anual_id,
               lc.codigo, ca.nombre_usado
        FROM resolucion r
        JOIN concurso_anual ca ON ca.id = r.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        WHERE c.anio = 2025 AND r.tipo = 'fallo_final'
        GROUP BY r.url_pdf
        ORDER BY lc.codigo, r.numero
    """)
    rows = cur.fetchall()

    print(f"\nFound {len(rows)} unique FalloFinal PDFs for 2025\n")

    all_jurados = []
    pdfs_without = []
    pdfs_with_error = []

    for row in rows:
        url = row["url_pdf"]
        ca_id = row["concurso_anual_id"]
        codigo = row["codigo"]
        nombre = row["nombre_usado"]
        fname = url.split("/")[-1]

        print(f"{'─'*60}")
        print(f"┃ {codigo}: {nombre}")
        print(f"{'─'*60}")

        entry = FILENAME_MAP.get(fname)
        if entry is None:
            for key, val in FILENAME_MAP.items():
                if key in url or key in fname:
                    entry = val
                    break
        if entry is None:
            print(f"    [SKIP] Unknown filename: {fname}")
            pdfs_without.append((codigo, fname, "unknown filename"))
            continue

        expected_ca_id, modalidad_id = entry

        try:
            jurados = process_pdf(url, ca_id, modalidad_id, codigo, fname)
            if not jurados:
                pdfs_without.append((codigo, fname, "no jurados parsed"))
            else:
                all_jurados.extend(jurados)
        except Exception as e:
            print(f"    [ERROR] {e}")
            pdfs_with_error.append((codigo, fname, str(e)))

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"PDFs processed: {len(rows)}")
    print(f"Total jurados found: {len(all_jurados)}")

    if pdfs_without:
        print(f"\nPDFs without jurado data:")
        for codigo, fname, reason in pdfs_without:
            print(f"  {codigo} - {fname}: {reason}")

    if pdfs_with_error:
        print(f"\nPDFs with errors:")
        for codigo, fname, error in pdfs_with_error:
            print(f"  {codigo} - {fname}: {error}")

    if not all_jurados:
        print("\nNo jurados to insert. Exiting.")
        conn.close()
        return

    if not DRY_RUN:
        print(f"\n{'='*60}")
        print("INSERTING INTO DATABASE")
        print(f"{'='*60}")

    cur.execute("""
        SELECT j.concurso_anual_id, j.modalidad_id, j.persona_id, j.cargo,
               p.nombres, p.apellidos
        FROM jurado j
        JOIN persona p ON p.id = j.persona_id
        JOIN concurso_anual ca ON ca.id = j.concurso_anual_id
        JOIN convocatoria c ON c.id = ca.convocatoria_id
        WHERE c.anio = 2025
    """)
    existing = cur.fetchall()
    if existing:
        print(f"\nExisting jurado records for 2025: {len(existing)}")
        for e in existing:
            print(f"  CA={e['concurso_anual_id']} M={e['modalidad_id']} "
                  f"PID={e['persona_id']} {e['nombres']} {e['apellidos']} - {e['cargo']}")

    by_concurso = defaultdict(list)

    for ca_id, modalidad_id, name, cargo in all_jurados:
        persona_id = find_or_create_persona(conn, name, cargo)
        if persona_id is None:
            if DRY_RUN:
                by_concurso[ca_id].append((name, cargo, None))
                continue
            continue

        mod_for_check = modalidad_id if modalidad_id else 0
        cur.execute(
            "SELECT 1 FROM jurado WHERE concurso_anual_id = ? AND "
            "COALESCE(modalidad_id, 0) = ? AND persona_id = ? AND cargo = ?",
            (ca_id, mod_for_check, persona_id, cargo)
        )
        already_exists = cur.fetchone()

        if DRY_RUN:
            mod_s = f" modalidad={modalidad_id}" if modalidad_id else ""
            label = "DUPLICATE" if already_exists else "INSERT"
            print(f"  [DRY-RUN] {label} jurado: ca={ca_id}{mod_s} persona={persona_id} ({name}) cargo='{cargo}'")
            by_concurso[ca_id].append((name, cargo, "duplicate" if already_exists else persona_id))
            continue

        if already_exists:
            by_concurso[ca_id].append((name, cargo, "duplicate"))
            continue

        cur.execute(
            "INSERT INTO jurado (concurso_anual_id, modalidad_id, persona_id, cargo) "
            "VALUES (?, ?, ?, ?)",
            (ca_id, modalidad_id, persona_id, cargo)
        )
        by_concurso[ca_id].append((name, cargo, persona_id))
        conn.commit()

    print(f"\n{'='*60}")
    print("RESULTS BY CONCURSO")
    print(f"{'='*60}")
    for ca_id in sorted(by_concurso.keys()):
        cur.execute("""
            SELECT lc.codigo, ca.nombre_usado
            FROM concurso_anual ca
            JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
            WHERE ca.id = ?
        """, (ca_id,))
        info = cur.fetchone()
        code = info["codigo"] if info else "?"
        jurados_list = by_concurso[ca_id]
        new_count = sum(1 for j in jurados_list if j[2] not in (None, "duplicate"))
        dup_count = sum(1 for j in jurados_list if j[2] == "duplicate")
        print(f"\n{code} (CA#{ca_id}): {len(jurados_list)} jurados ({new_count} new)")
        for name, cargo, pid in jurados_list:
            if pid and pid != "duplicate":
                pid_str = f"PID={pid}"
            elif pid == "duplicate":
                continue
            else:
                pid_str = "info"
            print(f"  {name:42s} {cargo:45s} ({pid_str})")

    if DRY_RUN:
        print(f"\n{'='*60}")
        print("DRY RUN — no changes were made")
        print("Run without --dry-run to insert into DB")
        print(f"{'='*60}")
    else:
        total = sum(1 for v in by_concurso.values() for j in v if j[2] not in (None, "duplicate"))
        print(f"\n{'='*60}")
        print(f"Done — {total} jurados inserted")
        print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    main()
