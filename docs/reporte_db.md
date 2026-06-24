# Reporte DB — Estímulos Económicos DAFO

Fecha: 2026-06-17 (actualizado)

## Resumen

| Métrica | Valor |
|---------|------:|
| Proyectos | 1,248 |
| Personas únicas | 1,946 |
| Resoluciones | 573 |
| Monto total otorgado | **S/ 147,233,729.93** |
| Años cubiertos | 2019–2025 |
| Líneas concursables | 26 |
| Modalidades definidas | 54 |
| Proyectos con modalidad | 395 (32%) |

## Totales por Año

| Año | Proyectos | Total Otorgado | Con modalidad |
|----:|:-------------:|:--------------:|:-------------:|
| 2025 | 138 | S/ 22,279,403 | 64 (46%) |
| 2024 | 196 | S/ 24,878,096 | 112 (57%) |
| 2023 | 187 | S/ 22,772,950 | 31 (17%) |
| 2022 | 172 | S/ 18,894,532 | 46 (27%) |
| 2021 | 230 | S/ 17,188,559 | 74 (32%) |
| 2020 | 139 | S/ 18,529,338 | 29 (21%) |
| 2019 | 186 | S/ 22,690,852 | 37 (20%) |

## Totales por Línea Concursable

| Línea | Proyectos | Total | Promedio |
|:------|:-------------:|:-----:|:--------:|
| CPF — Proyectos de Ficción | 169 | S/ 61,469,373 | S/ 363,724 |
| CDO — Proyectos de Documental | 65 | S/ 17,358,916 | S/ 267,060 |
| CFO — Formación Audiovisual | 156 | S/ 10,054,664 | S/ 64,453 |
| EDI — Distribución Cinematográfica | 81 | S/ 7,645,050 | S/ 94,383 |
| CPA — Proyectos de Animación | 49 | S/ 6,170,827 | S/ 125,935 |
| CGC — Gestión para el Audiovisual | 89 | S/ 5,538,992 | S/ 62,236 |
| CCM — Coproducciones Minoritarias | 17 | S/ 5,357,580 | S/ 315,152 |
| EPA — Preservación Audiovisual | 55 | S/ 5,239,325 | S/ 95,260 |
| CPC — Proyectos de Cortometrajes | 94 | S/ 3,888,965 | S/ 41,372 |
| FCA — Fortalecimiento de Capacidades | 80 | S/ 3,378,732 | S/ 42,234 |
| CGS — Salas de Exhibición Alternativa | 21 | S/ 3,376,115 | S/ 160,767 |
| CCC — Cine en Construcción | 25 | S/ 3,041,893 | S/ 121,676 |
| PDS — Pilotos de Serie / Desarrollo de Series | 33 | S/ 2,403,104 | S/ 72,821 |
| CIC — Cine Indígena y Afrodescendiente | 11 | S/ 2,196,100 | S/ 199,645 |
| FCP — Formación de Públicos | 18 | S/ 2,079,974 | S/ 115,554 |
| EPI — Promoción Internacional | 160 | S/ 1,329,967 | S/ 8,312 |
| NMA — Nuevos Medios Audiovisuales | 17 | S/ 1,153,320 | S/ 67,842 |
| CDV — Desarrollo de Videojuegos | 13 | S/ 1,149,050 | S/ 88,388 |
| CDC — Distribución y Circulación de Obras | 12 | S/ 1,010,850 | S/ 84,238 |
| CIN — Investigación sobre Cinematografía | 26 | S/ 890,000 | S/ 34,231 |
| CBI — Cortometrajes del Bicentenario | 13 | S/ 879,800 | S/ 67,677 |
| CCE — Creación Experimental | 27 | S/ 607,981 | S/ 22,518 |
| PAL — Producción Alternativa | 3 | S/ 570,000 | S/ 190,000 |
| CDL — Distribución de Largometraje | 2 | S/ 182,322 | S/ 91,161 |
| DLO — Doblaje en Lenguas Originarias | 2 | S/ 179,830 | S/ 89,915 |
| PDT — Premio a la Destacada Trayectoria | 10 | S/ 81,000 | S/ 8,100 |

