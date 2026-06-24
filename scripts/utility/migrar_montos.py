#!/usr/bin/env python3
"""
Migration script: fix anomalous amounts, duplicate resolution, and orphan resolutions.
Uses the fixed _parse_amount_str from the updated extract_2024.py.

Usage:
  python3 migrar_montos.py          # dry-run
  python3 migrar_montos.py --run    # apply changes
"""
import sys, os, re, sqlite3, subprocess, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db")
TMP_DIR = "/tmp/dafo_pdfs"
os.makedirs(TMP_DIR, exist_ok=True)

# Import fixed parser
from extract_2024 import _parse_amount_str, parse_fallo, parse_rd

ANOMALOUS_THRESHOLD = 1000

AFFECTED_RESOLUTIONS = [
    ("D000154-2019-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2019%20CGC%20-%20Fallo%20final.pdf", "fallo"),
    ("000501-2022-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2022-CDO-FalloFinal.pdf", "fallo"),
    ("000549-2022-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2022-CPA-FalloFinal.pdf", "fallo"),
    ("000585-2022-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2022-CDL-FalloFinalJurado.pdf", "fallo"),
    ("001153-2023-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2023-CCM-RD001153-2023-DGIA.pdf", "rd"),
    ("001011-2023-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2023-CFO-RD001011-2023-DGIA.pdf", "rd"),
    ("001165-2023-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2023-CPA-RD001165-2023-DGIA.pdf", "rd"),
    ("000970-2023-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2023-CFR-RD000970-2023-DGIA.pdf", "rd"),
    ("001051-2023-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2023-CFN-RD001051-2023-DGIA.pdf", "rd"),
    ("001089-2023-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2023-CFN-RD001089-2023-DGIA.pdf", "rd"),
    ("001144-2023-DGIA/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2023-CDS-RD001144-2023-DGIA.pdf", "rd"),
    ("000875-2024-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2024-CCM-FalloFinal.pdf", "fallo"),
    ("001152-2024-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2024-CDO-D-FalloFinalJurado.pdf", "fallo"),
    ("000861-2024-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2024-CDV-FalloFinal.pdf", "fallo"),
    ("000430-2024-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2024-EPI-RD000430%3A2024%3ADGIA%3AVMPCIC%3AMC.pdf", "rd"),
    ("000431-2024-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2024-EPI-RD000431%3A2024%3ADGIA%3AVMPCIC%3AMC.pdf", "rd"),
    ("001276-2024-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/2024-EPI-RD001276-2024-DAFO-DGIA-VMPCIC.pdf", "rd"),
    ("001110-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-CCE-FalloFinal.pdf", "fallo"),
    ("001053-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-CGC-FC-FalloFinal.pdf", "fallo"),
    ("001108-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-CIN-FalloFinal.pdf", "fallo"),
    ("001100-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-CPA-P-PP-DS-D-FalloFinal.pdf", "fallo"),
    ("001111-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-CPC-OP-FalloFinal_0.pdf", "fallo"),
    ("001124-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-EPA-RD001124-2025-DGIA-VMPCIC.pdf", "rd"),
    ("001125-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-EPA-RD001125-2025-DGIA-VMPCIC.pdf", "rd"),
    ("001126-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-EPA-RD001126-2025-DGIA-VMPCIC.pdf", "rd"),
    ("000938-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-EPI-RD000938-2025-DGIA-VMPCIC-MC.pdf", "rd"),
    ("000961-2025-DGIA-VMPCIC/MC", "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/doc-4/2025-EPI-RD000961-2025-DGIA-VMPCIC-MC.pdf", "rd"),
]


def get_proyectos_by_resolucion(conn, resol_num):
    cur = conn.execute("""
        SELECT po.id, po.monto_otorgado
        FROM proyecto po
        JOIN proyecto_resolucion pr ON pr.proyecto_id = po.id
        JOIN resolucion r ON r.id = pr.resolucion_id
        WHERE r.numero = ?
        ORDER BY po.id
    """, (resol_num,))
    return cur.fetchall()


