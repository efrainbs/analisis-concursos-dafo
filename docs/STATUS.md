# DAFO Extraction — Status

> Última actualización: 2026-06-24 — Nombres con "/" y "S/" corregidos (33 nuevas personas creadas de splits)

## Estado actual de la DB

```
Año   Resols  Posts   Con mod   Total S/.
----  ------  -----   -------   ------------
2025     77    192     192      26,324,701
2024     92    196     196      24,878,096
2023    116    190     190      23,082,500
2022     80    172     172      18,894,532
2021    125    229     229      17,138,559
2020     25    139     139      18,529,338
2019     60    182     182      22,382,952
```

**Total: 1300 proyectos, 1166 obras, 2127 personas (731 jurídicas, 1396 naturales), 576 resoluciones, 121 eventos internacionales, S/ 151,230,678.**
**Cobertura de modalidad: 1300/1300 (100%).**
**Cobertura obra.tipo: 1166/1166 (100%).**

## Lo que se hizo (nuevo)

### EDI — modalidades asignadas (Comercial / Alternativa / En línea)
- `fix_edi_modalidades.py`: Extrajo el tipo de distribución de los 79 RDs individuales de EDI.
- **3 modalidades reales** identificadas desde los RDs: **Comercial** (42), **Alternativa** (33), **En línea** (4).
- Las modalidades se crearon por concurso_anual: cada año tiene sus propios registros "Comercial", "Alternativa" y "En línea" según corresponda.
- Los RDs se descargaron y parsearon automáticamente; el texto se normalizó (NFC) para manejar acentos descompuestos (NFC vs NFD).
- Las 7 modalidades genéricas anteriores ("Estímulo a la Distribución Cinematográfica" sin distinción de tipo) se eliminaron por huérfanas.
- **Resultado: 79/79 EDI con modalidad correcta.**

### EPI — duplicados corruptos eliminados + eventos limpiados
- `fix_eventos_epi.py`: Limpieza masiva de nombres de eventos internacionales.
- **5 proyectos EPI duplicados eliminados** (P61955–P61959) que tenían nombres de beneficiario corruptos por fuga de columnas del PDF. Ya existían récords limpios (P61973, P61974, P61976, P61978, P61983) con la misma resolución, obra y eventos.
- **117 eventos corregidos** en `evento_internacional`: nombres reparados (letras faltantes, prefijo `EVENTO RNACIONAL ULADO A LA TULACIÓN` eliminado), países asignados correctamente.
- **Resultado: 0 eventos con país "No especificado" o "ESPACIO FORMATIVO". 0 proyectos EPI con nombre corrupto.**

### Nombres con "/" y "S/" corregidos (vía `fix_nombres_slash.py`)
- **16 splits de dos personas** separados en récords individuales: IDs 7960, 8492, 8494, 8496, 8502, 8504, 8508, 8512, 8516, 8521, 8550, 8582, 8593, 8599, 8614, 9344.
- **2 splits de tres personas**: 8496 (GARCIA ANGULO + CABRERIZO REY DE CASTRO + ALVAN LEON), 8521 (NATERS ROMERO + RIVAS VIDAL + FLORES GUERRA BAMONDE).
- **2 splits de seis personas** para proyecto CGC 2021 (61106): 9188 desdoblado en QUINTANA REVOREDO, RAMIREZ PINTO, ALEMAN BERNAL, ZAPANA VILCA, VALVERDE VALDIVIA, MARTINEZ ALVARADO.
- **3 personas con "/" falso** (separador de columna en PDF, no dos personas) corregidos a una sola: 8132 (ANGEL EDUARDO PAJARES CRUZ), 9169 (LORENA ALEXANDRA NOBILE GANOZA), 9348 (SUSANNE KAROLINE PELIKAN RIVERA).
- **3 complejos multi-persona** desdoblados: 9069 (LOPEZ SARANGO + GUARNIZO HUISA), 9278 (SALINAS YABAR + CONDORI ARANGO), 9297 (ZELA VALDEZ + KRYSTEK GALDOS-TANGUIS), 9322 (MARTINEZ CABRERA DE RENZL + MARTINEZ ALARCON), 9354 (OBREGON ROSSI + MONTEAGUDO GAUVRIT), 9348 (PELIKAN RIVERA + ESPARZA SANTA MARIA + CASTILLO AGÜERO), 9268 (DENEGRI SANCHEZ + 3 más pendientes de verificar).
- **3 S/ monto artifacts** removidos: 9052 (ROY MELGAR CARI), 9082 (SONIA ANGELICA TOLEDO ONES / PEDRO VIZ VIVANCO).
- **2 garbled** con primera letra faltante: 7923 (LIZ A FERNANDEZ), 7944 (ANTONIO BILL — primera letra indeterminada).
- **14 casos complejos pendientes de verificación por calidad de PDF**: 8226 (EPA 2021 — RD sin tabla extraíble), 8581, 9069 (extra), 9188 (extra), 9268 (extra), 9297 (extra), 9322 (extra), 9344 (extra), 9348 (extra), 9354 (extra).
- **33 nuevas personas naturales** creadas (IDs 10662–10692) y vinculadas a sus proyectos como responsables.
- **Resultado: 0 personas con "/" o "S/" en nombres.**

