# Análisis de Concursos DAFO - Estímulos Económicos para la Actividad Cinematográfica y Audiovisual

## Fuente

https://estimuloseconomicos.cultura.gob.pe/2025/estimulos-economicos-para-la-actividad-cinematografica-y-audiovisual-2025

Ministerio de Cultura del Perú - Dirección del Audiovisual, la Fonografía y los Nuevos Medios (DAFO).

---

## Alcance del análisis

- Página principal de la convocatoria 2025
- Las 18 páginas individuales de concurso (cards)
- PDFs de resultados (doc-4) de una muestra representativa de concursos
- Páginas de ediciones anteriores (2019–2024)

---

## Concursos 2025 (18 líneas)

| # | Código | Nombre | Tipo beneficiario |
|---|---|---|---|
| 1 | EPI | Estímulo a la promoción internacional | Persona natural |
| 2 | EDI | Estímulo a la distribución cinematográfica | Persona jurídica |
| 3 | CPF | Concurso de proyectos de ficción | Persona jurídica |
| 4 | CDO | Concurso de proyectos de documental | Persona jurídica |
| 5 | CGC | Concurso de proyectos de gestión para el audiovisual | Persona jurídica |
| 6 | CFO | Concurso para la formación audiovisual | — |
| 7 | CPC | Concurso de proyectos de cortometrajes | Persona jurídica |
| 8 | CCC | Concurso de cine en construcción | — |
| 9 | CPA | Concurso de proyectos de animación | Persona jurídica |
| 10 | PDT | Premio a la destacada trayectoria en el ámbito audiovisual | Persona natural |
| 11 | EPA | Estímulo a la preservación audiovisual | Persona jurídica |
| 12 | CIC | Concurso de video y cine indígena y afrodescendiente comunitario | Persona jurídica |
| 13 | CCM | Concurso de coproducciones minoritarias | — |
| 14 | CDC | Concurso de distribución y circulación de obras | — |
| 15 | CGS | Concurso de salas de exhibición alternativa | — |
| 16 | CDV | Concurso de desarrollo de videojuegos | Persona jurídica |
| 17 | CIN | Concurso de proyectos de investigación sobre cinematografía y audiovisual | — |
| 18 | CCE | Concurso de creación experimental | — |

### Subcategorías / Modalidades por concurso

| Concurso | Modalidades |
|---|---|
| CPF (Ficción) | Desarrollo, Nuevos realizadores, Regiones, Tercer largometraje a más |
| CDO (Documental) | Desarrollo, Producción |
| CPC (Cortometrajes) | Ópera prima, Segunda obra a más |
| CPA (Animación) | Cortometrajes, Desarrollo/Preproducción/Producción/Desarrollo de series |
| CDV (Videojuegos) | Preproducción, Producción |
| CGC (Gestión) | Festivales/encuentros/muestras, Fortalecimiento de capacidades |
| EPI, EDI, EPA, CIC, etc. | Sin subcategorías |

---

## Tipos de documento por concurso

Cada página de concurso tiene 4 secciones de documentos (doc-1 a doc-4). El doc-4 ("Documentos del resultado del concurso") contiene los PDFs de resultados que pueden ser de dos tipos:

### Tipo A: Fallo final único (lista múltiple de ganadores en una resolución)

Un solo PDF que declara a todos los beneficiarios. El artículo 1° contiene una tabla con:

- Persona jurídica (RUC) + Razón social
- Región
- Proyecto
- Categoría (si aplica: Ópera prima, Segunda obra a más, etc.)
- Responsable(s) del proyecto
- Director(es/as) del proyecto (solo en ficción)
- Monto otorgado

Además incluye una "Lista de espera" con la misma estructura.

Concursos con este formato: CPF, CDO, CPC, CPA, CDV, CGC, CFO, CCC, CCM, CDC, CGS, CIN, CCE, CIC.

### Tipo B: Resoluciones individuales por beneficiario

Un PDF por cada beneficiario. Cada resolución contiene:

- Persona natural: DNI, nombres completos, región, proyecto/evento, monto
- Persona jurídica: RUC, razón social, región, proyecto, responsable (DNI), monto

Concursos con este formato: EPI, EDI, EPA, PDT.

---

## Datos relevantes extraídos de PDFs

### EPI - Estímulo a la Promoción Internacional (persona natural)

```
Macarena Coello Neyra (DNI 47028030) - Lima
Proyecto: Allq'u
Evento: Salón de Productores y Proyectos Cinematográficos FICCali (Colombia)
Modalidad: Presencial
Monto: S/ 6,000.00
```

### CPF - Concurso de Proyectos de Ficción / Desarrollo (persona jurídica)

```
Aurora Films S.A.C. (RUC 20614112604) - Olguin Falcon, Zoila Alessandra
Proyecto: Javiera, Escucha Esto
Categoría: Ópera prima
Directora: Olguin Falcon, Zoila Alessandra
Monto: S/ 40,000.00
```