## Cobertura de Modalidades

| Línea | Sin modalidad | Años | Nota |
|:------|:-------------:|:----:|:-----|
| EPI | 160 | 2019-2025 | RDs individuales; modalidad = evento (ver `proyecto_evento`) |
| ~~CFO~~ | 0 | — | **Cubierto 100%**: Fase 2b (144) + fix CFR (12 movidas a CPF/Regiones) |
| EDI | 81 | 2019-2025 | RDs individuales |
| FCA | 80 | 2022-2023 | RDs individuales (FCA) |
| CGC | 56 | 2019-2021,2023 | **Fase 2a parcial** (21 asignadas 2022+2024). 56 restantes: 2019-2021 "categoría anual" histórica + 2023 RD compuesta ambigua |
| CPC | 66 | 2019-2023 | Fallos consolidados sin estructura (cruzar actas) |
| EPA | 55 | 2019-2025 | RDs individuales |
| CDO | 42 | 2019-2023 | Fallos consolidados sin estructura |
| PDS | 33 | 2019-2023 | Línea single-modalidad |
| CPA | 33 | 2019-2023,2025 | Fallos consolidados |
| CPF | 30 | 2019-2021 | "Largo ficción"/CEA/CFN-plain sin sub-código |
| CCE | 27 | 2019-2025 | Single-modalidad |
| CIN | 26 | 2019-2025 | Single-modalidad |
| CCC | 25 | 2019-2025 | Single-modalidad |
| CGS | 21 | 2019-2025 | Single-modalidad |
| Resto | 94 | — | FCP/NMA/CCM/CDV/CDC/CIC/PDT/etc. |

## Correcciones Aplicadas

| Corrección | Cantidad |
|:-----------|:--------:|
| Montos < S/100 corregidos (×1000) | 109 |
| Montos S/100–S/1000 corregidos (×1000) | (incluidos arriba) |
| Montos < S/1000 mantenidos (fuera de rango) | 2 (CGC 2019) |
| Montos cero mantenidos (error de parseo) | 1 (CPA 2025) |
| Resoluciones duplicadas eliminadas | 1 |
| Resoluciones huérfanas eliminadas | 6 |
| Duplicados EPA 2025 consolidados | 30 |
| **Modalidades asignadas Fase 1 (filename + a1)** | **141** |
| **Modalidades definidas creadas Fase 1 (CPF 2019-2023)** | **10** |
| **Modalidades asignadas Fase 2b CFO (monto canónico)** | **144** |
| **Modalidades definidas creadas Fase 2b (CFO 2019-2024)** | **9** |
| **Fix CFR 2020/2021/2022: posts movidas CFO→CPF/Regiones** | **12** |
| **Modalidades creadas fix CFR (Regiones CPF 2020-2022)** | **3** |
| **Modalidades asignadas Fase 2a CGC (monto+sección/single)** | **21** |
| **Modalidades creadas Fase 2a (Festivales CGC 2022)** | **1** |

## Anomalías Remanentes

1. **Proyecto 61395** — CGC 2019, S/ 491.90. ×1000 = S/491,900 fuera de rango CGC (30k–120k). Parseo incorrecto de tabla.
2. **Proyecto 61396** — CGC 2019, S/ 500.00. Mismo caso.
3. **Proyecto 61541** — CPA 2025, S/ 0.00. Título "RESPONSABLE(S) PROYECTO DEL PROYECTO" — error de parseo, no se pudo determinar el monto real.

## Limitaciones Conocidas

