# Análisis de Concursos DAFO

**Estimulos Económicos para la Actividad Cinematográfica y Audiovisual**
Ministerio de Cultura del Perú — Dirección del Audiovisual, la Fonografía y los Nuevos Medios

## Mapas del proyecto

- [[DAFO_Data_Dictionary|Diccionario de datos (esquema DB)]]
- [[DAFO_Extraction_Pipeline|Pipeline de extracción]]
- [[DAFO_Auditoria_2026-06-13|Auditoría de datos (2026-06-13)]]
- [[STATUS|Estado actual del poblamiento]]

## Referencias externas

- [Portal DAFO](https://estimuloseconomicos.cultura.gob.pe)
- [[modelo_base_datos|Modelo de base de datos (documentación)]]
- [[flujo_extraccion|Diagrama de flujo de extracción]]
- [[evolucion_2019_2025|Evolución histórica de líneas concursables]]

## Archivos fuente

| Script | Propósito |
|--------|-----------|
| `extract_2024.py` | Parser PDFs históricos (2019-2024) |
| `extract_beneficiaries.py` | Parser PDFs 2025 |
| `scrape_dafo_pdfs.py` | Crawler del portal DAFO |
| `schema.sql` | Esquema SQLite |
| `seed.sql` | Datos semilla |

## Base de datos

- [[concursos_dafo.db]] (SQLite)
- 14 tablas, 1,248 proyectos, 1,946 personas, 573 resoluciones
- S/ 147.2M en estímulos otorgados (2019-2025)
- 53 modalidades definidas; 374 proyectos con modalidad (30%)

## Pendientes

- [ ] [[reporte_db#Cobertura de Modalidades|Fase 2a modalidades]] — CGC (encabezados Categoría)
- [ ] [[reporte_db#Cobertura de Modalidades|Fase 2c]] — CPC/CDO/CPA pre-2024 (cruzar actas)
- [ ] [[reporte_db#Limitaciones Conocidas|Poblar integrantes]] (777 sin integrantes)
- [ ] [[reporte_db#Limitaciones Conocidas|Vincular eventos EPI]] (136 sin evento)
- [ ] [[reporte_db#Limitaciones Conocidas|Extraer DNI/RUC]] (1035 naturales, 401 jurídicas)
- [ ] [[DAFO_Auditoria_2026-06-13#Resolución duplicada|Limpiar resolución duplicada]]
- [ ] Procesar ~177 PDFs remanentes
- [x] [[reporte_db#2026-06-17 — Fix bug mapeo CFR|Fix bug CFR]] — 12 posts CFO→CPF/Regiones, CFO 100% cubierto
- [x] [[reporte_db#2026-06-17 — Modalidades Fase 2b CFO|Modalidades Fase 2b CFO]] — 144 asignadas
- [x] [[reporte_db#2026-06-17 — Modalidades Fase 1|Modalidades Fase 1]] — 141 asignadas