### Dashboard rediseñado: sidebar fija + main
- Diseño de dos columnas con `dash-sidebar` (320px, sticky, scroll) y `dash-main` (flex 1).
- Sidebar contiene: título DASHBOARD, filtros (edición, línea, región, modalidad, avanzados), y controles (Métrica Cantidad/Monto, Gráfico Línea/Barra).
- Selector "Líneas para evolución" movido dentro del chart de evolución (a la derecha del título).
- Gráfico de evolución ocupa ancho completo; los otros 6 charts en grilla de 2 columnas.
- Alturas de canvas aumentadas progresivamente: 504px (charts) y 576px (evolución).
- **Resultado: controles agrupados en sidebar, más espacio para gráficos.**

### Página Proyectos: gray hero de 50vh
- Título "PROYECTOS" reemplazado por un bloque gris (`--neutral-30`) de 50vh a ancho completo debajo del menú.
- Título "PROYECTOS" movido al sidebar (encima de los filtros), mismo estilo que DASHBOARD.
- CSS `.page-title` simplificado (32px, sin sticky, sin gradient overlay).
- **Resultado: hero visual de bienvenida de media pantalla.**

### Fixes menores
- `legend: { display: false }` en charts de dataset único (Líneas, Rangos, Modalidades, Departamentos) para eliminar etiqueta "undefined".
- Query de departamentos corregida (incluye `SUM(monto_otorgado)` para soportar métrica Monto).
- Tag balance corregido en dashboard.html (sidebar-section faltaba cierre).

### Títulos de proyecto corregidos (11 proyectos)
- `fix_titulos_regiones.py`: 8 proyectos CDO 2022 tenían nombre de región como título (AREQUIPA, CUSCO, CAJAMARCA, CALLAO) por bug en extracción del PDF `2022-CDO-FalloFinal.pdf` (columna DEPARTAMENTO asignada como PROYECTO).
  - **60902**: AREQUIPA → A MI MANERA
  - **60903**: CUSCO → AUSANGATE (ESTUDIO DOSLADOS S.C.R.L.)
  - **60904**: CAJAMARCA → CARNAVAL
  - **60905**: CUSCO → CARTA A UNA MEMORIA SIN CORRESPONDER
  - **60906**: PRODUCCIONES MEMORIA SIN CUSCO GUTIERREZ → KUMBIERA
  - **60907**: PRODUCCIONES MEMORIA SIN CUSCO GUTIERREZ → LA VIOLENCIA QUE NO VES
  - **60908**: CALLAO → RAZÓN DE VER
  - **60909**: PRODUCCIONES MEMORIA SIN CUSCO GUTIERREZ → TURBIOS TRÓPICOS
- 3 proyectos EPI 2025 con título garbled corregido desde RDs individuales:
  - **61590** (FRANCO SEBASTIAN DADONE): → Pan y Mortadela
  - **61649** (JAVIER IGNACIO SALVADOR VARGAS): → EL ATRAPANIEBLAS
  - **61774** (KATTYA LORENA TULINI VALENCIA): → Festival Internacional de Cine Documental de Ámsterdam (Espacio de Formación)
- **Resultado: 0 proyectos con región como título. 5 obras huérfanas (antiguos títulos incorrectos) sin referencias.**

