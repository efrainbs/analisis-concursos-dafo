import sqlite3

# Manually verified DNI -> (nombres, apellidos) mapping from RD 000780 PDF
# DB stores names in uppercase, so we match case-insensitively
dni_mapping = [
    ("46226944", "JUAN GABRIEL", "ARELLANO VILLEGAS"),
    ("73014800", "JUAN LEONARDO", "AVELLANEDA HUAMAN"),
    ("09887961", "MAGALI BETSABE", "BRUNO MORALES"),
    ("70275971", "FRIDA VICTORIA", "CARDENAS FIGUEROA"),
    ("72418472", "SAMUEL JOEL", "CHOQUEHUAYTA VALDERRAMA"),
    ("72971666", "VANESSA MARIVEL", "CONDE RODRIGUEZ"),
    ("71696154", "VIRNA VALERIA", "CUEVA YAIPEN"),
    ("70459818", "FERNAN GUILLERMO", "FERNANDEZ CANO"),
    ("45880583", "MIGUEL ANGEL", "FUENTES ARQQUE"),
    ("71775760", "NAYARITH LLASSIEL", "GASTULO LADINES"),
    ("72667849", "CARMEN DE LOS ANGELES", "HUAMAN FLORES"),
    ("73007061", "MIGUEL ANGEL", "HUAMAN MATEO"),
    ("48269054", "ELVIS", "HUAYTA PACSI"),
    ("44631838", "JAIR MAHOMET", "LOPEZ ALCALDE"),
    ("72522351", "WALTER FREDDY", "MANRIQUE CERVANTES"),
    ("41669383", "WALTHER AUGUSTO", "MARADIEGUE MONTARO"),
    ("44148735", "EDUARDO", "ORCADA VILLALVA"),
    ("76835899", "DIANA KAROL", "PUMALUNTO SOTO"),
    ("71438712", "LUIS JEAMPIERRE", "RAMOS APAZA"),
    ("75905509", "RODRIGO FRANCO", "RICRA MIRANDA"),
    ("44485950", "MARCIO ANDRE", "ROLANDO JARA"),
    ("71243089", "ANA CLAUDIA", "SALAS GUTIERREZ"),
    ("76645792", "ROLAN LUIS", "TAPAYURI SALAZAR"),
    ("45250030", "MERY LYCIA", "TERAN AYQUIPA"),
    ("72510960", "ROGER REYNALDO", "VELA SAAVEDRA"),
    ("18105682", "ALEJANDRO MANUEL", "AGREDA MEDRANO"),
    ("73237373", "NICOLAS ALEXANDER", "AGUILAR SAMANEZ"),
    ("47417140", "STEPHANIE GERALDINE", "ALTAMIRANO SALAZAR"),
    ("72943449", "SEBASTIAN ALEXIS", "ARIAS RUIZ"),
    ("71419013", "CARELLIA DALESKA", "BOLIVAR ESPINOZA"),
    ("46341275", "CLAUDIA STEFANY", "GONAZ DEL AGUILA"),
    ("78464796", "SANTIAGO RAMON", "HERRERA CLAPERS"),
    ("45629121", "MANUEL ALFONSO", "HIGUERAS CHICOT"),
    ("70165433", "LEONILDA", "HUMPIRI PUMA"),
    ("70258555", "JOSEPH SAMUEL", "LADRON DE GUEVARA COCA"),
    ("44271248", "JAVIER WILFREDO", "LARA CAMERE"),
    ("47507758", "NARDA KIARA", "LOZANO NUNEZ"),
    ("42815891", "MILAGROS GINA", "MELGAR CARI"),
    ("71418402", "TANYA MARLY", "MOLINA BERNALES"),
    ("48542900", "ROCIO LUCIA", "SAN MIGUEL BERAUN"),
    ("70578472", "JORGE ALEXANDER", "TALLEDO ROJAS"),
    ("60565020", "BETZABE MICOL", "TICERAN CABRERA"),
    ("77471358", "RODRIGO ENRIQUE", "VALENTI ALATTA"),
]

conn = sqlite3.connect('/home/efrain/Projects/Analisis_Concursos_DAFO/concursos_dafo.db')
cur = conn.cursor()

updated = 0
errors = []
for dni, nombres, apellidos in dni_mapping:
    cur.execute(
        "UPDATE persona SET dni = ? WHERE nombres = ? AND apellidos = ? AND tipo = 'natural'",
        (dni, nombres, apellidos)
    )
    if cur.rowcount > 0:
        updated += cur.rowcount
        print(f"  OK: {nombres} {apellidos} -> DNI {dni}")
    else:
        errors.append((nombres, apellidos, dni))
        print(f"  NOT FOUND: {nombres} {apellidos}")

conn.commit()
conn.close()
print(f"\nUpdated: {updated}")
if errors:
    print(f"Not found: {len(errors)}")
