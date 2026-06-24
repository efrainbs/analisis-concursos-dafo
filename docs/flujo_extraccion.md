# Diagrama de Flujo — Extracción DAFO

```mermaid
flowchart TB
    subgraph WEB["🌐 Web scraping (scrape_dafo_pdfs.py)"]
        A1["Visitar estimuloseconomicos.cultura.gob.pe<br>/{year}/estimulos-economicos-..."]
        A2["Extraer links de páginas<br>de cada concurso"]
        A3["Visitar cada página<br>/concursos/{slug}"]
        A4["Extraer URLs de PDFs<br>de todas las secciones (doc-1..doc-4)"]
        A5["Categorizar PDFs por nombre:<br>fallo_final, beneficiarios,<br>acta_evaluacion, lista_espera, other"]
        A6["Output: dafo_pdfs_map.json<br>{year: {codigo: {pdfs: [...]}}}"]
        A1 --> A2 --> A3 --> A4 --> A5 --> A6
    end

    subgraph DB_SCHEMA["🗄️ DB pre-seed (schema.sql + seed.sql)"]
        B1["convocatoria<br>(2019..2025)"]
        B2["linea_concursable<br>(EPI, CPF, CDO...)"]
        B3["concurso_anual<br>(unión convocatoria × línea)"]
        B4["modalidad<br>(Desarrollo, Ópera prima...)"]
        B1 --> B3
        B2 --> B3 --> B4
    end

    subgraph EXTRACT["⚙️ Extracción (extract_2024.py)"]
        C0["Leer dafo_pdfs_map.json"]
        C0a["Consultar DB existente<br>para IDs de concurso_anual<br>y modalidad"]

        subgraph FALLO["Tipo A — FalloFinal<br>(CPF, CDO, CPC, CPA, CDV...)"]
            F1["Descargar PDF con curl"]
            F2["Convertir a layout-text<br>con pdftotext -layout"]
            F3["Normalizar Unicode (NFC)"]
            F4["Extraer número de RD<br>y fecha 'San Borja, dd de mes del yyyy'"]
            F5["Ubicar ARTÍCULO PRIMERO<br>con regex"]
            F6["Detectar columnas de tabla<br>via keywords en headers<br>(PERSONA, REGIÓN, PROYECTO,<br>MONTO, CATEGORÍA...)"]
            
            subgraph F7_BRANCH["Estrategia de parseo"]
                F7A["¿Hay RUC en datos?"]
                F7A -->|"Sí"| F7RUC["Split por líneas con RUC<br>→ blocks = [[líneas]]"]
                F7A -->|"No"| F7MONTO["¿Hay columna MONTO<br>con datos?"]
                F7MONTO -->|"Sí"| F7M["Split monto-anchored:<br>blank line completa bloque,<br>split con sufijo legal<br>(S.A.C., E.I.R.L., S.R.L.)"]
                F7MONTO -->|"No"| F7G["Agrupar por blank lines"]
            end

            F7_PARSE["Por cada bloque extraer:<br>• razón_social / RUC<br>• región<br>• proyecto<br>• monto<br>• responsable/director<br>• evento (EPI)"]
            
            F8["Resolver nombres de región<br>parciales (AYEQUE→LAMBAYEQUE)"]
            F9["Limpiar razón social<br>(quitar RUC, puntuación<br>sobrante)"]
            F10["fixed_monto: fallback<br>desde preámbulo si<br>columna individual falla"]
        end

        subgraph RD["Tipo B — RD individual<br>(EPI, EDI, EPA)"]
            R1["Descargar PDF con curl"]
            R2["pdftotext -layout"]
            R3["Normalizar Unicode (NFC)"]
            R4["Extraer RD + fecha"]
            R5["Ubicar RESUELVE →<br>Artículo Primero"]
            R6["Detectar tipo:<br>Persona Natural o Jurídica"]
            
            subgraph R6_BR["Parseo por tipo"]
                R6N["Natural:<br>• Buscar DNI backward<br>• Nombre: líneas previas<br>• Evento: regex entre<br>ESTÍMULO y S/<br>• País: matching lista<br>• Región: matching"]
                R6J["Jurídica:<br>• Buscar RUC<br>• Razón social: líneas<br>previas a RUC N°<br>• Proyecto: párrafos<br>posteriores<br>• Responsable: (DNI)<br>en texto"]
            end

            R7["Parser unificado<br>(parse_epi_like)"]
            R8["fixed_monto: fallback<br>desde preámbulo"]
        end

        subgraph MULTI_RD["Tipo B2 — RD multi-beneficiario<br>(misma lógica que FalloFinal)"]
            M1["Usar parse_fallo_beneficiaries<br>con detect_table_columns<br>para columnas dinámicas"]
        end

        C1["Generar sentencias SQL<br>con INSERT para cada entidad"]
        
        C1_DEDUP["Lógica de dedup:<br>• persona: WHERE NOT EXISTS<br>  por RUC, DNI o nombre<br>• proyecto: INSERT OR IGNORE<br>• resolución: WHERE NOT EXISTS<br>  por url_pdf<br>• postulación: por concurso+persona<br>• proyecto_integrante: ON CONFLICT IGNORE"]
    end

    subgraph DB_POP["💾 Poblado de DB"]
        D1["concursos_dafo.db<br>(SQLite)"]
        D2["Tablas pobladas:"]
        D2E1["• persona (natural/jurídica)"]
        D2E2["• proyecto"]
        D2E3["• proyecto<br>(concurso + persona +<br>proyecto + monto)"]
        D2E4["• resolucion<br>(número, fecha, tipo, url)"]
        D2E5["• proyecto_resolucion<br>(M:N link)"]
        D2E6["• proyecto_integrante<br>(responsable, director)"]
        D2E7["• evento_internacional<br>• proyecto_evento<br>(solo EPI)"]
        
        D3["Ejecución:<br>--dry-run → stdout SQL<br>--run → sqlite3.executescript()"]
    end

    subgraph FILTERS["🧹 Filtros y limpieza aplicados"]
        E1["Saltar page headers/footers<br>(PATRIMONIO CULTURAL,<br>clave:, motos de año)"]
        E2["Ignorar RDs de listas<br>'aptas' o 'finalistas'<br>(no otorgan estímulos)"]
        E3["LIMA en columna empresa<br>→ tratar como vacío"]
        E4["Strip caracteres no<br>alfanuméricos en bordes<br>de razón social"]
        E5["Región: word boundaries<br>para evitar falsos ICA<br>dentro de CÓSMICA"]
        E6["Blank line handler:<br>siempre guarda bloque<br>aún sin monto"]
    end

    A6 --> C0
    C0 --> F1
    C0 --> R1
    C0 --> M1
    C0a --> C1
    
    F1 --> F2 --> F3 --> F4 --> F5 --> F6 --> F7_BRANCH
    F7RUC --> F7_PARSE
    F7M --> F7_PARSE
    F7G --> F7_PARSE
    F7_PARSE --> F8 --> F9 --> F10 --> C1

    R1 --> R2 --> R3 --> R4 --> R5 --> R6
    R6 --> R6_BR
    R6_BR --> R7 --> R8 --> C1

    M1 --> C1

    C1 --> C1_DEDUP --> C0a

    C1 -->|dry_run| D3
    C1 -->|--run| D3
    D3 --> D1
    D1 --> D2
    D2 --> D2E1
    D2 --> D2E2
    D2 --> D2E3
    D2 --> D2E4
    D2 --> D2E5
    D2 --> D2E6
    D2 --> D2E7

    F7_BRANCH -.-> FILTERS
    F7_PARSE -.-> FILTERS
    C1 -.-> FILTERS

    style WEB fill:#e1f5fe,stroke:#0288d1
    style DB_SCHEMA fill:#f3e5f5,stroke:#7b1fa2
    style EXTRACT fill:#fff3e0,stroke:#e65100
    style FALLO fill:#ffe0b2,stroke:#e65100
    style RD fill:#ffe0b2,stroke:#e65100
    style MULTI_RD fill:#ffe0b2,stroke:#e65100
    style DB_POP fill:#e8f5e9,stroke:#2e7d32
    style FILTERS fill:#fce4ec,stroke:#c62828
```

## Resumen del recorrido

| Fase | Script | Entrada | Salida |
|------|--------|---------|--------|
| **Scraping** | `scrape_dafo_pdfs.py` | `estimuloseconomicos.cultura.gob.pe` | `dafo_pdfs_map.json` (URLs de PDFs por año/código) |
| **Extracción** | `extract_2024.py` | `dafo_pdfs_map.json` + `concursos_dafo.db` (lookups) | Sentencias SQL INSERT |
| **Poblado** | `extract_2024.py --run` | SQL generado en memoria | `concursos_dafo.db` (SQLite) |
| **Seed** | `schema.sql` + `seed.sql` | SQL | `concursos_dafo.db` (estructura + datos semilla) |

### Tipos de parseo por concurso

- **FalloFinal (tabla multi-beneficiario):** CPF, CDO, CPC, CPA, CDV, CGC, CFO, CCC, CCM, CDC, CGS, CIN, CCE, CIC
- **RD individual (single-entry):** EPI (natural), EDI (jurídica), EPA (jurídica)
- **RD multi-beneficiario:** Todos los demás códigos detectados como `other` que contienen `-RD` en el filename