### UI: Región reemplazada por "Ver más" con expansión suave
- `templates/index.html`: Columna "Región" eliminada del header de resultados, reemplazada por "Ver más".
- Cada fila ahora tiene botón `Ver más [+]` que expande detalles con animación CSS (`max-height`/`opacity` transition, 0.35s ease).
- Región movida al panel expandido como primer campo de información adicional.
- **Resultado: Interfaz más limpia, expansión no brusca.**

### max-width unificado a 90vw + paleta azul oscuro
- `templates/index.html`, `dashboard.html`, `mapa.html`: `max-width: 1600px` → `90vw`.
- Paleta recalculada desde `#0D1B2A` (azul muy oscuro) como base, reemplazando `#000` en todos los tonos neutros (light y dark mode).

### Fix PDT — títulos corregidos y roles swap 2021
- Los 6 proyectos PDT ahora tienen `obra.titulo` = nombre del CANDIDATO(A) (persona reconocida) y `persona_beneficiaria` = PRESENTADOR.
- **2024**: 2 títulos corruptos corregidos (JULIO CESAR GONZALES OVIEDO, BELARMINA SOLAR BECERRA).
- **2021**: Roles swap corregido — los títulos tenían el nombre del presentador y la persona beneficiaria tenía al candidato. Ahora corresponde con los PDFs.
- **Resultado: PDT con datos correctos.**

### obra.tipo asignado por línea concursable
- Asignación manual de `obra.tipo` para líneas que tenían tipos mixtos o inconsistentes:
  - **CDC** (Distribución y Circulación) → `audiovisual` (12)
  - **CDL** (Distribución de Largometraje) → `distribucion` (2) _(nuevo tipo)_
  - **EDI** (Distribución Cinematográfica) → `distribucion` (79)
  - **FCP** (Formación de Públicos) → `gestion` (18)
- 2 proyectos EDI sin obra (60634 KINRA, 60990 VIAJE) resueltos con obra y tipo `distribucion`.
- **Resultado: 1351/1352 obras con tipo asignado.**

### obra.tipo visible en web app
- `server.py`: Agregado `ob.tipo as obra_tipo` al SELECT de búsqueda, con mapeo a etiqueta legible (audiovisual→"Obra audiovisual", formacion→"Formación", etc.).
- `templates/index.html`: El detalle de cada proyecto ahora muestra "Tipo de obra: Obra audiovisual / Formación / Preservación..."
- **Resultado: 1,148 obras con tipo visibles desde el buscador.**

### Integrantes insertados (777 registros)
- `fix_integrantes_regiones.py`: Insertó 777 integrantes faltantes para proyectos sin responsable/director.
- El beneficiario se usa como `director` (persona natural) o `responsable` (jurídica).
- 10 integrantes huérfanos (referenciaban proyectos inexistentes) eliminados.
- **Resultado: 479/479 naturales con integrante; 572/769 jurídicas con integrante.**

### Corrección de responsables en proyectos jurídicos (306 proyectos)
- `fix_responsables.py`: Extrajo responsables naturales de PDFs FalloFinal 2025 (columna RESPONSABLE).
  - 47 proyectos corregidos insertando la persona natural como responsable.
- `fix_old_fallos.py`: Extracción parcial de PDFs FalloFinal 2019-2024.
  - 4 proyectos 2020-CPC corregidos manualmente desde columna "DIRECTOR(ES/AS) DEL PROYECTO".
  - 252 proyectos antiguos: se eliminó la empresa como responsable (no se pudo extraer nombre confiable).
- `fix_juridicas_integrante.py` + `apply_integrante_fixes.py`: Re-extracción selectiva de FalloFinal PDFs.
  - 7 proyectos corregidos con nombres verificados manualmente en el PDF:
    - CCM 2024 (P60504): SUENA PERU → NORMA VELASQUEZ CHAVEZ
    - CGS 2025 (P61951): LEGAÑA DE PERRO → ALEX SANDER ARAGON TRUJILLO
    - CPF 2025 (P7308-P7312): 5 responsables de la línea P-R
  - ~77 proyectos FalloFinal sin solución por mala calidad de texto en PDFs antiguos (2019-2021).
  - **73 EDI sin integrante**: los RDs individuales no contienen columna RESPONSABLE (no extraíble).