def reparse_amounts(conn, dry_run=True):
    """Re-parse PDFs with anomalous amounts using the fixed parser."""
    fixes = []
    no_changes = []
    errors = []

    for res_num, pdf_url, pdf_type in AFFECTED_RESOLUTIONS:
        posts = get_proyectos_by_resolucion(conn, res_num)
        if not posts:
            continue
        old_amounts = {p[0]: p[1] for p in posts}

        config = {}
        try:
            if pdf_type == "fallo":
                result, err = parse_fallo(pdf_url, "2024", config)
            else:
                result, err = parse_rd(pdf_url, "", "2024", config)

            if err:
                errors.append(f"{res_num}: {err}")
                continue
            if not result or not result.get('beneficiaries'):
                errors.append(f"{res_num}: no beneficiaries found")
                continue

            # Map new amounts by proyecto order (they should match)
            new_beneficiaries = result['beneficiaries']
            if len(new_beneficiaries) != len(posts):
                errors.append(f"{res_num}: mismatch count (PDF={len(new_beneficiaries)}, DB={len(posts)})")
                continue

            for post_id, benef in zip([p[0] for p in posts], new_beneficiaries):
                new_amount = benef.get('monto', 0)
                old_amount = old_amounts[post_id]
                if abs(new_amount - old_amount) > 0.01 and new_amount > 0:
                    fixes.append((post_id, old_amount, new_amount, res_num))
                else:
                    no_changes.append((post_id, old_amount, new_amount, res_num))

        except Exception as e:
            errors.append(f"{res_num}: {e}")

    return fixes, no_changes, errors


def fix_duplicate_resolution(conn, dry_run=True):
    """Remove duplicate resolution 001167-2024-DGIA-VMPCIC/MC (ID 6246)."""
    cur = conn.execute("SELECT id, url_pdf FROM resolucion WHERE numero = '001167-2024-DGIA-VMPCIC/MC' ORDER BY id")
    rows = cur.fetchall()
    if len(rows) < 2:
        return f"No duplicate found (found {len(rows)} entries)", False

    # Keep first (combined PDF), remove second
    keep_id = rows[0][0]
    remove_id = rows[1][0]

    if dry_run:
        return f"DRY-RUN: Would remove resolucion id={remove_id} (keep id={keep_id})", True

    conn.execute("DELETE FROM proyecto_resolucion WHERE resolucion_id = ?", (remove_id,))
    conn.execute("DELETE FROM resolucion WHERE id = ?", (remove_id,))
    return f"Removed duplicate resolution id={remove_id}, kept id={keep_id}", True


def fix_orphan_resolutions(conn, dry_run=True):
    """Link orphan resolutions to their proyectos where possible, or mark them."""
    orphans = conn.execute("""
        SELECT r.id, r.numero, r.concurso_anual_id, lc.codigo
        FROM resolucion r
        JOIN concurso_anual ca ON ca.id = r.concurso_anual_id
        JOIN linea_concursable lc ON lc.id = ca.linea_concursable_id
        LEFT JOIN proyecto_resolucion pr ON pr.resolucion_id = r.id
        WHERE pr.proyecto_id IS NULL
    """).fetchall()

    actions = []
    for r_id, r_num, ca_id, codigo in orphans:
        actions.append(f"Resolution {r_num} ({codigo}): orphan (no proyectos linked)")
    return actions


def main():
    dry_run = '--run' not in sys.argv

    conn = sqlite3.connect(DB_PATH)

    print("=" * 60)
    print("STEP 1: Fixing anomalous amounts (re-parsing PDFs)")
    print("=" * 60)
    fixes, no_changes, errors = reparse_amounts(conn, dry_run)

    print(f"\n{len(fixes)} amounts to fix, {len(no_changes)} unchanged, {len(errors)} errors")
    if fixes:
        print("\nFixes:")
        for post_id, old, new, res_num in fixes[:20]:
            print(f"  post {post_id}: {old:>10.2f} → {new:>10.2f} ({res_num})")
        if len(fixes) > 20:
            print(f"  ... and {len(fixes)-20} more")

    if errors:
        print("\nErrors:")
        for e in errors[:10]:
            print(f"  {e}")
        if len(errors) > 10:
            print(f"  ... and {len(errors)-10} more")

    if not dry_run and fixes:
        for post_id, old, new, res_num in fixes:
            conn.execute("UPDATE proyecto SET monto_otorgado = ? WHERE id = ?", (new, post_id))
        print(f"\nApplied {len(fixes)} amount fixes")

    print(f"\n{'=' * 60}")
    print("STEP 2: Fixing duplicate resolution")
    print("=" * 60)
    msg, changed = fix_duplicate_resolution(conn, dry_run)
    print(f"  {msg}")

    print(f"\n{'=' * 60}")
    print("STEP 3: Orphan resolutions")
    print("=" * 60)
    actions = fix_orphan_resolutions(conn, dry_run)
    for a in actions:
        print(f"  {a}")
    if not actions:
        print("  None found")

    if not dry_run:
        conn.commit()
        print("\n✅ All changes committed.")
    else:
        print("\n⚠️  DRY RUN - no changes made. Use --run to apply.")

    conn.close()

    if not fixes and not errors and not changed:
        print("\n✅ No fixes needed.")


if __name__ == '__main__':
    main()
