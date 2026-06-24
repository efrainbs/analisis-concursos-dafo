#!/usr/bin/env python3
"""Scrape 2025 DAFO line pages for PDFs and insert into documento table."""
import json, os, re, sys, sqlite3
from urllib.parse import urljoin
from dafo_common import DB_PATH, get_concurso_anual_id

BASE = "https://estimuloseconomicos.cultura.gob.pe"
ARCHIVOS = BASE + "/sites/default/files/concursos/archivos/"

PAGE_SLUG_TO_CODE = {
    "estimulo-la-promocion-internacional": "EPI",
    "estimulo-la-distribucion-cinematografica": "EDI",
    "concurso-de-proyectos-de-ficcion": "CPF",
    "concurso-de-proyectos-de-documental": "CDO",
    "concurso-de-proyectos-de-gestion-para-el-audiovisual": "CGC",
    "concurso-para-la-formacion-audiovisual": "CFO",
    "concurso-de-proyectos-de-cortometrajes": "CPC",
    "concurso-de-cine-en-construccion": "CCC",
    "concurso-de-proyectos-de-animacion": "CPA",
    "premio-la-destacada-trayectoria-en-el-ambito-audiovisual": "PDT",
    "estimulo-la-preservacion-audiovisual": "EPA",
    "concurso-de-video-y-cine-indigena-y-afrodescendiente-comunitario": "CIC",
    "concurso-de-coproducciones-minoritarias": "CCM",
    "concurso-de-distribucion-y-circulacion-de-obras": "CDC",
    "concurso-de-salas-de-exhibicion-alternativa": "CGS",
    "concurso-de-desarrollo-de-videojuegos": "CDV",
    "concurso-de-proyectos-de-investigacion-sobre-cinematografia-y-audiovisual": "CIN",
    "concurso-de-creacion-experimental": "CCE",
}

CODE_TO_NAME = {v: k.replace("-", " ").title() for k, v in PAGE_SLUG_TO_CODE.items()}
CODE_TO_NAME.update({
    "EPI": "Estímulo a la Promoción Internacional",
    "EDI": "Estímulo a la Distribución Cinematográfica",
    "PDT": "Premio a la Destacada Trayectoria en el Ámbito Audiovisual",
    "EPA": "Estímulo a la Preservación Audiovisual",
})


def filename_to_tipo(name: str) -> str | None:
    name_lower = name.lower()
    if "base" in name_lower:
        return "bases"
    if "anexo" in name_lower or "formulario" in name_lower or "actacompromiso" in name_lower:
        return "anexos"
    if "consolidado" in name_lower or "recibidos" in name_lower or "sumilla" in name_lower or "contrato" in name_lower:
        return "anexos"
    if "fe" in name_lower and "errata" in name_lower:
        return "fe_erratas"
    if "error" in name_lower:
        return "fe_erratas"
    if "jurado" in name_lower or "encuentro" in name_lower:
        return "acta"
    if "aptos" in name_lower or "incorporacion" in name_lower:
        return "lista_espera"
    if "fallo" in name_lower or "resultado" in name_lower:
        return "resultado"
    return None


def generate_title(tipo: str, line_name: str) -> str:
    labels = {
        "bases": "Bases",
        "anexos": "Anexos",
        "acta": "Acta de evaluación",
        "lista_espera": "Lista de espera",
        "resultado": "Resultados",
        "fe_erratas": "Fe de erratas",
    }
    label = labels.get(tipo, tipo)
    return f"{label} — {line_name} (2025)"


def fetch(url):
    import subprocess
    r = subprocess.run(["curl", "-sL", "--max-time", "15", url], capture_output=True, text=True, timeout=20)
    return r.stdout


