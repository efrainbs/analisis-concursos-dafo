"""Download CFO FalloFinal PDFs 2019-2024 and extract DNIs."""
import sqlite3
import urllib.request
import re
import tempfile
import subprocess
import os

conn = sqlite3.connect('/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db')
cur = conn.cursor()

# Get CFO FalloFinal PDFs for 2019-2024
cur.execute("""
    SELECT DISTINCT r.id, r.url_pdf, cv.anio
    FROM resolucion r
    JOIN concurso_anual ca ON r.concurso_anual_id = ca.id
    JOIN convocatoria cv ON ca.convocatoria_id = cv.id
    JOIN linea_concursable lc ON ca.linea_concursable_id = lc.id
    WHERE lc.codigo = 'CFO' AND r.tipo = 'fallo_final'
      AND cv.anio BETWEEN 2019 AND 2024
    ORDER BY cv.anio
""")

rows = cur.fetchall()
print(f"Found {len(rows)} CFO FalloFinal PDFs to process\n")

for rid, url, anio in rows:
    print(f"=== CFO {anio} (resolucion_id={rid}) ===")
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            pdf_path = tmp.name
        print(f"  Downloading {url} ...")
        urllib.request.urlretrieve(url, pdf_path)
        
        # Extract text
        txt_path = pdf_path + '.txt'
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, txt_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  pdftotext failed: {result.stderr}")
            os.unlink(pdf_path)
            continue
        
        with open(txt_path) as f:
            text = f.read()
        
        # Count lines
        lines = text.split('\n')
        print(f"  PDF lines: {len(lines)}")
        
        # Find all DNI patterns
        dnis_found = re.findall(r'\((\d{8})\)', text)
        print(f"  DNI entries found: {len(dnis_found)}")
        
        # Show sample context for each DNI
        for i, line in enumerate(lines):
            m = re.search(r'\((\d{8})\)', line)
            if m:
                dni = m.group(1)
                # Look backwards for name
                before = []
                for j in range(i-1, max(i-8, -1), -1):
                    clean = lines[j].strip()
                    if not clean or clean in ('-', '|'):
                        continue
                    before.insert(0, clean)
                context = ' '.join(before[-4:]) if before else ''
                print(f"    DNI {dni} <- ... {context}")
        
        os.unlink(pdf_path)
        if os.path.exists(txt_path):
            os.unlink(txt_path)
            
    except Exception as e:
        print(f"  Error: {e}")

conn.close()
