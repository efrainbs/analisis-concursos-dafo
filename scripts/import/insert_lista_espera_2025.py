#!/usr/bin/env python3
"""Inserta los 12 beneficiarios de la RD 001134-2025-DGIA-VMPCIC/MC (lista de espera).

Esta RD del 12-Dic-2025 declara los últimos beneficiarios del año 2025,
promovidos desde la lista de espera cuando quedaron recursos disponibles.

Fuente: 2025-DAFO-ListaDeEspera.pdf (descargado del portal DAFO).
"""
import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "concursos_dafo.db"

RD_NUMERO = "001134-2025-DGIA-VMPCIC/MC"
RD_FECHA = "2025-12-12"
RD_URL = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/ee/archivos/2025-DAFO-ListaDeEspera.pdf"

# concurso_anual_id for 2025 lines
CA = {"CPF": 14, "CGC": 8, "CPA": 12, "CPC": 13, "CDO": 5}

# modalidad_id for 2025
MOD = {
    ("CPF", "Nuevos realizadores"): 2,
    ("CPF", "Desarrollo"): 1,
    ("CPF", "Tercer largometraje a más"): 4,
    ("CGC", "Festivales, encuentros y muestras"): 16,
    ("CPA", "Cortometrajes"): 9,
    ("CPC", "Ópera prima"): 7,
    ("CPC", "Segunda obra a más"): 8,
    ("CDO", "Desarrollo"): 5,
    ("CDO", "Producción"): 6,
}

# Los 12 beneficiarios extraídos del PDF.
# (linea, modalidad, razon_social, ruc, region, titulo, director, monto)
BENEFICIARIOS = [
    # Art. 1° — CPF Nuevos realizadores
    ("CPF", "Nuevos realizadores", "GIL DE COQUIS S.A.C.", "20614365227", "LIMA",
     "UN ESPÍRITU DE REVANCHA", "OSSIO SEMINARIO, JORGE FRANCISCO", 800000.00),
    ("CPF", "Nuevos realizadores", "YIN ZHANG FILMS S.A.C.", "20518558502", "LIMA",
     "EL PERRO LIU", "RELAYZE CHIANG, JONATAN", 800000.00),
    # Art. 2° — CGC Festivales
    ("CGC", "Festivales, encuentros y muestras", "EMPRESA M & D E.I.R.L.", "20541538489", "JUNÍN",
     "SEGUNDO FESTIVAL DE CINE DE LA SELVA CENTRAL - FECISC 2026", "DONAYRE BAZAN, MONICA CAROLINA", 60000.00),
    ("CGC", "Festivales, encuentros y muestras", "CONJUNTO CULTURAL EL COMUNAL E.I.R.L.", "20612472930", "PUNO",
     "KIMSA, ISKAY, HUK GALLARIN CINE", "RAMOS ARPITA, PEPE", 60000.00),
    # Art. 3° — CPA Cortometrajes
    ("CPA", "Cortometrajes", "COMETA AUDIOVISUAL S.A.C.", "20605037241", "LIMA",
     "PARA: LITA", "MONTALVO OSTOS, ERIC WILLLER / MONTALVO OSTOS, MARIEL LUZ", 92500.00),
    # Art. 4° — CPC Ópera prima
    ("CPC", "Ópera prima", "ANTISUYO S.A.C.", "20601649668", "LA LIBERTAD",
     "TEJIENDO PACARINAS, LA HILANDERA DE QUIRUVILCA", "SANDOVAL CASAMAYOR, GRACE KAREN", 60000.00),
    ("CPC", "Ópera prima", "KILLAPA SUNQUN AUDIO VISUAL E.I.R.L.", "20613741349", "AYACUCHO",
     "PELOTERA", "LAINES ARCCE, SHARON LISSETH", 60000.00),
    # Art. 5° — CPC Segunda obra a más
    ("CPC", "Segunda obra a más", "JACARANDA FILMS E.I.R.L.", "20608040049", "LIMA",
     "SABUESOS", "INGA VIZARRAGA, RAFAEL ALFREDO", 60000.00),
    # Art. 6° — CDO Desarrollo
    ("CDO", "Desarrollo", "BRANDED DOCUMENTARIES S E.I.R.L.", "20607609013", "LIMA",
     "RAÍCES: MEMORIA Y FUTURO", "GARCIA VIZCARRA, PABLO MARTIN", 40000.00),
    # Art. 7° — CPF Desarrollo
    ("CPF", "Desarrollo", "RENDERVERSE FILM PRODUCTION S.A.C.", "20606303301", "LIMA",
     "MAÑANA SERÁ MUY TARDE", "PLASENCIA GUTIERREZ, SEBASTIAN", 40000.00),
    # Art. 8° — CDO Producción
    ("CDO", "Producción", "AMPO FILMS E.I.R.L.", "20613871480", "LIMA",
     "MEMORANDUM", "PRIETO ESTRADA, ANTOLIN EDUARDO", 400000.00),
    # Art. 9° — CPF Tercer largometraje a más
    ("CPF", "Tercer largometraje a más", "LEOCES E.I.R.L.", "20605341692", "LIMA",
     "WIÑAY PHAWAY (EL VUELO ETERNO)", "GALINDO GALARZA, JULIO CESAR", 800000.00),
]