def fetch_pdfs_for_line(code: str, slug: str) -> list[dict]:
    url = f"{BASE}/2025/concursos/{slug}"
    html = fetch(url)
    if not html:
        print(f"  [SKIP] No content for {code}")
        return []

    pdfs = []
    for m in re.finditer(r'href="(/sites/default/files/concursos/archivos/[^"]*\.pdf[^"]*)"', html):
        url_path = m.group(1)
        full_url = urljoin(BASE, url_path)
        fname = url_path.split("/")[-1]
        pdfs.append({"url": full_url, "filename": fname})

    print(f"  {code}: {len(pdfs)} PDFs found")
    return pdfs


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    all_pdfs = {}
    for slug, code in PAGE_SLUG_TO_CODE.items():
        pdfs = fetch_pdfs_for_line(code, slug)
        all_pdfs[code] = pdfs

    # Also add the general PDFs from the main page
    print("\n--- Fetching general PDFs from main 2025 page ---")
    main_html = fetch(f"{BASE}/2025/estimulos-economicos-para-la-actividad-cinematografica-y-audiovisual-2025")
    general_pdfs = []
    if main_html:
        for m in re.finditer(r'href="(/sites/default/files/[^"]*\.pdf[^"]*)"', main_html):
            url_path = m.group(1)
            full_url = urljoin(BASE, url_path)
            fname = url_path.split("/")[-1]
            general_pdfs.append({"url": full_url, "filename": fname})
        print(f"  General PDFs: {len(general_pdfs)}")

    inserted = 0
    skipped = 0
    skipped_no_ca = 0

    for code, pdfs in all_pdfs.items():
        ca_id = get_concurso_anual_id(code, anio=2025)
        if ca_id is None:
            print(f"  [WARN] No concurso_anual for {code}/2025")
            skipped_no_ca += 1
            continue

        line_name = CODE_TO_NAME.get(code, code)

        for pdf in pdfs:
            url = pdf["url"]
            fname = pdf["filename"]
            tipo = filename_to_tipo(fname)

            if tipo is None:
                skipped += 1
                continue

            # Check duplicate
            c.execute("SELECT 1 FROM documento WHERE concurso_anual_id = ? AND url = ?", (ca_id, url))
            if c.fetchone():
                skipped += 1
                continue

            titulo = generate_title(tipo, line_name)
            c.execute(
                "INSERT INTO documento (concurso_anual_id, tipo_doc, url, titulo) VALUES (?, ?, ?, ?)",
                (ca_id, tipo, url, titulo),
            )
            inserted += 1

    # Insert general PDFs for all 2025 concurso_anual (or specific ones)
    # Lista de Espera goes to all lines
    lista_espera_urls = [p for p in general_pdfs if "lista" in p["filename"].lower() or "ListaDeEspera" in p["filename"]]
    rd_urls = [p for p in general_pdfs if p["filename"].startswith("2025-DAFO-RD")]

    for code in PAGE_SLUG_TO_CODE.values():
        ca_id = get_concurso_anual_id(code, anio=2025)
        if ca_id is None:
            continue
        line_name = CODE_TO_NAME.get(code, code)

        # Lista de espera
        for p in lista_espera_urls:
            c.execute("SELECT 1 FROM documento WHERE concurso_anual_id = ? AND url = ?", (ca_id, p["url"]))
            if not c.fetchone():
                c.execute(
                    "INSERT INTO documento (concurso_anual_id, tipo_doc, url, titulo) VALUES (?, ?, ?, ?)",
                    (ca_id, "lista_espera", p["url"], f"Lista de espera — {line_name} (2025)"),
                )
                inserted += 1

        # RDs (bases)
        for p in rd_urls:
            c.execute("SELECT 1 FROM documento WHERE concurso_anual_id = ? AND url = ?", (ca_id, p["url"]))
            if not c.fetchone():
                tipo = "bases" if "bases" in p["filename"].lower() else "fe_erratas"
                titulo = f"{'Bases' if tipo == 'bases' else 'Fe de erratas'} — {line_name} (2025)"
                c.execute(
                    "INSERT INTO documento (concurso_anual_id, tipo_doc, url, titulo) VALUES (?, ?, ?, ?)",
                    (ca_id, tipo, p["url"], titulo),
                )
                inserted += 1

    conn.commit()
    conn.close()

    print(f"\nInserted: {inserted}")
    print(f"Skipped (unmapped/no dup): {skipped}")
    print(f"Skipped (no concurso_anual): {skipped_no_ca}")


if __name__ == "__main__":
    main()
