#!/usr/bin/env python3
"""
V2: Fix anomalous amounts by re-extracting amounts from PDF text directly,
preserving the existing beneficiary structure in the DB.
"""
import re, sys, os, sqlite3, subprocess, urllib.parse

DB_PATH = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")
TMP_DIR = "/tmp/dafo_pdfs"
os.makedirs(TMP_DIR, exist_ok=True)


def _parse_amount_str(am_str):
    am_str = am_str.replace(' ', '')
    if ',' in am_str and '.' in am_str:
        if am_str.rfind(',') > am_str.rfind('.'):
            am_str = am_str.replace('.', '').replace(',', '.')
        else:
            am_str = am_str.replace(',', '')
    elif ',' in am_str:
        am_str = am_str.replace(',', '.')
    return float(am_str)


def extract_amounts_from_pdf(pdf_url):
    """Download PDF, convert to text, extract all S/ amounts, return sorted by position."""
    pdf_name = re.sub(r'[^a-zA-Z0-9]', '_', pdf_url.split('/')[-1])[:80]
    pdf_path = os.path.join(TMP_DIR, pdf_name)
    txt_path = pdf_path + "_layout.txt"

    if not os.path.exists(pdf_path):
        subprocess.run(['curl', '-sLk', '--max-time', '30', '-o', pdf_path, pdf_url], check=True, timeout=45)
    subprocess.run(['pdftotext', '-layout', pdf_path, txt_path], check=True, timeout=30)

    with open(txt_path) as f:
        layout_text = f.read()

    # Clean up
    for p in [pdf_path, txt_path]:
        try: os.unlink(p)
        except: pass

    # Find all amount lines with their positions
    amounts = []
    for i, line in enumerate(layout_text.split('\n')):
        for m in re.finditer(r'S/?\.?\s*([\d\s,]+[.,]\d{2})', line):
            try:
                val = _parse_amount_str(m.group(1))
                amounts.append((i, m.start(), val))
            except ValueError:
                pass

    # Find amounts from the Artículo Primero / RESUELVE section
    a1_start = -1
    for pattern in [r'ART[ÍI]CULO PRIMERO', r'Artículo Primero', r'SE RESUELVE:', r'RESUELVE:']:
        m = re.search(pattern, layout_text)
        if m:
            a1_start = m.start()
            break

    if a1_start < 0:
        a1_start = 0

    # Filter: only amounts >= 100 (skip small numbers like page numbers, years)
    a1_amounts = sorted([(line, col, val) for line, col, val in amounts if val >= 100])
    a1_area = sorted([(line, col, val) for line, col, val in amounts if val >= 100 and line >= layout_text[:a1_start].count('\n') - 5])

    # Return amounts found in the main body (after article first)
    return [v for _, _, v in a1_area]


