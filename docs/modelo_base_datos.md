# Modelo de Base de Datos - Estímulos Económicos DAFO

## Convenciones

- `PK` = Primary Key
- `FK` = Foreign Key
- `UQ` = Unique
- Tipos en notación PostgreSQL

---

## 1. convocatoria

Cada año de edición del programa.

```sql
CREATE TABLE convocatoria (
    id          SERIAL PRIMARY KEY,
    anio        INTEGER NOT NULL UNIQUE,
    nombre      TEXT NOT NULL,       -- ej: "Estímulos Económicos 2025"
    activa      BOOLEAN NOT NULL DEFAULT false
);
```

## 2. linea_concursable

La línea de concurso como concepto estable a través de los años.

```sql
CREATE TABLE linea_concursable (
    id              SERIAL PRIMARY KEY,
    codigo          TEXT NOT NULL UNIQUE,  -- EPI, CPF, CDV, etc.
    nombre_canonico TEXT NOT NULL,         -- "Estímulo a la Promoción Internacional"
    descripcion     TEXT,
    tipo_beneficiario TEXT NOT NULL CHECK (tipo_beneficiario IN ('natural', 'juridica', 'ambos'))
);
```

## 3. concurso_anual

La instancia concreta de una línea en un año específico.

```sql
CREATE TABLE concurso_anual (
    id                      SERIAL PRIMARY KEY,
    convocatoria_id         INTEGER NOT NULL REFERENCES convocatoria(id),
    linea_concursable_id    INTEGER NOT NULL REFERENCES linea_concursable(id),
    nombre_usado            TEXT NOT NULL,   -- nombre que usó ese año (puede diferir del canónico)
    presupuesto_asignado    NUMERIC(12,2),
    activo                  BOOLEAN NOT NULL DEFAULT true,
    UNIQUE (convocatoria_id, linea_concursable_id)
);
```

## 4. modalidad

Subcategorías dentro de un concurso anual (Desarrollo, Ópera prima, Preproducción...).

```sql
CREATE TABLE modalidad (
    id                  SERIAL PRIMARY KEY,
    concurso_anual_id   INTEGER NOT NULL REFERENCES concurso_anual(id),
    nombre              TEXT NOT NULL,
    presupuesto_asignado NUMERIC(12,2),
    UNIQUE (concurso_anual_id, nombre)
);
```

## 5. persona

Unificada: puede ser natural (DNI) o jurídica (RUC).

```sql
CREATE TABLE persona (
    id          SERIAL PRIMARY KEY,
    tipo        TEXT NOT NULL CHECK (tipo IN ('natural', 'juridica')),
    -- persona natural
    nombres     TEXT,
    apellidos   TEXT,
    dni         TEXT,
    -- persona jurídica
    razon_social TEXT,
    ruc         TEXT,
    -- común
    region      TEXT,
    direccion   TEXT,
    CHECK (
        (tipo = 'natural' AND dni IS NOT NULL AND nombres IS NOT NULL)
        OR
        (tipo = 'juridica' AND ruc IS NOT NULL AND razon_social IS NOT NULL)
    )
);

CREATE INDEX idx_persona_dni ON persona(dni);
CREATE INDEX idx_persona_ruc ON persona(ruc);
```

## 6. proyecto

La obra, proyecto, o actividad postulada.

```sql
CREATE TABLE proyecto (
    id          SERIAL PRIMARY KEY,
    titulo      TEXT NOT NULL,
    descripcion TEXT,
    tipo        TEXT   -- largometraje, cortometraje, videojuego, festival, preservación, investigación...
);
```

## 7. proyecto

Cada postulación declarada como beneficiaria (o lista de espera).

```sql
CREATE TABLE proyecto (
    id                      SERIAL PRIMARY KEY,
    concurso_anual_id       INTEGER NOT NULL REFERENCES concurso_anual(id),
    modalidad_id            INTEGER REFERENCES modalidad(id),
    persona_beneficiaria_id INTEGER NOT NULL REFERENCES persona(id),
    obra_id             INTEGER NOT NULL REFERENCES proyecto(id),
    categoria               TEXT,   -- "Ópera prima", "Festivales primeras ediciones", etc.
    monto_otorgado          NUMERIC(12,2) NOT NULL,
    estado                  TEXT NOT NULL DEFAULT 'beneficiario'
                            CHECK (estado IN ('beneficiario', 'lista_espera'))
);

CREATE INDEX idx_proyecto_concurso ON proyecto(concurso_anual_id);
```

## 8. proyecto_integrante

Personas con roles específicos dentro de una postulación (responsable, director, presenta_a).

```sql
CREATE TABLE proyecto_integrante (
    id              SERIAL PRIMARY KEY,
    proyecto_id  INTEGER NOT NULL REFERENCES proyecto(id),
    persona_id      INTEGER NOT NULL REFERENCES persona(id),
    rol             TEXT NOT NULL CHECK (rol IN ('responsable', 'director', 'presenta_a'))
);
```

