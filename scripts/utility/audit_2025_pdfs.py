#!/usr/bin/env python3
"""
Audit 2025 DAFO PDFs: compare extracted beneficiaries against DB.
Re-parses every PDF and reports line-by-line discrepancies.
"""
import subprocess, re, sys, os, sqlite3
from pathlib import Path

DB = Path.home() / "Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
TMP = Path("/tmp/dafo_audit")
TMP.mkdir(parents=True, exist_ok=True)

DOC4 = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/"
PDF_BASE = "https://estimuloseconomicos.cultura.gob.pe"

# ============ Individual RD files (EPI, EDI, EPA) ============
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

# Fallo Final PDFs — each entry: (line_code, label, filename)
FALLO_PDFS = [
    ("CPF", "Desarrollo", "2025-CPF-D-FalloFinal.pdf"),
    ("CPF", "Nuevos realizadores", "2025-CPF-P-NR-FalloFinal.pdf"),
    ("CPF", "Regiones", "2025-CPF-P-R-Beneficiarios.pdf"),
    ("CPF", "Tercer largometraje", "2025-CPF-TL-FalloFinal.pdf"),
    ("CDO", "Producción", "2025-CDO-P-FalloFinal.pdf"),
    ("CDO", "Desarrollo", "2025-CDO-D-FalloFinal.pdf"),
    ("CPC", "Segunda obra", "2025-CPC-2da-FalloFinal.pdf"),
    ("CPC", "Ópera prima", "2025-CPC-OP-FalloFinal_0.pdf"),
    ("CPA", "Cortometrajes", "2025-CPA-C-FalloFinal.pdf"),
    ("CPA", "P-PP-DS-D", "2025-CPA-P-PP-DS-D-FalloFinal.pdf"),
    ("CDV", "", "2025-CDV-FalloFinal.pdf"),
    ("CGC", "FEM", "2025-CGC-FEM-Beneficiarios.pdf"),
    ("CGC", "FC", "2025-CGC-FC-FalloFinal.pdf"),
    ("CIC", "", "2025-CIC-FalloFinal.pdf"),
    ("CCC", "", "2025-CCC-FalloFinalJurado.pdf"),
    ("CCM", "", "2025-CCM-FalloFinal.pdf"),
    ("CDC", "", "2025-CDC-FalloFinal.pdf"),
    ("CGS", "", "2025-CGS-FalloFinal.pdf"),
    ("CFO", "", "2025-CFO-ActadeEvaluación.pdf"),
    ("CIN", "", "2025-CIN-FalloFinal.pdf"),
    ("CCE", "", "2025-CCE-FalloFinal.pdf"),
]


def dl_pdf(url):
    name = re.sub(r'[^a-zA-Z0-9]', '_', url.split('/')[-1])
    pdf = TMP / name
    txt = TMP / f"{name}.txt"
    if pdf.exists() and txt.exists():
        return txt.read_text(errors='replace')
    subprocess.run(['curl', '-sLk', '-o', str(pdf), url], check=True, timeout=30)
    subprocess.run(['pdftotext', str(pdf), str(txt)], check=True, timeout=30)
    return txt.read_text(errors='replace')


def count_individual_rd(text):
    """Count beneficiaries in an individual RD PDF (EPI/EDI/EPA)."""
    a1 = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|Artículo\s)', text, re.DOTALL)
    if not a1:
        return 0, "no Artículo Primero"
    a1_text = a1.group(1)
    if 'PERSONA NATURAL' in a1_text.upper():
        return 1, "natural (OK)"
    if 'PERSONA JURÍDICA' in a1_text.upper() or 'PERSONA JURIDICA' in a1_text.upper():
        return 1, "jurídica (OK)"
    return 0, "unexpected format"


def count_fallo_beneficiaries(text):
    """Count beneficiaries in a Fallo Final PDF."""
    a1_match = re.search(r'Artículo Primero[\.\s\-]+(.*?)(?:Artículo Segundo|Artículo\s)', text, re.DOTALL)
    if not a1_match:
        return 0, "no Artículo Primero"
    a1 = a1_match.group(1)
    # Count DNI patterns (8 digits, not part of larger number)
    dnis = re.findall(r'(?<!\d)(\d{8})(?!\d)', a1)
    if not dnis:
        # Maybe it's a jurídica table: count RUCs (11 digits)
        rucs = re.findall(r'(?<!\d)(\d{11})(?!\d)', a1)
        if rucs:
            return len(rucs), f"jurídica ({len(rucs)} RUCs)"
        # Try counting S/ amounts as proxy for rows
        amounts = re.findall(r'S/[\.\s]*[\d\s,]+[.,]\d{2}', a1)
        if amounts:
            return len(amounts), f"by amount ({len(amounts)})"
        return 0, "no DNI/RUC/amount found"
    return len(dnis), f"natural ({len(dnis)} DNIs)"