- `fix_epa_integrante.py`: Re-extracción de responsables de EPA RDs 2021.
  - 1 proyecto corregido (P61873: GRETI PRODUCCIONES → FRANCISCO JOSE LOMBARDI OYARZU + EMILIO MOSCOSO MANRIQUE).
  - 9 EPA 2021 RDs restantes son PDFs escaneados (sin texto extraíble, necesitarían OCR).
- **Resultado: 0 proyectos con empresa como integrante. 211 jurídicas aún sin integrante.**

### Regiones normalizadas
- 958 personas con región NULL → `'SIN DATO'` (vía `fix_integrantes_regiones.py`).
- 80 personas nuevas (fix_responsables) también → `'SIN DATO'`.
- 5 regiones duplicadas unificadas (APURIMAC→APURÍMAC, JUNIN→JUNÍN, SAN MARTIN→SAN MARTÍN).
- **Resultado: 0% personas sin región. 1041 `'SIN DATO'`, 1038 con región real, 0 duplicados.**

### Categoria CGC completada
- `fix_categoria_cgc.py`: 28 proyectos CGC Anual/Multianual con categoria NULL → `'anual'`/`'multianual'`.
- 3 corruptos CPF Desarrollo corregidos: PRIMA/PRIMA ÓPERA/ÓPERA PRIMA ÓPERA → `'ÓPERA PRIMA'`.
- **Resultado: 59 proyectos con categoria (antes 31).**

### Fix de nombres corruptos (vía `fix_integrantes_regiones.py`)
- ~15 nombres con fragmentación o fuga de columna corregidos (ej: "CELESTE Y EL PEQUEÑO SAJINO" → responsable **Alicia Medina Revilla**).
- ~70% de nombres extraídos completos y correctos; ~15% con pequeña fuga de columna.

### CGC FEM 2025 — completado (3 beneficiarios insertados, 2 lista de espera corregidos)
- `insert_fem_2025_faltantes.py`: Insertó 3 proyectos faltantes del PDF 2025-CGC-FEM-Beneficiarios.pdf:
  - DEPA 514 E.I.R.L. — Festival de Cine de Trujillo (S/92,600)
  - FRAME & RENDER E.I.R.L. — Cine con Chifles 2026 (S/100,000)
  - OGECU — 8vo y 9no Festival Hecho por Mujeres y Disidencias (S/100,000)
- Corrigió P62014 y P62015 de `beneficiario` → `lista_espera` (resolución 001134-2025 confirmó lista de espera).
- **Resultado: CGC FEM 2025 completo: 13 beneficiarios + 2 lista de espera.**

### CFO 2025 — 43 beneficiarios insertados vía OCR
- `insert_cfo_2025.py`: El CFO 2025 tenía 0 proyectos (vs 34 en 2024). El PDF `2025-CFO-ActadeEvaluación.pdf` es un acta escaneada de 21 páginas.
- Se extrajeron 43 beneficiarios (personas naturales becadas para formación audiovisual) mediante OCR (tesseract).
- Clasificación: 23 formación corta (S/25,000 c/u) + 20 formación larga (S/45,000 c/u).
- **Resultado: CFO 2025 con 43 proyectos (S/1,595,000). Sin vínculo a resolución (el PDF no contiene fallo_final formal).**

### PDT 2025 — 1 beneficiario insertado
- `insert_pdt_2025.py`: Insertó el beneficiario del Premio a la Destacada Trayectoria 2025 desde RD 000903-2025.
- **VICTOR EDGAR RUIZ BOHORQUEZ** (Lima), presentado por ANDRÉS PAUL MAGALLANES MAGALLANES, S/20,000.

### MUTA Festival — duplicado eliminado y montos corregidos
- P61099 (X MUTA, S/0) eliminado como duplicado.
- P61307 (V MUTA 2020) monto corregido a S/92,600.
- P62100 (X MUTA 2025) insertado desde PDF FEM Beneficiarios (S/100,000).

## Lo que se hizo (anterior — resumen)