## 9. resolucion

Documento legal que formaliza los resultados.

```sql
CREATE TABLE resolucion (
    id                  SERIAL PRIMARY KEY,
    concurso_anual_id   INTEGER NOT NULL REFERENCES concurso_anual(id),
    numero              TEXT NOT NULL,   -- "001069-2025-DGIA-VMPCIC/MC"
    fecha_contenido     DATE,           -- fecha que aparece en el documento
    tipo                TEXT NOT NULL CHECK (tipo IN (
                            'fallo_final',
                            'acta_evaluacion',
                            'resolucion_beneficiario',
                            'lista_espera'
                        )),
    url_pdf             TEXT
);

CREATE INDEX idx_resolucion_concurso ON resolucion(concurso_anual_id);
```

## 10. proyecto_resolucion

Relación M:N entre proyectos y resoluciones (una postulación puede aparecer en fallo final + resolución individual + lista de espera).

```sql
CREATE TABLE proyecto_resolucion (
    proyecto_id  INTEGER NOT NULL REFERENCES proyecto(id),
    resolucion_id   INTEGER NOT NULL REFERENCES resolucion(id),
    PRIMARY KEY (proyecto_id, resolucion_id)
);
```

## 11. evento_internacional

Solo para EPI (Estímulo a la Promoción Internacional).

```sql
CREATE TABLE evento_internacional (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL,       -- "Salón de Productores FICCali"
    pais        TEXT NOT NULL,
    modalidad   TEXT NOT NULL CHECK (modalidad IN ('presencial', 'virtual')),
    tipo_evento TEXT CHECK (tipo_evento IN ('festival', 'mercado', 'premio', 'laboratorio'))
);
```

## 12. proyecto_evento

Relación M:N (una postulación puede vincularse a múltiples eventos).

```sql
CREATE TABLE proyecto_evento (
    proyecto_id          INTEGER NOT NULL REFERENCES proyecto(id),
    evento_internacional_id INTEGER NOT NULL REFERENCES evento_internacional(id),
    PRIMARY KEY (proyecto_id, evento_internacional_id)
);
```

## 13. jurado

Miembros del jurado designados para evaluar.

```sql
CREATE TABLE jurado (
    id                  SERIAL PRIMARY KEY,
    concurso_anual_id   INTEGER NOT NULL REFERENCES concurso_anual(id),
    modalidad_id        INTEGER REFERENCES modalidad(id),
    persona_id          INTEGER NOT NULL REFERENCES persona(id),
    cargo               TEXT    -- "Presidente", "Miembro", "Especialista en..."
);
```

## 14. documento

Todos los PDFs publicados en el sitio (bases, anexos, fe de erratas, resultados).

```sql
CREATE TABLE documento (
    id                  SERIAL PRIMARY KEY,
    concurso_anual_id   INTEGER NOT NULL REFERENCES concurso_anual(id),
    tipo_doc            TEXT NOT NULL CHECK (tipo_doc IN ('bases', 'anexos', 'fe_erratas', 'resultado')),
    url                 TEXT NOT NULL,
    titulo              TEXT,
    tamano_bytes        INTEGER
);
```

---

## Resumen de relaciones

```
convocatoria (1) ── (N) concurso_anual (N) ── (1) linea_concursable
                              │
                              ├── (N) modalidad
                              ├── (N) proyecto ── (N:1) persona
                              │       │                  │
                              │       │                  └── (N) proyecto_integrante ── (N:1) persona
                              │       │
                              │       └── (N:1) proyecto
                              │
                              ├── (N) resolucion
                              │       └── (M:N) proyecto_resolucion ── (N:1) proyecto
                              │
                              ├── (N) jurado ── (N:1) persona
                              │
                              ├── (N) documento
                              │
                              └── (N) proyecto
                                      └── (M:N) proyecto_evento ── (N:1) evento_internacional
```

## Notas de diseño

1. **persona unificada**: El CHECK constraint garantiza que según el tipo se completen los campos correctos (DNI para natural, RUC para jurídica).

2. **proyecto_integrante**: Permite modelar que en ficción haya responsable + director como personas distintas, mientras que en videojuegos solo haya responsable.

3. **proyecto.categoria**: Texto libre porque varía por concurso (Ópera prima, Segunda obra, Festivales primeras ediciones...). No se normaliza porque cada concurso tiene su propio vocabulario.

4. **concurso_anual.nombre_usado**: Captura cambios de nombre entre años (ej: "Pilotos de Serie" → "Desarrollo de series").

5. **Resoluciones M:N**: Una postulación puede estar en el fallo final (resolución colectiva) y también en una resolución individual de beneficiario.

6. **evento_internacional**: Desacoplado en tabla aparte porque solo aplica a EPI, no a los otros 17 concursos.
