#!/usr/bin/env python3
"""Fix bug de mapeo CFR 2020/2021/2022.

`extract_2024.py` mapeo los FallosFinal CFR a la linea CFO, pero CFR es
'Concurso de Proyectos de Largometraje de Ficcion exclusivo para las
regiones' -> realmente CPF, modalidad 'Regiones'. Mismo bug ya detectado
para CFR 2023 (corregido en assign_modalidades.py Fase 1 via sub-codigo
historico CFR->Regiones, pero solo para linea=CPF; aqui la linea asignada
es CFO, por eso el sub-codigo no aplico).

Este script mueve 12 proyectos (2 de 2020, 7 de 2021, 3 de 2022) de
CFO a CPF, junto con sus 3 resoluciones (rid 6634, 6520, 6443), y les
asigna modalidad 'Regiones' (creandola en CPF 2020/2021/2022 si no existe).

No destructivo respecto a montos/personas/proyectos: solo cambia
concurso_anual_id (proyecto + resolucion) y asigna modalidad_id.

Uso:
  python3 fix_cfr_mapeo.py            # dry-run
  python3 fix_cfr_mapeo.py --run
"""

import sqlite3
import sys

from dafo_common import DB_PATH

# Mapeo por anio: (ca_CFO_actual, ca_CPF_destino, rid_CFR, post_ids)
PLAN = {
    2020: {
        'ca_cfo': 47, 'ca_cpf': 39, 'rid': 6634,
        'posts': [61300, 61301],
    },
    2021: {
        'ca_cfo': 70, 'ca_cpf': 56, 'rid': 6520,
        'posts': [61091, 61092, 61093, 61094, 61095, 61096, 61097],
    },
    2022: {
        'ca_cfo': 86, 'ca_cpf': 75, 'rid': 6443,
        'posts': [60931, 60932, 60933],
    },
}

MODALIDAD_REGIONES = 'Regiones'


def ensure_modalidad(conn, ca_id, nombre):
    cur = conn.cursor()
    cur.execute("SELECT id FROM modalidad WHERE concurso_anual_id=? AND nombre=?",
                (ca_id, nombre))
    row = cur.fetchone()
    if row:
        return row[0], False  # (id, created)
    cur.execute("INSERT INTO modalidad (concurso_anual_id, nombre) VALUES (?, ?)",
                (ca_id, nombre))
    conn.commit()
    return cur.lastrowid, True


def main():
    do_run = '--run' in sys.argv
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()

    # Verificar estado actual (sanity check): los posts deben estar en CFO sin modalidad
    print("=" * 70, file=sys.stderr)
    print("FIX CFR 2020/2021/2022 — mover de CFO a CPF/Regiones", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    expected_total = 0
    for anio, p in PLAN.items():
        cur.execute("""SELECT COUNT(*), SUM(CASE WHEN po.concurso_anual_id=? AND po.modalidad_id IS NULL THEN 1 ELSE 0 END)
                       FROM proyecto po WHERE po.id IN (%s)"""
                    % ','.join('?' * len(p['posts'])),
                    [p['ca_cfo']] + p['posts'])
        n_total, n_ok = cur.fetchone()
        expected_total += len(p['posts'])
        status = 'OK' if n_total == len(p['posts']) and n_ok == len(p['posts']) else 'MISMATCH'
        print(f"  {anio}: {n_total}/{len(p['posts'])} posts en CFO sin modalidad [{status}]",
              file=sys.stderr)

        # Verificar resolucion
        cur.execute("SELECT concurso_anual_id, tipo FROM resolucion WHERE id=?",
                    (p['rid'],))
        row = cur.fetchone()
        if row:
            ca_r, tipo_r = row
            rstatus = 'OK' if ca_r == p['ca_cfo'] else f'WRONG ca={ca_r}'
            print(f"         rid={p['rid']} tipo={tipo_r} ca={ca_r} (esperado {p['ca_cfo']}) [{rstatus}]",
                  file=sys.stderr)
        else:
            print(f"         rid={p['rid']} NO ENCONTRADO", file=sys.stderr)

    print(f"\nTotal posts a mover: {expected_total}", file=sys.stderr)
    print(f"Total resoluciones a mover: {len(PLAN)}", file=sys.stderr)

    # Verificar ca_CPF destino existe
    print("\nConcursos_anuales CPF destino:", file=sys.stderr)
    for anio, p in PLAN.items():
        cur.execute("""SELECT ca.id, lc.codigo, c.anio FROM concurso_anual ca
                       JOIN linea_concursable lc ON lc.id=ca.linea_concursable_id
                       JOIN convocatoria c ON c.id=ca.convocatoria_id
                       WHERE ca.id=?""", (p['ca_cpf'],))
        row = cur.fetchone()
        if row:
            print(f"  {anio}: ca={row[0]} linea={row[1]} anio={row[2]} OK", file=sys.stderr)
        else:
            print(f"  {anio}: ca={p['ca_cpf']} NO ENCONTRADO", file=sys.stderr)

    if not do_run:
        print("\n[DRY-RUN] Sin cambios. Usar --run para aplicar.", file=sys.stderr)
        conn.close()
        return

    # ── Aplicar ──
    print("\n[RUN] Aplicando fix...", file=sys.stderr)
    created_modalidades = []
    updated_posts = 0
    updated_resols = 0
    for anio, p in PLAN.items():
        # 1) Crear modalidad 'Regiones' en CPF destino si no existe
        mod_id, created = ensure_modalidad(conn, p['ca_cpf'], MODALIDAD_REGIONES)
        if created:
            created_modalidades.append((anio, mod_id))
            print(f"  {anio}: creada modalidad 'Regiones' id={mod_id} en ca={p['ca_cpf']}",
                  file=sys.stderr)
        else:
            print(f"  {anio}: modalidad 'Regiones' ya existe id={mod_id} en ca={p['ca_cpf']}",
                  file=sys.stderr)

        # 2) Mover proyectos: concurso_anual_id + modalidad_id
        cur.execute("""UPDATE proyecto
                       SET concurso_anual_id=?, modalidad_id=?
                       WHERE id IN (%s) AND concurso_anual_id=? AND modalidad_id IS NULL"""
                    % ','.join('?' * len(p['posts'])),
                    [p['ca_cpf'], mod_id] + p['posts'] + [p['ca_cfo']])
        updated_posts += cur.rowcount

        # 3) Mover resolucion: concurso_anual_id
        cur.execute("""UPDATE resolucion SET concurso_anual_id=?
                       WHERE id=? AND concurso_anual_id=?""",
                    (p['ca_cpf'], p['rid'], p['ca_cfo']))
        updated_resols += cur.rowcount

    conn.commit()
    print(f"\n[RUN] Proyectos movidas: {updated_posts}/{expected_total}", file=sys.stderr)
    print(f"[RUN] Resoluciones movidas: {updated_resols}/{len(PLAN)}", file=sys.stderr)
    print(f"[RUN] Modalidades creadas: {len(created_modalidades)}", file=sys.stderr)
    conn.close()


if __name__ == '__main__':
    main()