- **Modalidades**: 853/1248 proyectos sin modalidad (68%). Fase 1 cubrió CPF/CPC/CPA/CDO/CGC 2024-2025 y CPF 2019-2023 por sub-código de filename + ARTÍCULO PRIMERO. Fase 2b cubrió CFO 2019-2024 (144) por inferencia canónica de monto. Fase 2a cubrió CGC 2024 (13) por encabezados `Categoría:` + monto y CGC 2022 (8) single-categoría. Fix CFR 2020/2021/2022 (12 posts) movidos a CPF/Regiones. Pendiente: CGC 2019-2021/2023 (56, "categoría anual" histórica o RD compuesta), Fase 2c CPC/CDO/CPA pre-2024, single-modalidad (EPI/EDI/EPA/FCA).
- **DNI/RUC**: 1035 personas naturales sin DNI, 401 jurídicas sin RUC. Los PDFs 2019–2022 no incluían esta información en las tablas publicadas.
- **Integrantes**: 777/1248 proyectos (62%) sin integrantes en `proyecto_integrante`.
- **Eventos EPI**: 136 proyectos EPI sin evento vinculado en `proyecto_evento`.
- **PDFs pendientes**: ~177 PDFs con formato histórico no estándar no fueron procesados.
- **Nombres partidos**: Algunos nombres de persona natural se dividieron incorrectamente entre `nombres` y `apellidos`.

---

## Historial de cambios

### 2026-06-17 — Modalidades Fase 2a CGC (21 asignaciones)

Script: `assign_modalidades_cgc.py`. Backup: `concursos_dafo.db.pre_modalidades_cgc`.

CGC tiene dos modalidades canónicas (nombres DB):
- **'Festivales, encuentros y muestras'** (PDF: 'Promoción y difusión')
- **'Fortalecimiento de capacidades'** (PDF: 'Formación y fortalecimiento de capacidades')

Método por año:
- **2024** (13 posts): encabezados `Categoría: X:` en ARTÍCULO PRIMERO
  validan inferencia por monto (umbral S/70k: ≤70k→Festivales, >70k→
  Fortalecimiento). 6 Festivales (S/49-50k) + 7 Fortalecimiento (S/89-100k).
- **2022** (8 posts): single-categoría. ARTÍCULO PRIMERO sin encabezados,
  montos homogéneos S/48-50k (todos festivales). Asignados a 'Festivales,
  encuentros y muestras'.

No asignados (56 posts, requieren inspección manual):
- 2019-2021 (46): ART PRIMERO declara 'categoría anual' (categoría histórica
  que no mapea a las 2024). Montos sugieren 2 grupos pero sin encabezados.
- 2023 (10): RD compuesta (001087+001243), sin encabezados `Categoría:`
  en ART PRIMERO. Inferencia por monto ambigua (considerando declara
  Promoción S/120k + Formación S/500k, montos no cuadran limpiamente).

1 modalidad nueva creada (Festivales CGC 2022). 2024 reutilizó existentes.
Cobertura con modalidad: 374 → 395 (32%).

### 2026-06-17 — Fix bug mapeo CFR 2020/2021/2022 (12 posts)

Script: `fix_cfr_mapeo.py`. Backup: `concursos_dafo.db.pre_cfr_fix`.

`extract_2024.py` mapeaba los FallosFinal CFR a la línea CFO, pero CFR es
"Concurso de Proyectos de Largometraje de Ficción exclusivo para las
regiones" → realmente **CPF, modalidad Regiones**. Mismo bug ya detectado
para CFR 2023 (corregido en Fase 1 vía sub-código histórico CFR→Regiones,
pero solo aplicaba si la línea ya era CPF; aquí la línea asignada era CFO).

Movidas 12 proyectos (2 de 2020, 7 de 2021, 3 de 2022) de CFO a CPF,
junto con sus 3 resoluciones (rid 6634, 6520, 6443). Creadas 3 modalidades
"Regiones" en CPF 2020/2021/2022.

| Año | Posts | Monto |
|----:|----:|----:|
| 2020 | 2 | S/ 1,000,000 |
| 2021 | 7 | S/ 3,640,000 |
| 2022 | 3 | S/ 1,650,000 |