1. **Extracción principal** — `extract_2024.py` (2019-2024) + `extract_beneficiaries.py` (2025): 1248 proyectos, poblando obras, personas, resoluciones desde PDFs.
2. **Correcciones de montos** — 109 montos anómalos (<S/100) corregidos ×1000.
3. **Auditoría 2019-2023** — `insert_audit_2019_2023.py`: 31 beneficiarios extraídos manualmente (S/ 2,649,793).
4. **Lista de espera 2025** — `insert_lista_espera_2025.py`: 12 beneficiarios (S/ 3,272,500).
5. **Dedup EPI/EDI 2025** — duplicados consolidados (EPI 329→32, EDI 72→12).
6. **Modalidades Fase 1-2c** — Cobertura 100% (1248/1248) vía `assign_modalidades.py`, `assign_modalidades_cfo.py`, `assign_modalidades_cgc.py`, `assign_modalidades_fase2c.py`, `assign_modalidades_fase2c_restantes.py`, `assign_single_modalidades.py`.
7. **Fix CFR** — `fix_cfr_mapeo.py`: 12 proyectos CFR mal mapeados a CFO corregidos.
8. **Fix PDT 2025** — `fix_pdt_2025.py`: Proyecto duplicado eliminado, datos movidos a 2022.
9. **Full re-extraction attempt** (2026-06-18) — Re-intento fallido (pérdida de 163 proyectos), restaurado desde backup. Conclusión: abordaje selectivo es mejor.

## Lo que queda pendiente

### Calidad de datos
| Problema | Cantidad | % | Notas |
|----------|----------|---|-------|
| `persona.dni` faltante (naturales) | 1,119 | ~55% | Sin fuente sin re-procesar PDFs |
| `proyecto.categoria` vacío | 1,189 | 95.3% | No se poblará (redundante con modalidad o requiere re-extracción pesada) |
| `obra.tipo` vacío | 0 | 0% | 9 asignadas por línea (CDO, EPI → audiovisual); 195 huérfanas corruptas eliminadas |
| Jurídicas sin integrante | 219 | 27.3% | 73 EDI sin columna RESPONSABLE en RDs; ~77 FalloFinal con PDFs no parseables; 69 otros |
| `jurado.modalidad_id` NULL | 397 | 92.5% | No necesario (jurados van asociados a estímulo, no modalidad) |
| Regiones duplicadas | 0 | — | Resuelto |

### Otros
- ~~**Eventos EPI** — 45 proyectos EPI sin `proyecto_evento`~~ — ✅ Todos los EPI tienen evento. Nombres y países limpiados (vía `fix_eventos_epi.py`).
- **CFO 2025 sin resolución vinculada** — 43 proyectos sin `proyecto_resolucion` (el acta escaneada no es un fallo_final formal).
- **PDT 2025** — 1 proyecto insertado (VICTOR EDGAR RUIZ BOHORQUEZ, S/20,000, RD 000903-2025). Resuelto.
- ~~**CCM 2025: P61949, P61950 sin resolución**~~ — ✅ Vinculados a RD 001037-2025 (link huérfano P7359 eliminado).
- ~~**CGS 2025: P61951 sin resolución**~~ — ✅ Vinculado a RD 001087-2025.
- **~177 PDFs remanentes** con formato histórico no estándar.
- **RDs 001127–001133 (2025)** — investigar si existen en el portal.
- **~14 casos multi-persona parcialmente resueltos** — splits aplicados pero segundas/terceras personas pendientes de verificación por PDF sin texto extraíble.
- **Nuevas modalidades EDI**: Comercial/Alternativa/En línea (79/79 asignados) — verificar consistencia con las bases de cada año.
- **Documentos faltantes en `documents`** — El PDF `2025-CGC-FEM-Beneficiarios.pdf` no está registrado en la tabla `documents`.

## Datos clave

- **Jurídicas**: 801 total — 582 con integrante (responsable/director natural), 0 con empresa como integrante, 219 sin integrante.
- **Personas**: 2127 (1396 naturales, 731 jurídicas) — 1038 con región real, 1041 `'SIN DATO'`, 0 sin asignar.
- **33 nuevas personas naturales** creadas de splits de nombres con "/".
- **Líneas concursables**: 26 activas (CPF 181, EPI 160, CFO 144, CPC 94, CGC 89, etc.)
- **Flask app**: `server.py` (puerto 8501, `run_app.sh`). Dashboard con 6 charts + mapa Leaflet.

## Cómo retomar

```bash
cd /home/efrain/Projects/Analisis_Concursos_DAFO

# Ver estado actual
sqlite3 concursos_dafo.db \
  "SELECT c.anio, COUNT(po.id) AS posts, printf('%,.0f', SUM(po.monto_otorgado)) AS total
   FROM convocatoria c JOIN concurso_anual ca ON ca.convocatoria_id=c.id
   JOIN proyecto po ON po.concurso_anual_id=ca.id
   GROUP BY c.anio ORDER BY c.anio DESC;"

# Servidor web
bash run_app.sh
```

