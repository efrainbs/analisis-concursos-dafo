-- Schema para Estímulos Económicos DAFO
-- SQLite
-- Ejecutar: sqlite3 concursos_dafo.db < schema.sql

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

BEGIN TRANSACTION;

-- 1. convocatoria
CREATE TABLE convocatoria (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    anio    INTEGER NOT NULL UNIQUE,
    nombre  TEXT NOT NULL,
    activa  INTEGER NOT NULL DEFAULT 0
);

-- 2. linea_concursable
CREATE TABLE linea_concursable (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo           TEXT NOT NULL UNIQUE,
    nombre_canonico  TEXT NOT NULL,
    descripcion      TEXT,
    tipo_beneficiario TEXT NOT NULL CHECK (tipo_beneficiario IN ('natural', 'juridica', 'ambos'))
);

-- 3. concurso_anual
CREATE TABLE concurso_anual (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    convocatoria_id       INTEGER NOT NULL REFERENCES convocatoria(id),
    linea_concursable_id  INTEGER NOT NULL REFERENCES linea_concursable(id),
    nombre_usado          TEXT NOT NULL,
    presupuesto_asignado  REAL,
    activo                INTEGER NOT NULL DEFAULT 1,
    UNIQUE (convocatoria_id, linea_concursable_id)
);

-- 4. modalidad
CREATE TABLE modalidad (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    concurso_anual_id  INTEGER NOT NULL REFERENCES concurso_anual(id),
    nombre             TEXT NOT NULL,
    presupuesto_asignado REAL,
    UNIQUE (concurso_anual_id, nombre)
);

-- 5. persona
CREATE TABLE persona (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo         TEXT NOT NULL CHECK (tipo IN ('natural', 'juridica')),
    -- persona natural
    nombres      TEXT,
    apellidos    TEXT,
    dni          TEXT,
    -- persona jurídica
    razon_social TEXT,
    ruc          TEXT,
    -- común
    region       TEXT,
    direccion    TEXT,
    CHECK (
        (tipo = 'natural' AND nombres IS NOT NULL)
        OR
        (tipo = 'juridica' AND ruc IS NOT NULL AND razon_social IS NOT NULL)
    )
);

CREATE INDEX idx_persona_dni ON persona(dni);
CREATE INDEX idx_persona_ruc ON persona(ruc);

-- 5b. obra (metadatos del proyecto)
CREATE TABLE obra (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo      TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    tipo        TEXT
);

-- 6. proyecto (postulación beneficiada)
CREATE TABLE proyecto (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    concurso_anual_id       INTEGER NOT NULL REFERENCES concurso_anual(id),
    modalidad_id            INTEGER REFERENCES modalidad(id),
    persona_beneficiaria_id INTEGER NOT NULL REFERENCES persona(id),
    obra_id                 INTEGER REFERENCES obra(id),
    categoria               TEXT,
    monto_otorgado          REAL NOT NULL,
    estado                  TEXT NOT NULL DEFAULT 'beneficiario'
                            CHECK (estado IN ('beneficiario', 'lista_espera'))
);

CREATE INDEX idx_proyecto_concurso ON proyecto(concurso_anual_id);

-- 7. proyecto_integrante
CREATE TABLE proyecto_integrante (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    proyecto_id     INTEGER NOT NULL REFERENCES proyecto(id),
    persona_id      INTEGER NOT NULL REFERENCES persona(id),
    rol             TEXT NOT NULL CHECK (rol IN ('responsable', 'director', 'presenta_a'))
);

-- 9. resolucion
CREATE TABLE resolucion (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    concurso_anual_id  INTEGER NOT NULL REFERENCES concurso_anual(id),
    numero             TEXT NOT NULL,
    fecha_contenido    TEXT,
    tipo               TEXT NOT NULL CHECK (tipo IN (
                            'fallo_final',
                            'acta_evaluacion',
                            'resolucion_beneficiario',
                            'lista_espera'
                        )),
    url_pdf            TEXT
);

CREATE INDEX idx_resolucion_concurso ON resolucion(concurso_anual_id);

-- 9. proyecto_resolucion
CREATE TABLE proyecto_resolucion (
    proyecto_id   INTEGER NOT NULL REFERENCES proyecto(id),
    resolucion_id INTEGER NOT NULL REFERENCES resolucion(id),
    PRIMARY KEY (proyecto_id, resolucion_id)
);

-- 11. evento_internacional
CREATE TABLE evento_internacional (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    pais        TEXT NOT NULL,
    modalidad   TEXT NOT NULL CHECK (modalidad IN ('presencial', 'virtual')),
    tipo_evento TEXT CHECK (tipo_evento IN ('festival', 'mercado', 'premio', 'laboratorio'))
);

-- 11. proyecto_evento
CREATE TABLE proyecto_evento (
    proyecto_id             INTEGER NOT NULL REFERENCES proyecto(id),
    evento_internacional_id INTEGER NOT NULL REFERENCES evento_internacional(id),
    PRIMARY KEY (proyecto_id, evento_internacional_id)
);

-- 12. jurado
CREATE TABLE jurado (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    concurso_anual_id  INTEGER NOT NULL REFERENCES concurso_anual(id),
    modalidad_id       INTEGER REFERENCES modalidad(id),
    persona_id         INTEGER NOT NULL REFERENCES persona(id),
    cargo              TEXT
);

-- 13. documento
CREATE TABLE documento (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    concurso_anual_id  INTEGER NOT NULL REFERENCES concurso_anual(id),
    tipo_doc           TEXT NOT NULL CHECK (tipo_doc IN ('bases', 'anexos', 'fe_erratas', 'resultado', 'acta', 'lista_espera')),
    url                TEXT NOT NULL,
    titulo             TEXT,
    tamano_bytes       INTEGER
);

COMMIT;