def main():
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA foreign_keys = ON")
    c = conn.cursor()

    # 1. Crear la resolución (usando CPF 2025 como ca_id principal, primer artículo)
    existing = c.execute("SELECT id FROM resolucion WHERE numero = ?", (RD_NUMERO,)).fetchone()
    if existing:
        rd_id = existing[0]
        print(f"  RD {RD_NUMERO} ya existe (id={rd_id})")
    else:
        c.execute(
            "INSERT INTO resolucion (concurso_anual_id, numero, fecha_contenido, tipo, url_pdf) VALUES (?, ?, ?, ?, ?)",
            (CA["CPF"], RD_NUMERO, RD_FECHA, "lista_espera", RD_URL),
        )
        rd_id = c.lastrowid
        print(f"  RD {RD_NUMERO} creada (id={rd_id}, tipo=lista_espera)")

    total_monto = 0
    inserted = 0

    for linea, modalidad, razon, ruc, region, titulo, director, monto in BENEFICIARIOS:
        ca_id = CA[linea]
        mod_id = MOD[(linea, modalidad)]
        total_monto += monto

        # 2. Persona jurídica (buscar por RUC o crear)
        row = c.execute("SELECT id FROM persona WHERE ruc = ?", (ruc,)).fetchone()
        if row:
            pid = row[0]
        else:
            c.execute(
                "INSERT INTO persona (tipo, razon_social, ruc, region) VALUES (?, ?, ?, ?)",
                ("juridica", razon, ruc, region),
            )
            pid = c.lastrowid

        # 3. Proyecto (buscar por título o crear)
        row = c.execute("SELECT id FROM obra WHERE titulo = ?", (titulo,)).fetchone()
        if row:
            proj_id = row[0]
        else:
            c.execute(
                "INSERT INTO obra (titulo, tipo) VALUES (?, ?)",
                (titulo, "audiovisual"),
            )
            proj_id = c.lastrowid

        # 4. Proyecto
        c.execute(
            "INSERT INTO proyecto (concurso_anual_id, modalidad_id, persona_beneficiaria_id, obra_id, monto_otorgado, estado) "
            "VALUES (?, ?, ?, ?, ?, 'beneficiario')",
            (ca_id, mod_id, pid, proj_id, monto),
        )
        post_id = c.lastrowid

        # 5. Link postulación → resolución
        c.execute(
            "INSERT INTO proyecto_resolucion (proyecto_id, resolucion_id) VALUES (?, ?)",
            (post_id, rd_id),
        )

        inserted += 1
        print(f"  [{inserted:2d}] {linea:3s} {modalidad:35s} | {razon:42s} | S/ {monto:>10,.0f} | {titulo}")

    conn.commit()
    conn.close()

    print(f"\nInsertados: {inserted} beneficiarios")
    print(f"Monto total: S/ {total_monto:,.2f}")
    print(f"RD: {RD_NUMERO} (id={rd_id})")


if __name__ == "__main__":
    main()
