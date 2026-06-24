#!/usr/bin/env python3
"""Auditoría 2019-2023: inserta beneficiarios de PDFs faltantes.

Reutiliza parse_fallo/parse_rd de extract_2024.py con mapeo CORRECTO
(arregla bug donde 2020-CDI-FalloFinal.pdf estaba mapeado a CDL pero es CIN).

No borra nada: usa INSERT ... WHERE NOT EXISTS / INSERT OR IGNORE.
"""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_2024 import parse_fallo, parse_rd, generate_sql, YEAR_CONFIG

DB = os.path.expanduser('~/Projects/Analisis_Concursos_DAFO/concursos_dafo.db')

BASE = 'https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/'

# (filename, año, code_correcto, modalidad, tipo)
# code_correcto = línea concursable real según contenido del PDF
PDFS = [
    # 2020 — CIN (bug mapeo: extract_2024.py lo tenía como CDL)
    ('2020-CDI-FalloFinal.pdf', '2020', 'CIN', '', 'fallo_final'),
    # 2020 — CDL (Cine en Construcción de Largometraje)
    ('2020-CLC-FalloFinal.pdf', '2020', 'CDL', '', 'fallo_final'),
    # 2020 — EDI RDs individuales (6 RDs, una beneficiaria c/u)
    ('2020%20EDI%20RD%20000348-2020-DGIA-MC_1.pdf', '2020', 'EDI', '', 'resolucion_beneficiario'),
    ('2020%20EDI%20RD%20000369-2020-DGIA-MC.pdf', '2020', 'EDI', '', 'resolucion_beneficiario'),
    ('2020%20EDI%20RD%20000377-2020-DGIA-MC.pdf', '2020', 'EDI', '', 'resolucion_beneficiario'),
    ('2020%20EDI%20RD%20000496-2020-DGIA-MC.pdf', '2020', 'EDI', '', 'resolucion_beneficiario'),
    ('2020%20EDI%20RD%20N%C2%BA%20499-2020-DGIA-MC.pdf', '2020', 'EDI', '', 'resolucion_beneficiario'),
    ('2020%20EDI%20RD%20N%C2%BA%20500-2020-DGIA-MC.pdf', '2020', 'EDI', '', 'resolucion_beneficiario'),
    # 2021 — CDL (CLC histórico)
    ('2021-CLC-FalloFinal.pdf', '2021', 'CDL', '', 'fallo_final'),
    # 2023 — CCE (Creación Experimental)
    ('2023-CCE-RD-001176-2023-DGIA.pdf', '2023', 'CCE', '', 'resolucion_beneficiario'),
    # 2023 — CDC (Distribución y Circulación)
    ('2023-CDC-RD-001115-2023-DGIA_0.pdf', '2023', 'CDC', '', 'resolucion_beneficiario'),
    # 2023 — EPA (Preservación, código histórico CPR)
    ('2023-CPR-RD000989-2023-DGIA.pdf', '2023', 'EPA', '', 'resolucion_beneficiario'),
    # 2023 — PDT (Premio Destacada Trayectoria)
    ('2023-PDT-RD001040-2023-DGIA.pdf', '2023', 'PDT', '', 'resolucion_beneficiario'),
]


def main():
    dry_run = '--dry-run' in sys.argv

    sql = "BEGIN TRANSACTION;\n"
    total = 0
    errors = 0
    no_bene = 0

    for fname, anio, code, modalidad, tipo in PDFS:
        config = YEAR_CONFIG[anio]
        conv_id = config['convocatoria_id']
        url = BASE + fname
        display = fname.split('/')[-1].split('%20')[-1] if '%20' in fname else fname

        print(f"\n--- {code} {anio}: {display} ---", file=sys.stderr)

        if tipo == 'fallo_final':
            result, err = parse_fallo(url, anio, config)
        else:
            result, err = parse_rd(url, code, anio, config)

        if result and result.get('beneficiaries'):
            n = len(result['beneficiaries'])
            montos = [b.get('monto', 0) for b in result['beneficiaries']]
            total_monto = sum(montos)
            print(f"  OK: {n} beneficiarios, S/ {total_monto:,.0f}", file=sys.stderr)
            for b in result['beneficiaries']:
                name = b.get('razon_social') or f"{b.get('nombres','')} {b.get('apellidos','')}"
                print(f"    - {name.strip()}: S/ {b.get('monto',0):,.0f} | {b.get('proyecto','')[:40]}", file=sys.stderr)
            total += n
            sql += generate_sql(result, code, modalidad, conv_id, resolucion_tipo=tipo)
        elif result:
            print(f"  Sin beneficiarios (lista aptos/finalistas/jurado)", file=sys.stderr)
            no_bene += 1
        else:
            print(f"  ERROR: {err}", file=sys.stderr)
            errors += 1

    sql += "COMMIT;\n"

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Total: {total} beneficiarios extraídos", file=sys.stderr)
    print(f"Sin beneficiarios: {no_bene} PDFs (aptos/finalistas/jurado)", file=sys.stderr)
    print(f"Errores: {errors}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    if dry_run:
        print(sql)
        print("\n[--dry-run] No se escribió a la DB", file=sys.stderr)
    else:
        print(f"Escribiendo a DB...", file=sys.stderr)
        with sqlite3.connect(DB) as conn:
            conn.executescript(sql)
        print(f"DB actualizada.", file=sys.stderr)


if __name__ == '__main__':
    main()