## Archivos relevantes

### Pipeline de extracción
- `extract_2024.py` — Parser PDFs históricos (2019-2024)
- `extract_beneficiaries.py` — Parser PDFs 2025
- `dafo_common.py` — Helpers (regiones, modalidades, query builder)

### Correcciones de datos
- `fix_integrantes_regiones.py` — Insertó 777 integrantes, fijó 958 regiones, eliminó 10 huérfanos
- `fix_responsables.py` — Extrajo responsables de PDFs FalloFinal 2025 (47 proyectos)
- `fix_old_fallos.py` — Extracción parcial FalloFinal 2019-2024
- `fix_cfr_mapeo.py` — Fix CFR mal mapeados (CFO→CPF/Regiones)
- `fix_pdt_2025.py` — Eliminación duplicado PDT
- `fix_anomalous_montos.py` — Corrección de 109 montos ×1000
- `fix_obra_titles.py` / `re_extract_obra_titles.py` — Corrección de títulos
- `fix_titulos_regiones.py` — Fix títulos = nombre de región + EPI garbled (11 proyectos)
- `fix_categoria_cgc.py` — Categoria CGC (Anual→anual, Multianual→multianual) + corruptos CPF
- `fix_juridicas_integrante.py` — Re-extracción de responsables de FalloFinal PDFs (dry-run)
- `apply_integrante_fixes.py` — Aplica 7 fixes manuales verificados de integrante
- `fix_epa_integrante.py` — Extracción de responsable de EPA RD579 (P61873)
- `fix_eventos_epi.py` — Limpieza masiva de nombres de eventos EPI (117 fixes)
- `fix_edi_modalidades.py` — Extracción de tipo de distribución EDI desde RDs (Comercial/Alternativa/En línea, 79 proyectos)
- `fix_nombres_slash.py` — Corrección de 35+ personas con "/" y "S/" en nombres (33 nuevas creadas de splits)
- `extract_epi_eventos.py` — Extracción de eventos internacionales de EPI RDs
- `insert_fem_2025_faltantes.py` — Insertó 3 proyectos faltantes CGC FEM 2025 + corrigió lista de espera
- `insert_cfo_2025.py` — Insertó 43 beneficiarios CFO 2025 vía OCR desde acta escaneada
- `insert_pdt_2025.py` — Insertó 1 beneficiario PDT 2025 (Premio a la Destacada Trayectoria)

### Modalidades
- `assign_modalidades.py` — Fase 1 (filename + artículo primero)
- `assign_modalidades_cfo.py` — Fase 2b CFO (monto canónico)
- `assign_modalidades_cgc.py` — Fase 2a CGC (históricos)
- `assign_modalidades_fase2c.py` — CPC/CDO/CPA pre-2024
- `assign_modalidades_fase2c_restantes.py` — CPF 2019-2021 + CPA 2025
- `assign_single_modalidades.py` — 20 líneas single-modalidad

### Web app
- `server.py` — Flask app (rutas: `/`, `/dashboard`, `/mapa`, `/api/dashboard`)
- `templates/dashboard.html` — Dashboard con Chart.js + AJAX
- `templates/mapa.html` — Mapa Leaflet coroplético
- `templates/index.html` — Búsqueda de proyectos
- `run_app.sh` — Lanzador (puerto 8501)

### Otros
- `audit_2019_2023.py` / `insert_audit_2019_2023.py` — Auditoría
- `insert_lista_espera_2025.py` — Lista de espera
- `scrape_dafo_pdfs.py` / `scrape_2025_pdfs.py` — Descarga de PDFs
- `extract_dni_ruc.py` — Intento de extracción DNI/RUC
- `concursos_dafo.db` — SQLite DB
- `dafo_pdfs_map.json` — Mapa de URLs de PDFs
- `schema.sql` / `seed.sql` — Esquema y semilla

## Backups

`concursos_dafo.db.pre_*` — snapshots antes de cada fix importante.
Más recientes: `pre_epi_garbled_fix` (antes de eliminar duplicados EPI), `pre_cfr_fix`, `pre_modalidades_cfo`, `pre_modalidades`, `pre_fase2c`.
