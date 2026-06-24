#!/usr/bin/env python3
"""Populate the documento table from dafo_pdfs_map.json."""
import json
import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dafo_common import DB_PATH, get_concurso_anual_id

PDFS_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dafo_pdfs_map.json")

CATEGORY_TO_TIPO = {
    "fallo_final": "resultado",
    "beneficiarios": "resultado",
    "resultados": "resultado",
    "acta_evaluacion": "acta",
    "acta": "acta",
    "lista_espera": "lista_espera",
}


def filename_to_tipo(name: str) -> str | None:
    name_lower = name.lower()
    if "base" in name_lower:
        return "bases"
    if "anexo" in name_lower:
        return "anexos"
    if "fe" in name_lower and "errata" in name_lower:
        return "fe_erratas"
    if "error" in name_lower:
        return "fe_erratas"
    if "formulario" in name_lower:
        return "anexos"
    if "recibidos" in name_lower:
        return "anexos"
    if "aptos" in name_lower:
        return "lista_espera"
    if "comunicado" in name_lower or "finalistas" in name_lower:
        return "resultado"
    if any(w in name_lower for w in ("contrato", "sumilla", "guion", "tratamiento", "consulta", "referencia", "consolidado", "respuestas", "pitch", "cesi")):
        return "anexos"
    return None


def generate_title(line_name: str, category: str, anio: str) -> str:
    labels = {
        "fallo_final": "Fallo final",
        "beneficiarios": "Beneficiarios",
        "resultados": "Resultados",
        "acta_evaluacion": "Acta de evaluación",
        "acta": "Acta",
        "lista_espera": "Lista de espera",
        "bases": "Bases",
        "anexos": "Anexos",
        "fe_erratas": "Fe de erratas",
    }
    label = labels.get(category, category.replace("_", " ").title())
    return f"{label} — {line_name} ({anio})"


def main():
    with open(PDFS_MAP) as f:
        data = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    inserted = 0
    skipped_no_ca = 0
    skipped_other = 0
    skipped_dup = 0

    for anio in sorted(data.keys()):
        for codigo, info in data[anio].items():
            line_name = info.get("name", codigo)
            ca_id = get_concurso_anual_id(codigo, anio=int(anio))
            if ca_id is None:
                skipped_no_ca += 1
                continue

            for pdf in info.get("pdfs", []):
                url = pdf["url"]
                category = pdf.get("category", "other")
                fname = pdf.get("name", url.split("/")[-1])

                tipo = CATEGORY_TO_TIPO.get(category)
                if tipo is None:
                    tipo = filename_to_tipo(fname)
                if tipo is None:
                    skipped_other += 1
                    continue

                titulo = generate_title(line_name, category if tipo in CATEGORY_TO_TIPO.values() else tipo, anio)

                c.execute(
                    "SELECT 1 FROM documento WHERE concurso_anual_id = ? AND url = ?",
                    (ca_id, url),
                )
                if c.fetchone():
                    skipped_dup += 1
                    continue

                c.execute(
                    "INSERT INTO documento (concurso_anual_id, tipo_doc, url, titulo) VALUES (?, ?, ?, ?)",
                    (ca_id, tipo, url, titulo),
                )
                inserted += 1

    conn.commit()
    conn.close()

    print(f"Inserted: {inserted}")
    print(f"Skipped (no concurso_anual): {skipped_no_ca}")
    print(f"Skipped (unmapped other): {skipped_other}")
    print(f"Skipped (duplicate url): {skipped_dup}")


if __name__ == "__main__":
    main()