### CDV - Concurso de Desarrollo de Videojuegos / Preproducción (persona jurídica)

```
Kon Juegos S.A.C. (RUC 20603385137) - Lima
Proyecto: Runa Lazos Espirituales 2025
Responsable: Ballon Sevillano, Roberto Jose
Monto: S/ 60,000.00
```

### CIC - Concurso de Video y Cine Indígena (persona jurídica)

```
Federación de Comunidades Nativas del Ampiyacu (FECONA) (RUC 20567123309) - Loreto
Proyecto: Fiesta Baaja Voces del Ampiyacu
Responsables: Quevare Garcia, Deyser Royer / Arbilde Rios, Maritza
Monto: S/ 200,000.00
```

### EDI - Estímulo a la Distribución Cinematográfica (persona jurídica)

```
Cine Aymara Studios E.I.R.L. (RUC 20448736301) - Puno
Obra: Los Indomables
Monto: S/ 100,000.00
```

### PDT - Premio a la Destacada Trayectoria (persona natural)

```
Candidato: Victor Edgar Ruiz Bohorquez (DNI 07058224) - Lima
Presentado por: Andrés Paul Magallanes Magallanes (DNI 09867917)
Monto: S/ 20,000.00
```

---

## Estructura del sitio web

- Plataforma: Drupal 11
- Cada página de año: `/2025`, `/2024`, etc.
- Cada concurso: `/2025/concursos/{slug}`
- Documentos almacenados en: `/sites/default/files/concursos/archivos/doc-{1,2,3,4}/`
- PDFs de resultados en doc-4

---

## Evolución histórica 2019–2025

| Año | Concursos | Cambios clave |
|---|---|---|
| **2019** | 22 | Año base del programa. Sufijo `(2019)` en títulos. Cortometrajes del Bicentenario. |
| **2020** | 22 | COVID. Se elimina "Distribución de Largometraje". Primer split en convocatorias. |
| **2021** | **23** | Se agregan Videojuegos, Animación, Premio Trayectoria. Nacen categorías "Estímulo a...". |
| **2022** | **25** (pico) | Se agregan Cine Indígena, Doblaje en Lenguas Originarias, Fortalecimiento de Capacidades. |
| **2023** | 23 | "Pilotos de Serie" → "Desarrollo de series". Desaparece Doblaje. |
| **2024** | **17** (mínimo) | Edición Bicentenario. Fusión ficción regional/nacional. Desaparecen Nuevos Medios, Creación Experimental, Cine en Construcción. |
| **2025** | 18 | Recuperación leve. Aparece Creación Experimental y Proyectos Inmersivos. |

### Líneas que han existido algún año pero no en otros

| Línea | Años activos |
|---|---|
| Cortometrajes del Bicentenario | 2019, 2024 |
| Doblaje en Lenguas Originarias | 2022 |
| Pilotos de Serie / Desarrollo de Series | 2019–2023 |
| Producción Alternativa | 2021 |
| Nuevos Medios Audiovisuales | 2019–2023 |
| Cine en Construcción | 2019–2023 |
| Creación Experimental | 2019–2023, 2025 |
| Estímulo a la Formación de Públicos | 2022–2024 |

---

## Propuesta de modelo de base de datos

### Principios de diseño

1. Separar **línea concursable estable** de su **instancia anual** (nombres y presupuestos cambian por año)
2. Tabla única `persona` con discriminador `tipo` (natural/jurídica) en vez de tablas separadas
3. Roles de persona dentro de una postulación mediante tabla puente (responsable, director, presenta_a)
4. Subcategorías como `modalidad` vinculada al concurso anual
5. Versionado de resoluciones (M:N con proyectos)

### Diagrama de entidades

```
convocatoria (año)
    │
    ├── concurso_anual ────── linea_concursable (código EPI, CPF...)
    │       │
    │       ├── modalidad (Desarrollo, Ópera prima...)
    │       ├── proyecto ─── persona (beneficiaria)
    │       │       │              │
    │       │       │              └── proyecto_integrante (rol: responsable, director)
    │       │       │
    │       │       └── proyecto
    │       │
    │       ├── proyecto_resolucion ─── resolucion
    │       │
    │       ├── jurado ─── persona
    │       │
    │       └── documento
    │
    └── (convocatoria tiene N concurso_anual)
```

### Entidades detalladas

Ver archivo `modelo_base_datos.md` para el esquema SQL completo.

---

## Pendientes

- [ ] Extraer datos del Acta de Evaluación del Jurado (contiene criterios, puntajes, miembros del jurado)
- [ ] Revisar PDFs de doc-1 (bases) para entender criterios de evaluación
- [ ] Extraer lista completa de ganadores 2025 de los PDFs restantes
- [ ] Cargar datos históricos 2019–2024
- [ ] Verificar si los códigos de concurso (EPI, CPF, etc.) son consistentes entre años