def get_db_counts():
    """Get project counts per line and per RD from the database."""
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    # Projects per line
    cur.execute("""
        SELECT lc.codigo, COUNT(*) as cnt
        FROM proyecto p
        JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
        JOIN convocatoria cv ON ca.convocatoria_id = cv.id
        JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
        WHERE cv.anio = 2025
        GROUP BY lc.codigo
        ORDER BY lc.codigo
    """)
    per_line = dict(cur.fetchall())
    # All RDs for 2025
    cur.execute("""
        SELECT r.id, r.numero, r.url_pdf, lc.codigo
        FROM resolucion r
        JOIN proyecto_resolucion rp ON r.id = rp.resolucion_id
        JOIN proyecto p ON rp.proyecto_id = p.id
        JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
        JOIN convocatoria cv ON ca.convocatoria_id = cv.id
        JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
        WHERE cv.anio = 2025
        GROUP BY r.id
        ORDER BY r.numero
    """)
    rds = {}
    for rid, rnum, rurl, rcod in cur.fetchall():
        rds.setdefault(rcod, []).append(f"{rnum} ({rid})")
    conn.close()
    return per_line, rds


print("=" * 70)
print("DAFO 2025 — Auditoría de Beneficiarios vs DB")
print("=" * 70)

db_per_line, db_rds = get_db_counts()

print(f"\nTotal en DB: {sum(db_per_line.values())} proyectos")
print()

# ============ EPI, EDI, EPA (individual RDs) ============
print("-" * 70)
print("RDs individuales (1 PDF = 1 beneficiario)")
print("-" * 70)
for label, files, codigo in [
    ("EPI", EPI_FILES, "EPI"),
    ("EDI", EDI_FILES, "EDI"),
    ("EPA", EPA_FILES, "EPA"),
]:
    pdf_count = 0
    errors = []
    for fname in files:
        url = DOC4 + fname
        try:
            text = dl_pdf(url)
            n, msg = count_individual_rd(text)
            if n == 1:
                pdf_count += 1
            else:
                errors.append(f"  {fname}: {msg}")
        except Exception as e:
            errors.append(f"  {fname}: ERROR {e}")
    db_cnt = db_per_line.get(codigo, 0)
    status = "✓ OK" if pdf_count == db_cnt else f"✗ MISMATCH"
    print(f"\n{codigo}:")
    print(f"  PDFs en lista: {len(files)}")
    print(f"  Parseados OK:  {pdf_count}")
    print(f"  En DB:         {db_cnt}")
    print(f"  Status:        {status}")
    if errors:
        for e in errors:
            print(f"  {e}")

# ============ Fallo Final PDFs ============
print("\n" + "-" * 70)
print("PDFs Fallo Final (1 PDF = N beneficiarios)")
print("-" * 70)

# Group by line code
from collections import defaultdict
fallo_by_line = defaultdict(list)
for codigo, label, fname in FALLO_PDFS:
    fallo_by_line[codigo].append((label, fname))

for codigo in sorted(fallo_by_line.keys()):
    total_pdf = 0
    details = []
    errors = []
    for label, fname in fallo_by_line[codigo]:
        url = DOC4 + fname
        try:
            text = dl_pdf(url)
            n, msg = count_fallo_beneficiaries(text)
            total_pdf += n
            details.append(f"    {label or fname}: {n} ({msg})")
        except Exception as e:
            errors.append(f"    {fname}: ERROR {e}")
    db_cnt = db_per_line.get(codigo, 0)
    # For CFO: don't compare against DB since it was manually inserted
    status = "✓ OK" if total_pdf == db_cnt else f"✗ GAP={db_cnt - total_pdf}" if db_cnt > total_pdf else f"✗ EXTRA={total_pdf - db_cnt}"
    if codigo == "CFO":
        status = "⚠ Manual (OCR DB)" if db_cnt > 0 else "⚠ No extraído"
    print(f"\n{codigo}:")
    for d in details:
        print(d)
    print(f"  Total PDF:     {total_pdf}")
    print(f"  En DB:         {db_cnt}")
    print(f"  Status:        {status}")
    if errors:
        for e in errors:
            print(f"  {e}")

# ============ Summary ============
print("\n" + "=" * 70)
print("RESUMEN")
print("=" * 70)

# Recalculate total from fresh parse
total_parsed = 0
for codigo, label, fname in FALLO_PDFS:
    url = DOC4 + fname
    try:
        text = dl_pdf(url)
        n, _ = count_fallo_beneficiaries(text)
        total_parsed += n
    except:
        pass

total_rd = 0
for files in [EPI_FILES, EDI_FILES, EPA_FILES]:
    for fname in files:
        url = DOC4 + fname
        try:
            text = dl_pdf(url)
            n, _ = count_individual_rd(text)
            total_rd += n
        except:
            pass

grand_total_parsed = total_parsed + total_rd
db_total = sum(db_per_line.values())
gap = db_total - grand_total_parsed

print(f"\nBeneficiarios extraídos de PDFs: {grand_total_parsed}")
print(f"  - Fallo Final:   {total_parsed}")
print(f"  - RDs indv.:     {total_rd}")
print(f"Proyectos en DB:   {db_total}")
print(f"Diferencia:        {gap}")
print(f"Esperado (oral):   215")
print(f"Gap vs 215:        {215 - db_total}")

# Check for CFO - it's a special case
print(f"\nNota: CFO ({db_per_line.get('CFO',0)}) fue insertado manualmente desde acta OCR.")
print(f"      El PDF oficial es RD000780-2025-DGIA-VMPCIC-MC.pdf (no en lista de extracción).")
