# Auditoría de datos — 2026-06-13

## Resumen

| Métrica | Valor |
|---------|-------|
| Proyectos | 1,063 |
| Personas | 2,221 |
| Resoluciones | 505 |
| Total otorgado | S/ 112,247,930.77 |
| Montos cero | 0 ✅ |
| Montos NULL | 0 ✅ |
| Montos negativos | 0 ✅ |

## Hallazgos

### Críticos

#### Falta masiva de DNI/RUC
- **1,077** de 1,171 personas naturales (92%) sin DNI
- **791** de 1,050 personas jurídicas (75%) sin RUC
- **Causa probable:** el parser no extrae el campo de documento de identidad de los PDFs
- **Impacto:** no se puede cruzar con RENIEC/SUNAT
- **Acción:** modificar `extract_2024.py` para capturar DNI y RUC desde las tablas

#### Montos anómalos
~82 proyectos con montos < S/ 1,000 que no corresponden a los valores reales:

| Línea | Año | Cantidad | Rango |
|-------|-----|----------|-------|
| EPI | 2024-2025 | 4 | S/ 5.39 - S/ 10.00 |
| CFO | 2023 | 18 | S/ 8.24 - S/ 25.00 |
| CPA | 2023-2025 | 13 | S/ 50.00 - S/ 90.00 |
| CPC | 2025 | 6 | S/ 57.20 - S/ 60.00 |
| CDO | 2024 | 4 | S/ 38.10 - S/ 40.00 |
| ... | | ~82 | |

**Muestra validada manualmente:** `validacion_pdfs/` contiene 12 PDFs para cotejar.

#### Resolución duplicada
`001167-2024-DGIA-VMPCIC/MC` insertada 2 veces en tabla `resolucion` (IDs 5383 y 5384), vinculada a las mismas 7 proyectos CPC 2024.

### Moderados

| Issue | Cantidad |
|-------|----------|
| Resoluciones huérfanas (sin postulación) | 8 |
| Duplicado exacto EPI 2025 (post 7246/?) | 1 |
| Personas sin región | 1,162 (52%) |

## Muestra de validación

Ver carpeta `validacion_pdfs/`. Descargados 12 PDFs de:
- 3 controles (montos normales)
- 3 montos anómalos
- 3 sin DNI
- 3 sin RUC