def main():
    dry_run = '--run' not in sys.argv
    conn = sqlite3.connect(DB_PATH)

    # Get all anomalous proyectos grouped by resolution
    rows = conn.execute("""
        SELECT po.id, po.monto_otorgado, r.numero, r.url_pdf, lc.codigo, conv.anio
        FROM proyecto po
        JOIN concurso_anual ca ON ca.id = po.concurso_anual_id
        JOIN convocatoria conv ON conv.id = ca.convocatoria_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        WHERE po.monto_otorgado > 0 AND po.monto_otorgado < 1000
        ORDER BY r.numero, po.id
    """).fetchall()

    # Group by resolution
    from collections import OrderedDict
    groups = OrderedDict()
    for post_id, old_monto, res_num, pdf_url, codigo, anio in rows:
        groups.setdefault(res_num, {'url': pdf_url, 'codigo': codigo, 'anio': anio, 'posts': []})
        groups[res_num]['posts'].append((post_id, old_monto))

    fixes = []
    errors = []
    skips = []

    for res_num, info in groups.items():
        pdf_url = info['url']
        posts = info['posts']
        print(f"\n{res_num} ({info['codigo']} {info['anio']}): {len(posts)} posts...", file=sys.stderr)

        try:
            amounts = extract_amounts_from_pdf(pdf_url)
            # Skip amounts that are clearly budget totals (very large)
            amounts = [a for a in amounts if a < 2000000]

            print(f"  Found {len(amounts)} valid amounts: {[f'{a:.0f}' for a in amounts[:15]]}{'...' if len(amounts)>15 else ''}", file=sys.stderr)

            if len(amounts) < len(posts):
                errors.append(f"{res_num}: not enough amounts ({len(amounts)} < {len(posts)} posts)")
                continue

            # Match amounts to posts in order
            for i, (post_id, old_monto) in enumerate(posts):
                new_monto = amounts[i] if i < len(amounts) else old_monto
                if abs(new_monto - old_monto) > 0.01 and new_monto > 0:
                    fixes.append((post_id, old_monto, new_monto, res_num))

        except Exception as e:
            errors.append(f"{res_num}: {e}")

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Results: {len(fixes)} fixes, {len(errors)} errors", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    if fixes:
        print("\nFixes:", file=sys.stderr)
        for post_id, old, new, res_num in fixes:
            print(f"  post {post_id}: {old:>10.2f} → {new:>10.2f} ({res_num})", file=sys.stderr)

    if errors:
        print("\nErrors:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)

    # Duplicate resolution fix
    print(f"\n{'='*60}", file=sys.stderr)
    print("Duplicate resolution:", file=sys.stderr)
    dup = conn.execute("SELECT id, url_pdf FROM resolucion WHERE numero = '001167-2024-DGIA-VMPCIC/MC' ORDER BY id").fetchall()
    if len(dup) >= 2:
        print(f"  Would remove id={dup[1][0]}, keep id={dup[0][0]}", file=sys.stderr)

    # Orphan resolutions
    print(f"\n{'='*60}", file=sys.stderr)
    print("Orphan resolutions:", file=sys.stderr)
    orphans = conn.execute("""
        SELECT r.id, r.numero, lc.codigo, conv.anio
        FROM resolucion r
        JOIN concurso_anual ca ON ca.id = r.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        JOIN convocatoria conv ON conv.id = ca.convocatoria_id
        LEFT JOIN proyecto_resolucion pr ON pr.resolucion_id = r.id
        WHERE pr.proyecto_id IS NULL
        ORDER BY conv.anio
    """).fetchall()
    for r_id, r_num, codigo, anio in orphans:
        print(f"  {r_num} ({codigo} {anio}, id={r_id})", file=sys.stderr)

    # Apply fixes
    if not dry_run:
        for post_id, old, new, res_num in fixes:
            conn.execute("UPDATE proyecto SET monto_otorgado = ? WHERE id = ?", (new, post_id))
        if len(dup) >= 2:
            conn.execute("DELETE FROM proyecto_resolucion WHERE resolucion_id = ?", (dup[1][0],))
            conn.execute("DELETE FROM resolucion WHERE id = ?", (dup[1][0],))
        conn.commit()
        print(f"\n✅ Applied {len(fixes)} fixes, removed duplicate {dup[1][0] if len(dup)>=2 else 'N/A'}", file=sys.stderr)
    else:
        print(f"\n⚠️  Dry run. Use --run to apply.", file=sys.stderr)

    conn.close()

    # Return fixes for display
    return fixes


if __name__ == '__main__':
    fixes = main()
    # Print summary to stdout for the user
    print(f"\n{'='*60}")
    print(f"MIGRATION SUMMARY")
    print(f"{'='*60}")
    print(f"Amounts fixed: {len(fixes)}")
    for post_id, old, new, res_num in fixes[:20]:
        print(f"  post {post_id}: S/ {old:.2f} → S/ {new:.2f}")
    if len(fixes) > 20:
        print(f"  ... and {len(fixes)-20} more")