Resultado: **CFO 100% cubierto** (0 sin modalidad). CFR 2019-2023 ahora
todos en CPF/Regiones (21 posts total). Montos intactos (verificado vs backup).

### 2026-06-17 — Modalidades Fase 2b CFO (144 asignaciones)

Script: `assign_modalidades_cfo.py` (no destructivo, solo UPDATE de `modalidad_id`).
Backup: `concursos_dafo.db.pre_modalidades_cfo`.

CFO tiene dos modalidades canónicas: **'Formación corta'** (≤S/25k) y
**'Formación larga'** (>S/25k, tope S/45k), definidas en las bases del concurso
(líneas 168-172 del PDF 2024). Método principal: **inferencia por monto**
(canónico y robusto). Validación cruzada con:
- **Columna MODALIDAD** de la tabla 2024 (Jurado + 2da Fase): coincidencia
  13/13 con la inferencia por monto (validado).
- **ARTÍCULO PRIMERO** 'categoría formación corta/larga' (2019, 2020):
  engañoso en fallos multi-categoría (2019 CFO tiene Art. Primero=corta y
  Art. Segundo=larga), por lo que se usa solo como info, no para asignación.

**EXCLUYE** resoluciones CFR (url_pdf LIKE '%CFR%'): 12 posts mal mapeados
a CFO en `extract_2024.py` (son realmente CPF/Regiones). Corregidos
posteriormente con `fix_cfr_mapeo.py` (ver entrada de historial).

| Año | Posts | Corta | Larga |
|----:|----:|----:|----:|
| 2024 | 34 | 15 | 19 |
| 2023 | 18 | 18 | 0 |
| 2022 | 9 | 9 | 0 |
| 2021 | 55 | 14 | 41 |
| 2020 | 13 | 13 | 0 |
| 2019 | 15 | 11 | 4 |

9 modalidades nuevas creadas (CFO 2019-2024). Cobertura con modalidad:
218 → 362 (29%).

### 2026-06-17 — Modalidades Fase 1 (141 asignaciones)

Script: `assign_modalidades.py` (no destructivo, solo UPDATE de `modalidad_id`).
Backup: `concursos_dafo.db.pre_modalidades`.

Para cada postulación sin modalidad, agrupada por resolución, deriva la modalidad
de: (1) sub-código del filename (CPF-D→Desarrollo, CPC-OP→Ópera prima, CDE→CPF
Desarrollo, CFN→Nuevos realizadores/Tercer, CFR→Regiones, etc.); (2) fallback
ARTÍCULO PRIMERO del PDF (`modalidad de 'X'` / `categoría de 'X'` con comillas
curvas). Solo asigna en casos de confianza (RD de modalidad única). Fallos
consolidados multi-modalidad se dejan para Fase 2.

| Año | Línea | Posts | Modalidades |
|----:|:------|----:|:------|
| 2025 | CPF | 18 | Desarrollo, Nuevos realizadores, Regiones, Tercer largometraje a más |
| 2025 | CPC | 12 | Ópera prima, Segunda obra a más |
| 2025 | CPA | 4 | Cortometrajes |
| 2025 | CGC | 10 | Festivales/encuentros/muestras, Fortalecimiento de capacidades |
| 2025 | CDO | 8 | Desarrollo, Producción |
| 2023 | CPF | 13 | Nuevos realizadores (a1), Tercer largometraje a más (a1), Regiones |
| 2022 | CPF | 26 | Desarrollo, Nuevos realizadores, Tercer largometraje a más |
| 2021 | CPF | 12 | Desarrollo |
| 2020 | CPF | 16 | Desarrollo |
| 2019 | CPF | 22 | Desarrollo, Regiones |

10 modalidades nuevas creadas (CPF 2019-2023). 2024/2025 reutilizaron las
modalidades ya definidas. Cobertura con modalidad: 77 → 218 (17%).

### 2026-06-17 — Auditoría 2019-2023 + lista de espera 2025

**Auditoría 2019-2023: 31 beneficiarios insertados (S/ 2,649,793)**

