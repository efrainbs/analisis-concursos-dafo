#!/usr/bin/env python3
"""
Discover FalloFinal / Beneficiarios PDFs for DAFO 2019-2024.
Visits each concurso page and extracts PDF links.
Outputs JSON mapping year -> code -> [PDF URLs]
"""

import subprocess, re, json, os, sys

BASE = "https://estimuloseconomicos.cultura.gob.pe"
ARCHIVOS_BASE = BASE + "/sites/default/files/"

def fetch(url, retries=2):
    for attempt in range(retries):
        try:
            r = subprocess.run(['curl', '-sL', '--max-time', '15', url],
                             capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout:
                return r.stdout
        except:
            pass
    return ''

def extract_concurso_links(html):
    links = set()
    for m in re.finditer(r'href="(https?://estimuloseconomicos\.cultura\.gob\.pe/20\d{2}/concursos/[^"]+)"', html):
        links.add(m.group(1))
    return sorted(links)

def code_from_url(url):
    slug = url.rstrip('/').split('/')[-1]
    # Remove year suffix like "-2019"
    slug = re.sub(r'-\d{4}$', '', slug)
    code_map = {
        'proyectos-de-ficcion': 'CPF',
        'proyectos-de-largometraje-de-ficcion': 'CPF',
        'largometraje-de-ficcion-exclusivo-para-las-regiones': 'CPF',
        'largometraje-de-ficcion-exclusivo-para-las-regiones-del-pais-excepto-lima': 'CPF',
        'largometraje-de-ficcion-exclusivo-para-las-regiones-del-pais-excepto-lima-metropolitana-y-callao': 'CPF',
        'largometraje-de-ficcion-a-nivel-nacional': 'CPF',
        'proyectos-de-largometraje-de-ficcion-estimulo-alternativo': 'CPF',
        'desarrollo-de-proyectos-de-largometraje': 'CPF',
        'proyectos-de-documental': 'CDO',
        'documental-formato-largo': 'CDO',
        'proyectos-de-documental-formato-largo': 'CDO',
        'proyectos-de-cortometraje': 'CPC',
        'concurso-nacional-de-proyectos-de-cortometraje': 'CPC',
        'proyectos-de-cortometrajes': 'CPC',
        'cortometrajes': 'CPC',
        'proyectos-de-animacion': 'CPA',
        'preproduccion-de-largometraje-de-animacion': 'CPA',
        'desarrollo-de-videojuegos': 'CDV',
        'gestion-cultural-para-el-audiovisual': 'CGC',
        'proyectos-de-gestion-cultural-para-el-audiovisual': 'CGC',
        'proyectos-de-gestion-para-el-audiovisual': 'CGC',
        'cine-en-construccion': 'CCC',
        'largometraje-en-construccion': 'CCC',
        'largometraje-en-construccion-antes-postproduccion': 'CCC',
        'coproducciones-minoritarias': 'CCM',
        'creacion-experimental': 'CCE',
        'obras-experimentales': 'CCE',
        'concurso-nacional-de-obras-experimentales': 'CCE',
        'distribucion-y-circulacion-de-obras': 'CDC',
        'circulacion-de-obras': 'CDC',
        'concurso-nacional-de-distribucion-y-circulacion-de-obras': 'CDC',
        'gestion-de-salas-de-exhibicion-alternativa': 'CGS',
        'salas-de-cine-de-exhibicion-alternativa': 'CGS',
        'formacion-audiovisual': 'CFO',
        'concurso-nacional-para-la-formacion-audiovisual': 'CFO',
        'preservacion-audiovisual': 'EPA',
        'proyectos-de-preservacion-audiovisual': 'EPA',
        'video-y-cine-indigena-y-afrodescendiente-comunitario': 'CIC',
        'video-y-cine-indigena-comunitario': 'CIC',
        'cine-indigena-y-comunitario': 'CIC',
        'investigacion-sobre-cinematografia-y-audiovisual': 'CIN',
        'concurso-nacional-de-proyectos-de-investigacion-sobre-cinematografia-y-audiovisual': 'CIN',
        'nuevos-medios-audiovisuales': 'NMA',
        'concurso-nacional-de-proyectos-de-nuevos-medios-audiovisuales': 'NMA',
        'pilotos-de-serie': 'PDS',
        'concurso-nacional-de-pilotos-de-serie': 'PDS',
        'desarrollo-de-series': 'PDS',
        'distribucion-de-largometraje': 'CDL',
        'proyectos-de-distribucion-de-largometraje': 'CDL',
        'produccion-alternativa': 'PAL',
        'doblaje-de-obras-en-lenguas-originarias': 'DLO',
        'cortometrajes-del-bicentenario': 'CBI',
        'concurso-nacional-de-proyectos-cortometrajes-del-bicentenario': 'CBI',
        'cortometrajes-sobre-heroinas-peruanas': 'CBI',
        'proyectos-de-cortometrajes-sobre-heroinas-peruanas-en-el-marco-del-bicentenario': 'CBI',
        'estimulo-la-distribucion-cinematografica': 'EDI',
        'estimulo-a-la-distribucion-cinematografica': 'EDI',
        'concurso-nacional-de-distribucion': 'EDI',
        'estimulo-la-promocion-internacional': 'EPI',
        'estimulo-a-la-promocion-internacional': 'EPI',
        'promocion-internacional': 'EPI',
        'estimulo-la-preservacion-audiovisual': 'EPA',
        'estimulo-a-la-preservacion-audiovisual': 'EPA',
        'estimulo-la-formacion-audiovisual': 'CFO',
        'estimulo-a-la-formacion-audiovisual': 'CFO',
        'estimulo-la-formacion-de-publicos': 'FCP',
        'estimulo-la-formacion-de-publicos-traves-de-festivales-y-encuentros': 'FCP',
        'estimulo-a-la-formacion-de-publicos-a-traves-de-festivales-y-encuentros': 'FCP',
        'estimulo-al-fortalecimiento-de-capacidades': 'FCA',
        'premio-la-destacada-trayectoria-en-el-ambito-audiovisual': 'PDT',
        'premio-a-la-destacada-trayectoria-en-el-ambito-audiovisual': 'PDT',
        'destacada-trayectoria': 'PDT',
    }
    return code_map.get(slug, '')

def extract_pdf_links(html, page_url):
    """Extract PDF links from a concurso page."""
    pdfs = []
    for m in re.finditer(r'href="([^"]*\.pdf)"', html, re.IGNORECASE):
        url = m.group(1)
        if url.startswith('/'):
            url = BASE + url
        elif not url.startswith('http'):
            url = page_url.rstrip('/') + '/' + url.lstrip('/')
        pdfs.append(url)
    return list(set(pdfs))

def categorize_pdf(url):
    name = url.lower().split('/')[-1]
    name_no_ext = name.replace('.pdf', '')
    if 'fallo' in name_no_ext:
        return 'fallo_final'
    if 'beneficiario' in name_no_ext:
        return 'beneficiarios'
    if 'acta' in name_no_ext:
        if 'evaluacion' in name_no_ext or 'jurado' in name_no_ext:
            return 'acta_evaluacion'
        return 'acta'
    if 'jurado' in name_no_ext:
        return 'acta_evaluacion'
    if 'espera' in name_no_ext:
        return 'lista_espera'
    if 'ganadore' in name_no_ext:
        return 'resultados'
    if 'resultado' in name_no_ext:
        return 'resultados'
    return 'other'

def process_year(year):
    base_slug = "estimulos-economicos-para-la-actividad-cinematografica-y-audiovisual"
    if year == 2019:
        url = f"{BASE}/{year}/{base_slug}-2019"
    elif year == 2024:
        url = f"{BASE}/{year}/{base_slug}-{year}-edicion-bicentenario"
    else:
        url = f"{BASE}/{year}/{base_slug}-{year}"
    
    print(f"\n{'='*60}")
    print(f"Processing {year}...")
    print(f"URL: {url}")
    
    html = fetch(url)
    if not html:
        print(f"  ERROR: Could not fetch landing page")
        return {}
    
    concurso_links = extract_concurso_links(html)
    print(f"  Found {len(concurso_links)} concurso links")
    
    results = {}
    for link in concurso_links:
        ch = fetch(link)
        if not ch:
            print(f"  Could not fetch {link.split('/')[-1]}")
            slug = link.rstrip('/').split('/')[-1]
            code = 'UNKNOWN'
            results[code] = {'links': [], 'name': slug, 'pdfs': []}
            continue
        
        code = code_from_url(link)
        if not code:
            code = 'UNKNOWN'
        
        title_match = re.search(r'<title>(.*?)</title>', ch, re.DOTALL)
        title = title_match.group(1).strip() if title_match else link.split('/')[-1]
        # Clean title
        title = re.sub(r'\s*\|\s*Estímulos económicos para la cultura', '', title)
        
        pdfs = extract_pdf_links(ch, link)
        
        if code not in results:
            results[code] = {'name': title, 'pdfs': []}
        
        for pdf_url in pdfs:
            cat = categorize_pdf(pdf_url)
            results[code]['pdfs'].append({
                'url': pdf_url,
                'category': cat,
                'name': pdf_url.split('/')[-1]
            })
        
        n_resultados = sum(1 for p in results[code]['pdfs'] if p['category'] in ('fallo_final', 'beneficiarios', 'acta_evaluacion'))
        print(f"  {code:8s} | {title[:50]:50s} | {len(pdfs):2d} PDFs ({n_resultados} resultados)")
    
    return results

def main():
    all_results = {}
    years = [2019, 2020, 2021, 2022, 2023, 2024]
    if len(sys.argv) > 1:
        years = [int(y) for y in sys.argv[1:] if y.isdigit()]
    
    for year in years:
        results = process_year(year)
        all_results[year] = results
    
    out_path = os.path.expanduser("~/Projects/Analisis_Concursos_DAFO/dafo_pdfs_map.json")
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to {out_path}")

if __name__ == '__main__':
    main()
