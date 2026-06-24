#!/usr/bin/env python3
"""
Batch-fix garbled EPI event names in evento_internacional.
Only updates names/countries in-place — never deletes or remaps.
"""
import os, re, sqlite3, sys

DB = os.path.join(os.path.dirname(__file__), 'concursos_dafo.db')
DRY_RUN = '--run' not in sys.argv

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

fixes = []

def fix(event_id, nombre=None, pais=None):
    fixes.append((event_id, nombre, pais))

# --- Known event mappings (verified via RDs or user) ---
fix(69, nombre='FESTIVAL DE CINE DE SANTIAGO', pais='Chile')
fix(70, nombre='SALÓN DE PRODUCTORES Y PROYECTOS CINEMATOGRÁFICOS FICCALI', pais='Colombia')
fix(72, pais='Brasil')  # BrLab
fix(76, nombre='SALÓN DE PRODUCTORES Y PROYECTOS CINEMATOGRÁFICOS FICCALI', pais='Colombia')
fix(78, pais='Panamá')  # ACAMPADOC
fix(79, nombre='FESTIVAL INTERNACIONAL DE CINE DE LOCARNO / LOCARNO INTERNATIONAL FILM FESTIVAL', pais='Suiza')
fix(85, nombre='Inside Out', pais='Canadá')
fix(87, nombre='Festival Internacional de Cine de Sao Paulo', pais='Brasil')
fix(89, nombre='FESTIVAL INTERNACIONAL DE CINE DOCUMENTAL DE ÁMSTERDAM / IDFA, INTERNATIONAL DOCUMENTARY FILMFESTIVAL AMSTERDAM', pais='Países Bajos')
fix(90, pais='España')
fix(91, nombre='FESTIVAL DE CINE IBEROLATINOAMERICANO DE TRIESTE', pais='Italia')
fix(92, nombre='Festival Internacional de Cine de Guadalajara', pais='México')
fix(93, nombre='SANFIC, FESTIVAL INTERNACIONAL DE CINE DE SANTIAGO', pais='Chile')
fix(94, pais='EE.UU')
fix(95, nombre='FESTIVAL INTERNACIONAL DE CINE DEL CAIRO / CAIRO INTERNATIONAL FILM FESTIVAL', pais='Egipto')
fix(96, nombre='Festival Internacional de Cine de Guadalajara', pais='México')
fix(97, pais='Suiza')
fix(98, nombre='FESTIVAL DE SAN SEBASTIÁN / DONOSTIA ZINEMALDIA', pais='España')
fix(99, pais='Argentina')
fix(101, nombre='Festival Internacional de Animación de Annecy', pais='Francia')
fix(103, pais='Canadá')  # Toronto documentary festival
fix(104, nombre='Festival Internacional de Cine de Viña del Mar FICVIÑA', pais='Chile')
fix(105, nombre='FIDOCS, FESTIVAL INTERNACIONAL DE DOCUMENTALES', pais='Chile')
fix(106, pais='Suiza')  # FIFDH Geneva
fix(107, nombre='FESTIVAL DES 3 CONTINENTS', pais='Francia')
fix(109, nombre='Festival Internacional de Cine de Karlovy Vary / Karlovy Vary International Film Festival', pais='República Checa')
fix(110, nombre='FESTIVAL BIARRITZ AMÉRICA LATINA / FESTIVAL BIARRITZ AMÉRIQUE LATINE', pais='Francia')
fix(111, pais='Francia')
fix(112, pais='España')
fix(114, nombre='FESTIVAL DE CINE DE TURÍN', pais='Italia')
fix(115, nombre='FESTIVAL INTERNACIONAL DE CINE DE SAN SEBASTIÁN / DONOSTIA ZINEMALDIA', pais='España')
fix(116, nombre='Festival Internacional de Cine de Guadalajara', pais='México')
fix(117, nombre='FESTIVAL DE CINE DE ROMA', pais='Italia')
fix(118, nombre='Festival Internacional de Cine de la India - GOA', pais='India')
fix(119, nombre='Cine Qua Non LAB', pais='México')
fix(120, nombre='Festival Internacional de Cine de Guadalajara', pais='México')
fix(122, nombre='FESTIVAL INTERNACIONAL DE CINE DE LOCARNO / LOCARNO INTERNATIONAL FILM FESTIVAL', pais='Suiza')
fix(123, nombre='Festival de Cine de las Alturas', pais='Argentina')
fix(124, nombre='FESTIVAL INTERNACIONAL DE CINE DOCUMENTAL DE ÁMSTERDAM / IDFA, INTERNATIONAL DOCUMENTARY FILMFESTIVAL AMSTERDAM', pais='Países Bajos')
fix(126, nombre='Festival Internacional de Cine de Guadalajara', pais='México')
fix(129, pais='Chile')  # FICWALLMAPU
fix(131, nombre='Festival Internacional de Cine de Tesalónica', pais='Grecia')
fix(132, nombre='Premios Ariel', pais='México')
fix(134, nombre='FESTIVAL INTERNACIONAL DE CINE DE LOCARNO / LOCARNO INTERNATIONAL FILM FESTIVAL', pais='Suiza')
fix(135, nombre='FANTASOLAB', pais='Argentina')
fix(136, nombre='Festival Internacional de Cine de Monterrey', pais='México')
fix(137, nombre='Festival Internacional de Cine de Valdivia', pais='Chile')
fix(138, nombre='Festival Internacional de Cine de Viña del Mar FICVIÑA', pais='Chile')
fix(139, pais='México')  # SHORTS MÉXICO
fix(140, nombre='Festival Biarritz América Latina', pais='Francia')
fix(143, nombre='Festival Internacional de Animación de Annecy', pais='Francia')
fix(145, nombre='VENTANA SUR', pais='Argentina')
fix(146, nombre='Festival Biarritz América Latina', pais='Francia')
fix(150, nombre='Sundance Film Festival', pais='EE.UU')
fix(151, nombre='Festival Internacional de Cine de Guadalajara', pais='México')
fix(152, nombre='Festival de Cine de Montevideo', pais='Uruguay')
fix(153, nombre='Premios Goya', pais='España')
fix(154, nombre='Festival de Málaga', pais='España')
fix(155, nombre='Festival de Cine de las Alturas', pais='Argentina')
fix(157, nombre='DocsMX', pais='México')
fix(158, nombre='Lab Guion', pais='Colombia')
fix(159, nombre='Lab Guion', pais='Colombia')
fix(160, pais='Colombia')  # FICCali
fix(161, pais='Chile')  # SANFIC
fix(163, nombre='SANFIC, FESTIVAL INTERNACIONAL DE CINE DE SANTIAGO', pais='Chile')
fix(164, nombre='SANFIC, FESTIVAL INTERNACIONAL DE CINE DE SANTIAGO', pais='Chile')
fix(165, nombre='Bolivia Lab', pais='Bolivia')
fix(166, nombre='FESTIVAL INTERNACIONAL DE CINE DOCUMENTAL DE BUENOS AIRES FIDBA', pais='Argentina')
fix(167, nombre='Encuentro Documental de los Otros - EDOC', pais='Ecuador')
fix(168, nombre='Encuentro Documental de los Otros - EDOC', pais='Ecuador')
fix(169, pais='Reino Unido')  # BFI London
fix(170, nombre='FESTIVAL DE SAN SEBASTIÁN / DONOSTIA ZINEMALDIA', pais='España')
fix(171, nombre='Pixelatl', pais='México')
fix(173, nombre='MIA, Mercado Audiovisual Internacional', pais='Italia')
fix(175, nombre='Festival Internacional de Cine Doclisboa', pais='Portugal')
fix(176, nombre='Festival Internacional de Cine de Valdivia', pais='Chile')
fix(177, nombre='Festival Internacional de Cine de Sao Paulo', pais='Brasil')
fix(178, nombre='Black Nights Film Festival - PÖFF', pais='Estonia')
fix(179, nombre='Canary Islands International Film Market', pais='España')
fix(180, nombre='Nativa Festival', pais='Brasil')
fix(181, nombre='FESTIVAL INTERNACIONAL DE CINE DOCUMENTAL DE BUENOS AIRES FIDBA', pais='Argentina')
fix(182, nombre='FESTIVAL DES 3 CONTINENTS', pais='Francia')
fix(183, pais='Países Bajos')  # IDFA
fix(184, nombre='GOSHORTS', pais='México')
fix(186, nombre='Black Nights Film Festival - PÖFF', pais='Estonia')
fix(188, pais='España')
fix(189, pais='Chile')
fix(190, pais='España')
fix(192, pais='Argentina')
fix(196, pais='EE.UU')
fix(197, pais='España')
fix(199, pais='Francia')
fix(200, pais='Chile')
fix(202, pais='Brasil')
fix(203, pais='España')
fix(204, pais='Argentina')
fix(205, pais='Países Bajos')
fix(214, nombre='FESTIVAL INTERNACIONAL DEL NUEVO CINE LATINOAMERICANO DE LA HABANA', pais='Cuba')
fix(223, pais='México')
fix(224, pais='México')
fix(226, pais='Francia')
fix(229, pais='Chile')
fix(231, pais='Colombia')
fix(232, pais='México')
fix(233, nombre='FECIR FESTIVAL INTERNACIONAL DE CINE RENGO', pais='Chile')
fix(234, pais='Bolivia')
fix(235, pais='Colombia')
fix(236, pais='Colombia')
fix(237, pais='España')
fix(238, pais='EE.UU')
fix(239, pais='Portugal')
fix(241, pais='España')
fix(242, pais='Cuba')
fix(243, pais='México')
fix(244, pais='México')
fix(245, pais='Estados Unidos')
fix(246, pais='Francia')

