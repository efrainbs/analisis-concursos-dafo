# Diagrama ER - Base de Datos DAFO

```mermaid
erDiagram
    convocatoria {
        int id PK
        int anio UK
        text nombre
        int activa
    }

    linea_concursable {
        int id PK
        text codigo UK
        text nombre_canonico
        text descripcion
        text tipo_beneficiario
    }

    concurso_anual {
        int id PK
        int convocatoria_id FK
        int linea_concursable_id FK
        text nombre_usado
        real presupuesto_asignado
        int activo
    }

    modalidad {
        int id PK
        int concurso_anual_id FK
        text nombre
        real presupuesto_asignado
    }

    persona {
        int id PK
        text tipo
        text nombres
        text apellidos
        text dni
        text razon_social
        text ruc
        text region
        text direccion
    }

    obra {
        int id PK
        text titulo
        text descripcion
        text tipo
    }

    proyecto {
        int id PK
        int concurso_anual_id FK
        int modalidad_id FK
        int persona_beneficiaria_id FK
        int obra_id FK
        text categoria
        real monto_otorgado
        text estado
    }

    proyecto_integrante {
        int id PK
        int proyecto_id FK
        int persona_id FK
        text rol
    }

    resolucion {
        int id PK
        int concurso_anual_id FK
        text numero
        text fecha_contenido
        text tipo
        text url_pdf
    }

    proyecto_resolucion {
        int proyecto_id FK
        int resolucion_id FK
    }

    evento_internacional {
        int id PK
        text nombre
        text pais
        text modalidad
        text tipo_evento
    }

    proyecto_evento {
        int proyecto_id FK
        int evento_internacional_id FK
    }

    jurado {
        int id PK
        int concurso_anual_id FK
        int modalidad_id FK
        int persona_id FK
        text cargo
    }

    documento {
        int id PK
        int concurso_anual_id FK
        text tipo_doc
        text url
        text titulo
        int tamano_bytes
    }

    convocatoria ||--o{ concurso_anual : tiene
    linea_concursable ||--o{ concurso_anual : "se instancia en"
    concurso_anual ||--o{ modalidad : contiene
    concurso_anual ||--o{ proyecto : agrupa
    concurso_anual ||--o{ resolucion : publica
    concurso_anual ||--o{ jurado : designa
    concurso_anual ||--o{ documento : adjunta
    modalidad ||--o{ proyecto : clasifica
    persona ||--o{ proyecto : "es beneficiaria"
    persona ||--o{ proyecto_integrante : participa
    persona ||--o{ jurado : evalua
    obra ||--o{ proyecto : describe
    proyecto ||--o{ proyecto_integrante : tiene
    proyecto ||--o{ proyecto_resolucion : vinculado
    proyecto ||--o{ proyecto_evento : asiste
    resolucion ||--o{ proyecto_resolucion : vincula
    evento_internacional ||--o{ proyecto_evento : recibe
```

## Estructura simplificada

```
convocatoria (año)
  └─ concurso_anual (EPI 2025, CPF 2025...)
       ├─ modalidad (Desarrollo, Producción...)
       └─ proyecto (postulación beneficiada)
            ├─ obra (título, descripción)
            ├─ persona (beneficiario: natural o jurídica)
            ├─ proyecto_integrante (responsable, director)
            ├─ proyecto_resolucion (fallo, RD)
            └─ proyecto_evento (festivales EPI)
```

## Tablas principales (12)

| Tabla | Propósito |
|-------|-----------|
| `convocatoria` | Edición anual del programa |
| `linea_concursable` | Línea de concurso (EPI, CPF, CDV...) |
| `concurso_anual` | Instancia de una línea en un año |
| `modalidad` | Subcategoría del concurso |
| `persona` | Persona natural o jurídica (unificada) |
| `obra` | Metadatos del proyecto postulado |
| `proyecto` | Postulación beneficiada |
| `proyecto_integrante` | Roles dentro del proyecto |
| `resolucion` | Documento legal de resultados |
| `proyecto_resolucion` | Proyecto ↔ Resolución (M:N) |
| `evento_internacional` | Festival/mercado (solo EPI) |
| `proyecto_evento` | Proyecto ↔ Evento (M:N) |
| `jurado` | Evaluadores del concurso |
| `documento` | PDFs publicados (bases, anexos) |
