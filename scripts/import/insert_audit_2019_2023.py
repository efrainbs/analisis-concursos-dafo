#!/usr/bin/env python3
"""Auditoría 2019-2023: inserta beneficiarios de PDFs faltantes con datos limpios.

Extracción manual de 13 PDFs no procesados por extract_2024.py.
Corrige bugs de mapeo detectados:
  - 2020-CDI-FalloFinal.pdf → CIN (no CDL)
  - 2020-CLC-FalloFinal.pdf → CCC (no CDL)
  - 2021-CLC-FalloFinal.pdf → CCC (no CDL)

No borra nada: dedup por persona (RUC/DNI/razon_social) y proyecto (titulo).
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "concursos_dafo.db"

BASE = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/"

# concurso_anual_id por año/línea
CA = {
    ('CIN', 2020): 52,
    ('CCC', 2020): 40,
    ('CCC', 2021): 59,
    ('EDI', 2020): 38,
    ('CCE', 2023): 104,
    ('CDC', 2023): 105,
    ('EPA', 2023): 101,
    ('PDT', 2023): 135,
}

# Estructura de cada entrada:
# (ca_key, rd_numero, rd_fecha, rd_tipo, rd_url, [beneficiarios])
# beneficiario = (tipo, razon_social, ruc, nombres, apellidos, dni, region, titulo_proyecto, director, monto)

DATOS = [
    # ── CIN 2020 (RD 000370, fallo_final) — 5 personas naturales ──
    (('CIN', 2020), '000370-2020-DGIA/MC', '2020-11-13', 'fallo_final',
     BASE + '2020-CDI-FalloFinal.pdf',
     [
         ('natural', '', '', 'SILVANA JACQUELINE', 'ALARCÓN SANCHEZ', '', 'CALLAO',
          'MUTACIONES DEL ESPECTADOR EN PERÚ: HACIA LA CREACIÓN DEL PERFIL DEL CONSUMIDOR DE ESTRENOS CINEMATOGRÁFICOS NACIONALES EN EL 2019', '', 30000.00),
         ('natural', '', '', 'MAURICIO JOSE', 'GODOY PAREDES', '', 'LIMA',
          'LAS DIVERSAS VOCES SOBRE EL CONFLICTO ARMADO INTERNO PERUANO EN PRODUCCIONES AUDIOVISUALES', '', 30000.00),
         ('natural', '', '', 'SUGEY MILAGROS', 'LOPEZ ALCALDE', '', 'LAMBAYEQUE',
          'ESTRUCTURA DE CONTENIDOS DE LOS FESTIVALES DE CINE EN EL PERÚ PARA LA CREACIÓN DE PÚBLICOS', '', 30000.00),
         ('natural', '', '', 'FABIOLA', 'REYNA GUTIERREZ', '', 'LIMA',
          'BRECHAS DE GÉNERO EN EL CINE PERUANO', '', 30000.00),
         ('natural', '', '', 'GABRIELA CRISTINA', 'YEPES ROSSEL', '', 'LIMA',
          'REBELDES Y VALIENTES: MUJERES DETRÁS DE LA CÁMARA (1910-1992)', '', 30000.00),
     ]),

    # ── CCC 2020 (RD 000405, fallo_final) — 5 personas jurídicas ──
    (('CCC', 2020), '000405-2020-DGIA/MC', '2020-12-02', 'fallo_final',
     BASE + '2020-CLC-FalloFinal.pdf',
     [
         ('juridica', 'EFEX COMUNICACIONES S.A.C.', '', '', '', '', 'LA LIBERTAD',
          'ÁRBOLES QUE HE INVENTADO', 'DE LEON, GILBERTHS MARTIN', 86290.00),
         ('juridica', 'HIPERACTIVA COMUNICACIONES S E.I.R.L.', '', '', '', '', 'LIMA',
          'ROJO PROFUNDO', 'ZEVALLOS RIOS, MAGALI', 130930.90),
         ('juridica', 'LA SOGA PRODUCCIONES EIRL', '', '', '', '', 'LIMA',
          'AMELIA', 'OYARZU, FRANCISCO JOSE', 155000.00),
         ('juridica', 'TOMBUKTU FILMS S.A.C.', '', '', '', '', 'LIMA',
          'UN MUNDO PARA JULIUS', 'CARMEN ROSSANA', 139500.00),
         ('juridica', 'YURAQYANA FILMS S.A.C.', '', '', '', '', 'LIMA',
          'ANTONIA EN LA VIDA', 'GAMARRA, MARIA NATALIA', 106700.00),
     ]),

    # ── CCC 2021 (RD 000469, fallo_final) — 4 personas jurídicas ──
    (('CCC', 2021), '000469-2021-DGIA/MC', '2021-12-15', 'fallo_final',
     BASE + '2021-CLC-FalloFinal.pdf',
     [
         ('juridica', 'PRODUCTORA AUDIOVISUAL CASA LUZ E.I.R.L.', '', '', '', '', 'LIMA',
          'El Viaje al Origen del Kene', 'ARRASCUE NAVAS, RODOLFO ABDIAS', 150000.00),
         ('juridica', 'AYNI PRODUCCIONES S.A.C.', '', '', '', '', 'LIMA',
          'Donde hubo fuego UCHPA queda', 'RODRIGUEZ ROMANI, JOSE ANTONIO', 146700.00),
         ('juridica', 'ATIAJA FILM SAC', '', '', '', '', 'LIMA',
          'HOGAR', 'BURMESTER ATIAJA, ALEJANDRO AUGUSTO', 155000.00),
         ('juridica', 'ARDE LIMA E.I.R.L.', '', '', '', '', 'LIMA',
          'Arde Lima', 'CASTRO ANTEZANA, ALBERTO JOSE', 111745.00),
     ]),

    # ── EDI 2020 — 6 RDs individuales, 1 beneficiaria c/u ──
    (('EDI', 2020), '000348-2020-DGIA/MC', '2020-10-30', 'resolucion_beneficiario',
     BASE + '2020%20EDI%20RD%20000348-2020-DGIA-MC_1.pdf',
     [
         ('juridica', 'CARAPULKRA FILMS S.A.C.', '', '', '', '', 'LIMA',
          'LINA DE LIMA', '', 140000.00),
     ]),
    (('EDI', 2020), '000369-2020-DGIA/MC', '2020-11-13', 'resolucion_beneficiario',
     BASE + '2020%20EDI%20RD%20000369-2020-DGIA-MC.pdf',
     [
         ('juridica', 'GRETI PRODUCCIONES AUDIOVISUALES E.I.R.L.', '', '', '', '', 'LIMA',
          'CINES DE VIDEO', '', 90000.00),
     ]),
    (('EDI', 2020), '000377-2020-DGIA/MC', '2020-11-17', 'resolucion_beneficiario',
     BASE + '2020%20EDI%20RD%20000377-2020-DGIA-MC.pdf',
     [
         ('juridica', 'LA TROPILLA DE OBRAJEROS E.I.R.L.', '', '', '', '', 'LIMA',
          'MATAINDIOS', '', 145000.00),
     ]),
    (('EDI', 2020), '000496-2020-DGIA/MC', '2020-12-04', 'resolucion_beneficiario',
     BASE + '2020%20EDI%20RD%20000496-2020-DGIA-MC.pdf',
     [
         ('juridica', 'PLOT POINT E.I.R.L.', '', '', '', '', 'LIMA',
          'LARGA DISTANCIA', '', 120000.00),
     ]),
    (('EDI', 2020), '000499-2020-DGIA/MC', '2020-12-07', 'resolucion_beneficiario',
     BASE + '2020%20EDI%20RD%20N%C2%BA%20499-2020-DGIA-MC.pdf',
     [
         ('juridica', 'PIONEROS PRODUCCIONES E.I.R.L.', '', '', '', '', 'PUNO',
          'MANCO CAPAC', '', 145000.00),
     ]),
    (('EDI', 2020), '000500-2020-DGIA/MC', '2020-12-07', 'resolucion_beneficiario',
     BASE + '2020%20EDI%20RD%20N%C2%BA%20500-2020-DGIA-MC.pdf',
     [
         ('juridica', 'BUENALETRA PRODUCCIONES S.A.C.', '', '', '', '', 'LIMA',
          'MUJER DE SOLDADO', '', 89800.00),
     ]),

    # ── CCE 2023 (RD 001176, resolucion_beneficiario) — 4 personas naturales con DNI ──
    (('CCE', 2023), '001176-2023-DGIA/MC', '2023-11-22', 'resolucion_beneficiario',
     BASE + '2023-CCE-RD-001176-2023-DGIA.pdf',
     [
         ('natural', '', '', 'MARICE FRANCIS YDELSA', 'CASTAÑEDA GUTIERREZ', '41330199', 'LIMA',
          'SOLAR', '', 24627.50),
         ('natural', '', '', 'FERNANDO', 'CRIOLLO NAVARRO', '71273708', 'LIMA',
          'ANIMA MUNDI', '', 30000.00),
         ('natural', '', '', 'JULIO JESUS GUIDO', 'CHARCA LOPEZ', '72158979', 'PUNO',
          'SOCTAYO', '', 30000.00),
         ('natural', '', '', 'JORGE RICARDO', 'CASTRO GUTIERREZ', '41361457', 'CUSCO',
          'ESE BRILLANTE OBJETO DEL DESEO', '', 30000.00),
     ]),

    # ── CDC 2023 (RD 001115, resolucion_beneficiario) — 3 personas jurídicas con RUC ──
    (('CDC', 2023), '001115-2023-DGIA/MC', '2023-10-05', 'resolucion_beneficiario',
     BASE + '2023-CDC-RD-001115-2023-DGIA_0.pdf',
     [
         ('juridica', 'CATACRESIS CINE E.I.R.L.', '20568707410', '', '', '', 'JUNÍN',
          'DOCUANDES: DOCUMENTALES ANDINOS POST BICENTENARIO', 'SULCA RICRA, ROMULO', 49500.00),
         ('juridica', 'CINE Y TV TELEANDES S.R.L.', '20374545591', '', '', '', 'LIMA',
          'GROMPES, CURUMI Y LA NIÑA DE LA PAPAYA', 'VALDIVIA GOMEZ, JULIO FERNANDO', 90000.00),
         ('juridica', "PLAN'S S.A.C.", '20610726012', '', '', '', 'JUNÍN',
          'VOLVER A VIVIR', 'CENZANO, ANTHONY JHUNIOR', 90000.00),
     ]),

    # ── EPA 2023 (RD 000989, resolucion_beneficiario) — 2 personas jurídicas con RUC ──
    (('EPA', 2023), '000989-2023-DGIA/MC', '2023-11-15', 'resolucion_beneficiario',
     BASE + '2023-CPR-RD000989-2023-DGIA.pdf',
     [
         ('juridica', '199 COMUNICACIONES E.I.R.L.', '20611031352', '', '', '', 'LIMA',
          'NOTICIEROS CULTURALES "VICUS" Y NOTICIERO "MUJER, HOY"', 'ORE ROMERO, PEDRO GUILLERMO', 112000.00),
         ('juridica', 'DE SAME FILMS S.A.C.', '20603354428', '', '', '', 'CALLAO',
          'CHABUCA GRANDA, CONFIDENCIAS / ESTIGMA (OBRAS DE MARTHA LUNA)', 'MOSCOSO SILVA, CHRISTIAN DAVID', 112000.00),
     ]),

    # ── PDT 2023 (RD 001040, resolucion_beneficiario) — 2 personas naturales con DNI ──
    (('PDT', 2023), '001040-2023-DGIA/MC', '2023-11-28', 'resolucion_beneficiario',
     BASE + '2023-PDT-RD001040-2023-DGIA.pdf',
     [
         ('natural', '', '', 'JOSE ANTONIO', 'PORTUGAL SPEEDIE', '07819996', 'AREQUIPA',
          '', '', 10000.00),
         ('natural', '', '', 'ALVARO', 'VELARDE LA ROSA', '08194292', 'LIMA',
          '', '', 10000.00),
     ]),
]


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    total_benefs = 0
    total_monto = 0

    for ca_key, rd_num, rd_fecha, rd_tipo, rd_url, benefs in DATOS:
        ca_id = CA[ca_key]
        linea, anio = ca_key

        # 1. Resolución (dedup por url_pdf)
        row = c.execute("SELECT id FROM resolucion WHERE url_pdf = ?", (rd_url,)).fetchone()
        if row:
            rd_id = row[0]
        else:
            c.execute(
                "INSERT INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf) VALUES (?, ?, ?, ?, ?)",
                (ca_id, rd_num, rd_fecha, rd_tipo, rd_url),
            )
            rd_id = c.lastrowid

        print(f"\n--- {linea} {anio} | RD {rd_num} (id={rd_id}) ---")

        for tipo_p, razon, ruc, nombres, apellidos, dni, region, titulo, director, monto in benefs:
            # 2. Persona (dedup)
            if tipo_p == 'juridica':
                if ruc:
                    row = c.execute("SELECT id FROM persona WHERE ruc = ?", (ruc,)).fetchone()
                else:
                    row = c.execute(
                        "SELECT id FROM persona WHERE tipo='juridica' AND razon_social = ? AND (ruc IS NULL OR ruc = '')",
                        (razon,),
                    ).fetchone()
                if row:
                    pid = row[0]
                else:
                    c.execute(
                        "INSERT INTO persona (tipo, razon_social, ruc, region) VALUES (?, ?, ?, ?)",
                        ('juridica', razon, ruc or '', region),
                    )
                    pid = c.lastrowid
            else:  # natural
                if dni:
                    row = c.execute("SELECT id FROM persona WHERE dni = ?", (dni,)).fetchone()
                else:
                    row = c.execute(
                        "SELECT id FROM persona WHERE tipo='natural' AND nombres = ? AND apellidos = ? AND (dni IS NULL OR dni = '')",
                        (nombres, apellidos),
                    ).fetchone()
                if row:
                    pid = row[0]
                else:
                    c.execute(
                        "INSERT INTO persona (tipo, nombres, apellidos, dni, region) VALUES (?, ?, ?, ?, ?)",
                        ('natural', nombres, apellidos, dni or '', region),
                    )
                    pid = c.lastrowid

            # 3. Proyecto (dedup por titulo)
            proj_id = None
            if titulo:
                row = c.execute("SELECT id FROM obra WHERE titulo = ?", (titulo,)).fetchone()
                if row:
                    proj_id = row[0]
                else:
                    c.execute("INSERT INTO obra (titulo, tipo) VALUES (?, 'audiovisual')", (titulo,))
                    proj_id = c.lastrowid

            # 4. Proyecto (dedup por ca_id + persona)
            row = c.execute(
                "SELECT id FROM proyecto WHERE concurso_anual_id = ? AND persona_beneficiaria_id = ?",
                (ca_id, pid),
            ).fetchone()
            if row:
                post_id = row[0]
                # Update monto if current is 0 and new is not
                c.execute(
                    "UPDATE proyecto SET monto_otorgado = ? WHERE id = ? AND monto_otorgado = 0",
                    (monto, post_id),
                )
            else:
                c.execute(
                    "INSERT INTO proyecto (concurso_anual_id, persona_beneficiaria_id, obra_id, monto_otorgado, estado) "
                    "VALUES (?, ?, ?, ?, 'beneficiario')",
                    (ca_id, pid, proj_id, monto),
                )
                post_id = c.lastrowid

            # 5. Link postulación → resolución
            c.execute(
                "INSERT OR IGNORE INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
                (post_id, rd_id),
            )

            # 6. Director como integrante (responsable) para jurídicas
            if director and len(director) >= 5:
                # Limpiar nombre del director
                resp = director
                import re
                dni_match = re.search(r'(\d{8})', resp)
                resp = re.sub(r'\d{8}', '', resp)
                resp = re.sub(r'[()]', '', resp)
                resp = re.sub(r'DNI\s*N?[°º]?\s*', '', resp, flags=re.IGNORECASE)
                resp = resp.strip().rstrip(',').strip()
                resp = re.sub(r'\s+', ' ', resp).strip()

                if ',' in resp:
                    parts = resp.split(',', 1)
                    resp_apellidos = parts[0].strip()
                    resp_nombres = parts[1].strip()
                else:
                    words = resp.split()
                    if len(words) >= 2:
                        resp_nombres = ' '.join(words[:-1])
                        resp_apellidos = words[-1]
                    else:
                        resp_nombres = resp
                        resp_apellidos = ''

                if resp_nombres and resp_apellidos:
                    if dni_match:
                        dni_resp = dni_match.group(1)
                        row = c.execute("SELECT id FROM persona WHERE dni = ?", (dni_resp,)).fetchone()
                    else:
                        row = c.execute(
                            "SELECT id FROM persona WHERE tipo='natural' AND nombres = ? AND apellidos = ? AND (dni IS NULL OR dni = '')",
                            (resp_nombres, resp_apellidos),
                        ).fetchone()
                    if row:
                        resp_pid = row[0]
                    else:
                        c.execute(
                            "INSERT INTO persona (tipo, nombres, apellidos, dni) VALUES (?, ?, ?, ?)",
                            ('natural', resp_nombres, resp_apellidos, dni_resp if dni_match else ''),
                        )
                        resp_pid = c.lastrowid

                    c.execute(
                        "INSERT OR IGNORE INTO proyecto_integrante (proyecto_id, persona_id, rol) VALUES (?, ?, 'responsable')",
                        (post_id, resp_pid),
                    )

            total_benefs += 1
            total_monto += monto
            name = razon or f"{nombres} {apellidos}"
            print(f"  [{total_benefs:2d}] {name.strip():45s} | S/ {monto:>10,.0f} | {titulo[:40]}")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Total insertados: {total_benefs} beneficiarios")
    print(f"Monto total: S/ {total_monto:,.2f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
