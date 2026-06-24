"""
Batch OCR extraction for EDI 2019 and EPI 2019 scanned resolution PDFs.
"""
import subprocess, json, re, os, sys

DB = "/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db"
TESSDATA = "/tmp"

# Load PDF map
with open('/home/efrain/Projects/Analisis_Concursos_DAFO/dafo_pdfs_map.json') as f:
    MAP = json.load(f)

# Concurso info for EDI (20) and EPI (19)
CONCURSO = {"EDI": 20, "EPI": 19}

# Base URL
BASE = "https://estimuloseconomicos.cultura.gob.pe/sites/default/files/concursos/archivos/"

def ocr_pdf(pdf_url):
    """Download PDF, convert to images, OCR each page, return text."""
    fname = "/tmp/ocr_temp.pdf"
    subprocess.run(["curl", "-sLk", "-o", fname, pdf_url], capture_output=True, timeout=30)
    
    pages_text = []
    # Convert to images
    subprocess.run(["pdftoppm", "-png", "-r", "200", "-gray", fname, "/tmp/ocr_page"],
                   capture_output=True, timeout=30)
    
    # Find all pages
    for i in range(1, 10):  # max 9 pages
        img = f"/tmp/ocr_page-{i}.png"
        if not os.path.exists(img):
            break
        result = subprocess.run(
            ["tesseract", img, "stdout", "-l", "spa"],
            capture_output=True, text=True,
            env={**os.environ, "TESSDATA_PREFIX": TESSDATA},
            timeout=60
        )
        pages_text.append(result.stdout)
    
    # Cleanup
    subprocess.run(["rm", "-f", fname] + [f"/tmp/ocr_page-{i}.png" for i in range(1, 10)], capture_output=True)
    
    return "\n".join(pages_text)

def extract_data(text, line):
    """Extract beneficiary, project, amount, region from OCR text."""
    data = {"beneficiary": None, "project": None, "amount": None, "region": None}
    
    # Look for resolution table with columns: Persona Jurídica / Región / Proyecto / Monto
    # Pattern: the table usually has a row with entity name, region, project name, director, amount
    
    # Try to find structured data - look for S/ amount patterns near the table
    # The amount usually appears as: S/ X XX,XX or S/ XX XXX,XX
    
    # Find amounts
    amounts = re.findall(r'S/\s*([\d\s]+[,.]\d{2})', text)
    
    # Find the table section - usually after "Artículo Primero"
    # For EDI, the article says "Declárese como beneficiaria"
    # For EPI, similar
    
    # Look for beneficiary in text - usually appears in the considerando section
    # "Persona Jurídica beneficiaria, XXX"
    m = re.search(r'beneficiar[iao].*?[,\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+(?:S\.A\.C\.|E\.I\.R\.L\.|S\.R\.L\.|S\.A\.))', text)
    if m:
        data["beneficiary"] = m.group(1).strip()
    
    # Or look in table format
    if not data["beneficiary"]:
        m = re.search(r'(?:Jurídica|beneficiaria)[\s\n]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+(?:S\.A\.C\.|E\.I\.R\.L\.|S\.R\.L\.|S\.A\.))', text)
        if m:
            data["beneficiary"] = m.group(1).strip()
    
    # Find project name
    m = re.search(r'obra cinematográfica [""“]?([^""”\n]+)[""”]?', text)
    if m:
        data["project"] = m.group(1).strip()
    
    if not data["project"]:
        m = re.search(r'["""]([^"""]+)["""]', text)
        if m:
            data["project"] = m.group(1).strip()
    
    # Find region
    m = re.search(r'Región[\s\n]+([A-ZÁÉÍÓÚÑ]+(?:\s[A-ZÁÉÍÓÚÑ]+)*)', text)
    if m:
        data["region"] = m.group(1).strip()
    
    # Find amount - look for S/ amounts that aren't in considerando
    # The actual award amount is usually a specific value mentioned in the resolving section
    amounts_in_table = re.findall(r'(?:Monto|Estimulo|Premio)[\s\n]+S/\s*([\d\s]+[,.]\d{2})', text)
    if amounts_in_table:
        data["amount"] = amounts_in_table[-1]
    else:
        # Look for the amount in the table row - typically appears as S/XXX,XX
        amounts_near_table = re.findall(r'S/\s*(\d[\d\s]*[,.]\d{2})', text)
        if amounts_near_table:
            # Filter out amounts that are too large (budget) or too small
            for amt in amounts_near_table:
                clean = amt.replace(" ", "").replace(",", ".")
                try:
                    val = float(clean)
                    if 5000 <= val <= 200000:
                        data["amount"] = amt
                        break
                except:
                    pass
    
    return data

def insert_into_db(line, concurso_id, data, resol_num):
    """Insert extracted data into SQLite."""
    conn = subprocess.run(["sqlite3", DB], 
        input=f"""
        -- Create persona
        INSERT OR IGNORE INTO persona (tipo, razon_social, ruc, region)
        VALUES ('juridica', '{data["beneficiary"]}', 'SIN_RUC', '{data["region"] or "LIMA"}');
        
        -- Create proyecto
        INSERT OR IGNORE INTO obra (titulo)
        VALUES ('{data["project"]}');
        
        -- Check if already exists
        SELECT COUNT(*) FROM proyecto po
        JOIN persona p ON p.id=po.persona_beneficiaria_id
        JOIN obra ob ON ob.id=po.obra_id
        WHERE p.razon_social='{data["beneficiary"]}' AND ob.titulo='{data["project"]}'
        AND po.monto_otorgado={data["amount"]};
        """,
        capture_output=True, text=True)
    return conn.stdout.strip()

def process_all():
    results = []
    for line in ["EDI", "EPI"]:
        pdfs = MAP.get("2019", {}).get(line, {}).get("pdfs", [])
        beneficiarios = [p for p in pdfs if isinstance(p, dict) and p.get("category") == "beneficiarios"]
        
        print(f"\n{'='*60}")
        print(f"{line}: {len(beneficiarios)} beneficiario PDFs")
        print(f"{'='*60}")
        
        for pdf in beneficiarios:
            name = pdf.get("name", "")
            url = pdf.get("url", "")
            
            if not url.startswith("http"):
                url = BASE + url
            
            print(f"\n--- {name} ---")
            
            text = ocr_pdf(url)
            data = extract_data(text, line)
            
            print(f"  Beneficiary: {data['beneficiary']}")
            print(f"  Project: {data['project']}")
            print(f"  Amount: {data['amount']}")
            print(f"  Region: {data['region']}")
            
            # Extract resolution number
            m = re.search(r'(?:N[°º]?\s*)?(D\d{6}-\d{4}-DGIA[-\s]?V?M?P?C?I?C?/?(?:MC)?)', text)
            resol_num = m.group(1) if m else "UNKNOWN"
            print(f"  Resolution: {resol_num}")
            
            results.append({"line": line, "name": name, "data": data, "resol": resol_num})
    
    return results

if __name__ == "__main__":
    results = process_all()
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        d = r["data"]
        print(f"{r['line']:4s} | {str(d['beneficiary'])[:40]:40s} | {str(d['project'])[:30]:30s} | S/ {d['amount'] or '?':>10s} | {d['region'] or '?':10s}")