# --- Remaining auto-repairs for garbled names ---
# Algorithmic fixes for events with missing first letters
all_rows = db.execute("SELECT id, nombre, pais FROM evento_internacional ORDER BY id").fetchall()

for row in all_rows:
    eid, name, country = row['id'], row['nombre'], row['pais']
    # Skip if already in explicit fixes list
    if any(f[0] == eid for f in fixes):
        continue
    
    orig = name
    # Extract from known garbage prefixes
    name = re.sub(r'^EVENTO\s+RNACIONAL\s+ULADO\s+A\s+LA\s+TULACI[ÓO]N\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^RNACIONA\s+NCULADO\s+A\s+LA\s+TULACI[ÓO]N\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^NACIONAL\s+LADO\s+A\s+LA\s+E\s+ULACI[ÓO]N\s+', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^[,\s]+', '', name)
    
    # Fix leading truncated festival
    name = re.sub(r'^ESTIVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    name = re.sub(r'^STIVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    name = re.sub(r'^TIVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    name = re.sub(r'^IVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    name = re.sub(r'^VAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    
    # Fix INTERNACIONAL truncations
    name = re.sub(r'\bRNACIONAL\b', 'INTERNACIONAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bRNACIONA\b', 'INTERNACIONAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bNTERNACIONAL\b', 'INTERNACIONAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bNACIONAL\b', 'INTERNACIONAL', name, flags=re.IGNORECASE)
    
    # Fix FESTIVAL truncations in middle of name
    name = re.sub(r'\bESTIVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bSTIVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bTIVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bIVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bFESTVAL\b', 'FESTIVAL', name, flags=re.IGNORECASE)
    
    # Fix CINE truncations
    name = re.sub(r'\bINE\b', 'CINE', name, flags=re.IGNORECASE)
    name = re.sub(r'\bE CINE\b', 'DE CINE', name, flags=re.IGNORECASE)
    
    # Fix other known truncations
    name = re.sub(r'\bIMENTAL\b', 'DOCUMENTAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bUMENTAL\b', 'DOCUMENTAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bUMENTALES\b', 'DOCUMENTALES', name, flags=re.IGNORECASE)
    name = re.sub(r'\bOCUMENTAL\b', 'DOCUMENTAL', name, flags=re.IGNORECASE)
    name = re.sub(r'\bOCUMENTALES\b', 'DOCUMENTALES', name, flags=re.IGNORECASE)
    name = re.sub(r'\bIMACIÓN\b', 'ANIMACIÓN', name, flags=re.IGNORECASE)
    name = re.sub(r'\bANIMACI[OÓ]N\b', 'ANIMACIÓN', name, flags=re.IGNORECASE)
    name = re.sub(r'\bCORTROMETRAJES\b', 'CORTOMETRAJES', name, flags=re.IGNORECASE)
    
    # Fix "DE DE" → "DE", "E " → "DE "
    name = re.sub(r'\bDE DE\b', 'DE', name, flags=re.IGNORECASE)
    name = re.sub(r'\bE\b', 'DE', name, flags=re.IGNORECASE)
    
    # Remove "S/" monetary artifacts
    name = re.sub(r'S/', '', name)
    name = re.sub(r'\s+S\s+', ' ', name)
    
    # Remove virtual artifacts
    name = re.sub(r'\s+éxico\s*-\s*virtual\s*\)?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+ombia\s*-\s*virtual\s*\)?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+rancia\s*-\s*virtual\s*\)?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+Unido\s*-\s*virtual\s*\)?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+virtual\s*\)?', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[()]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    name = re.sub(r'\s*[,;]+\s*$', '', name)
    name = re.sub(r'^\s*[,;]+\s*', '', name)
    
    if name != orig and len(name) >= 5:
        fix(eid, nombre=name)

print(f"Total fixes to apply: {len(fixes)}")

if DRY_RUN:
    print("\nDRY RUN — usa --run para aplicar")
    for eid, nombre, pais in fixes:
        changes = []
        if nombre:
            old = db.execute("SELECT nombre FROM evento_internacional WHERE id=?", (eid,)).fetchone()[0]
            if old != nombre:
                changes.append(f"nombre: '{old[:50]}' → '{nombre[:50]}'")
        if pais:
            old = db.execute("SELECT pais FROM evento_internacional WHERE id=?", (eid,)).fetchone()[0]
            if old != pais:
                changes.append(f"pais: '{old}' → '{pais}'")
        if changes:
            print(f"  ID {eid}: {'; '.join(changes)}")
else:
    for eid, nombre, pais in fixes:
        if nombre:
            db.execute("UPDATE evento_internacional SET nombre = ? WHERE id = ?", (nombre, eid))
        if pais:
            db.execute("UPDATE evento_internacional SET pais = ? WHERE id = ?", (pais, eid))
    db.commit()
    print(f"Aplicados {len(fixes)} fixes")

db.close()
