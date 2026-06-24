# Diccionario de datos

Esquema completo en [[schema.sql]].

## Tablas

### `convocatoria`
Años de convocatoria (2019-2025).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | PK | |
| `anio` | INTEGER UNIQUE | Año de la convocatoria |
| `nombre` | TEXT | Nombre descriptivo |
| `activa` | BOOLEAN | |

### `linea_concursable`
Líneas de estímulo (EPI, CPF, CDO, etc.). 18 activas en 2025.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | PK | |
| `codigo` | TEXT UNIQUE | Código (EPI, CPF, ...) |
| `nombre_canonico` | TEXT | Nombre oficial |
| `tipo_beneficiario` | TEXT | `natural`, `juridica` o `ambos` |

### `concurso_anual`
Una línea específica en un año determinado.

### `modalidad`
Sub-categorías dentro de un concurso anual (ej: CPF-Desarrollo, CPF-Regiones).

### `persona`
Tabla unificada para personas naturales y jurídicas.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `tipo` | `natural` / `juridica` | |
| `nombres`, `apellidos` | TEXT | Solo para naturales |
| `dni` | TEXT | Solo para naturales |
| `razon_social` | TEXT | Solo para jurídicas |
| `ruc` | TEXT | Solo para jurídicas |
| `region` | TEXT | Departamento |

### `proyecto`
Una postulación beneficiada con estímulo económico.

### `proyecto`
Obra o proyecto presentado.

### `resolucion`
Resolución directoral o fallo final que oficializa los resultados.

### `proyecto_resolucion`
Relación M:N entre proyectos y resoluciones.

### `proyecto_integrante`
Equipo detrás de una postulación (responsable, director, presenta_a).

### `evento_internacional` / `proyecto_evento`
Solo para EPI: festivales, mercados, premios.

### `jurado`
Miembros del jurado por concurso.

### `documento`
PDFs asociados (bases, anexos, fe de erratas, resultados).

## Estados actuales

Ver [[DAFO_Auditoria_2026-06-13]].
