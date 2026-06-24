#!/usr/bin/env python3
"""Build FTS5 index for proyectos.

Indexes searchable text across multiple joined tables:
  - proyecto (titulo, descripcion)
  - persona (nombres, apellidos, razon_social, region)
  - linea_concursable (codigo, nombre_canonico)
  - modalidad (nombre)
  - proyecto_integrante -> persona (nombres+apellidos)
  - resolucion (numero)
  - proyecto (monto_otorgado as string)

Tokenizer: unicode61 with remove_diacritics=2 (accent-insensitive).
Re-run after re-importing data.
"""
import sqlite3
from pathlib import Path

DB = Path.home() / "Projects/Analisis_Concursos_DAFO/concursos_dafo.db"

DDL = """
DROP TABLE IF EXISTS proyecto_fts;
CREATE VIRTUAL TABLE proyecto_fts USING fts5(
    proyecto_id UNINDEXED,
    titulo,
    descripcion,
    nombres,
    apellidos,
    razon_social,
    region,
    linea_codigo,
    linea_nombre,
    modalidad,
    integrantes,
    rd_numero,
    monto_str,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

POPULATE = """
INSERT INTO proyecto_fts (
    proyecto_id, titulo, descripcion, nombres, apellidos,
    razon_social, region, linea_codigo, linea_nombre, modalidad,
    integrantes, rd_numero, monto_str
)
SELECT
    p.id,
    COALESCE(ob.titulo, ''),
    COALESCE(ob.descripcion, ''),
    COALESCE(pe.nombres, ''),
    COALESCE(pe.apellidos, ''),
    COALESCE(pe.razon_social, ''),
    COALESCE(pe.region, ''),
    lc.codigo,
    lc.nombre_canonico,
    COALESCE(mo.nombre, ''),
    COALESCE((
        SELECT GROUP_CONCAT(COALESCE(pn.nombres,'') || ' ' || COALESCE(pn.apellidos,''), ' | ')
        FROM proyecto_integrante pi
        JOIN persona pn ON pi.persona_id = pn.id
        WHERE pi.proyecto_id = p.id
    ), ''),
    COALESCE((
        SELECT GROUP_CONCAT(r.numero, ' | ')
        FROM resolucion r
        JOIN proyecto_resolucion rp ON r.id = rp.resolucion_id
        WHERE rp.proyecto_id = p.id
    ), ''),
    printf('S/ %.0f', p.monto_otorgado)
FROM proyecto p
JOIN concurso_anual ca ON p.concurso_anual_id = ca.id
JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
JOIN convocatoria cv ON ca.convocatoria_id = cv.id
LEFT JOIN obra ob ON p.obra_id = ob.id
LEFT JOIN persona pe ON p.persona_beneficiaria_id = pe.id
LEFT JOIN modalidad mo ON p.modalidad_id = mo.id;
"""


def main():
    conn = sqlite3.connect(str(DB))
    cur = conn.cursor()
    print("Dropping + creating proyecto_fts (FTS5, unicode61, remove_diacritics=2)...")
    cur.executescript(DDL)
    print("Populating from JOIN of proyecto + obra + persona + linea + modalidad + integrantes + resolucion...")
    cur.executescript(POPULATE)
    conn.commit()
    n = cur.execute("SELECT COUNT(*) FROM proyecto_fts").fetchone()[0]
    print(f"OK: {n} rows indexed.")
    # Quick smoke tests
    for q in ("cpf", "ficcion", "ficción", "fiction", "lima", "documental"):
        try:
            r = cur.execute(
                "SELECT COUNT(*) FROM proyecto_fts WHERE proyecto_fts MATCH ?",
                [q + "*"],
            ).fetchone()[0]
            print(f"  MATCH '{q}*': {r} hits")
        except sqlite3.OperationalError as e:
            print(f"  MATCH '{q}*': ERROR {e}")
    conn.close()


if __name__ == "__main__":
    main()