13 PDFs no procesados por `extract_2024.py`, extraídos manualmente con
datos limpios. Script: `insert_audit_2019_2023.py`.

Bugs de mapeo corregidos en `extract_2024.py` (detectados, no fixeados en
el script original):
- `2020-CDI-FalloFinal.pdf` → CIN (estaba mapeado a CDL)
- `2020-CLC-FalloFinal.pdf` → CCC (estaba mapeado a CDL)
- `2021-CLC-FalloFinal.pdf` → CCC (estaba mapeado a CDL)

| Año | Línea | RD | Posts | Monto |
|----:|:------|:---|----:|------:|
| 2020 | CIN | 000370-2020-DGIA/MC | 5 | S/ 150,000 |
| 2020 | CCC | 000405-2020-DGIA/MC | 5 | S/ 618,421 |
| 2020 | EDI | 6 RDs individuales | 6 | S/ 729,800 |
| 2021 | CCC | 000469-2021-DGIA/MC | 4 | S/ 563,445 |
| 2023 | CCE | 001176-2023-DGIA/MC | 4 | S/ 114,628 |
| 2023 | CDC | 001115-2023-DGIA/MC | 3 | S/ 229,500 |
| 2023 | EPA | 000989-2023-DGIA/MC | 2 | S/ 224,000 |
| 2023 | PDT | 001040-2023-DGIA/MC | 2 | S/ 20,000 |

PDFs sin beneficiarios (NO insertados, legítimo):
- 2020 CDC: no publicó fallo final (solo acta de compromiso)
- 2023 CCE/CDC/EPA/PDT RDs de aptos/finalistas/jurado (sin monto)

Gaps cerrados:
- 2020: CIN 0→5, CCC 2→7, EDI 0→6
- 2021: CCC 3→7
- 2023: CCE 0→4, CDC 0→3, EPA 0→2, PDT 0→2

Duplicados preexistentes detectados (no de esta auditoría):
- EPA 2021: GRETI PRODUCCIONES y PONTIFICIA UNIVERSIDAD CATÓLICA (2 c/u)

### 2026-06-17 — Lista de espera 2025 + fixes UX app

**RD 001134-2025-DGIA-VMPCIC/MC (12-Dic-2025) — Lista de espera**
- Detectada RD faltante: la última del año 2025, que declara beneficiarios
  promovidos desde la lista de espera cuando quedaron recursos.
- Fuente: `2025-DAFO-ListaDeEspera.pdf` (consolidado, 477KB).
- 12 nuevos beneficiarios insertados (S/ 3,272,500) en 5 líneas:
  - CPF: +4 (Nuevos realizadores ×2, Desarrollo ×1, Tercer largometraje ×1) = S/ 2,080,000
  - CPC: +3 (Ópera prima ×2, Segunda obra ×1) = S/ 180,000
  - CGC: +2 (Festivales ×2) = S/ 120,000
  - CDO: +2 (Desarrollo ×1, Producción ×1) = S/ 440,000
  - CPA: +1 (Cortometrajes ×1) = S/ 92,500
- Art. 10° notifica a ESCUELA DE CINE DE LIMA que no hay recursos para declararla.
- Script: `insert_lista_espera_2025.py`.
- Resolución creada con `tipo='lista_espera'` (id=6719).

**Verificación dedup EPI/EDI 2025**
- Confirmado que la reducción EPI 329→32 y EDI 72→12 fue correcta:
  eran duplicados exactos (mismo obra_id, monto, RD).
  Ej: KATTYA TULINI tenía 62 posts idénticos del proyecto 327.

**UX app — filtros y búsquedas**
- `onchange="this.form.submit()"` en yf/yt/tp/mm/checkboxes la.
- Botón Apply visible junto a filtros de año.
- `toggleAdv()` sincroniza input oculto `adv`.
- `adv_active` en server.py: auto-abre Advanced si hay filtros avanzados.
- Template auto-recarga; server reiniciado (PID 68470).
