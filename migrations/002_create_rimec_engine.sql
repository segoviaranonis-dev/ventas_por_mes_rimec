-- ============================================================
-- MIGRACIÓN 002 — RIMEC ENGINE: Gestión de Eventos de Precio
-- ============================================================

-- ── 1. precio_evento ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS precio_evento (
    id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre_evento         text        NOT NULL,
    nombre_archivo        text        NOT NULL,
    fecha_evento          timestamptz NOT NULL DEFAULT now(),
    fecha_vigencia_desde  date        NOT NULL,
    fecha_vigencia_hasta  date        NULL,
    usuario_id            bigint      NULL REFERENCES usuario_v2(id_usuario),
    estado                text        NOT NULL DEFAULT 'borrador'
                              CHECK (estado IN ('borrador','validado','cerrado')),
    created_at            timestamptz NOT NULL DEFAULT now()
);

-- ── 2. precio_evento_caso ────────────────────────────────────
CREATE TABLE IF NOT EXISTS precio_evento_caso (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evento_id           bigint      NOT NULL REFERENCES precio_evento(id),
    nombre_caso         text        NOT NULL,
    dolar_politica      numeric     NOT NULL,
    factor_conversion   numeric     NOT NULL,
    indice_calculado    numeric     NOT NULL
                            GENERATED ALWAYS AS
                            ((dolar_politica * factor_conversion) / 100) STORED,
    descuento_1         numeric     NULL,
    descuento_2         numeric     NULL,
    descuento_3         numeric     NULL,
    descuento_4         numeric     NULL,
    genera_lpc03_lpc04  boolean     NOT NULL DEFAULT false,
    regla_redondeo      text        NOT NULL DEFAULT 'centena',
    marcas              text[]      NULL,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- ── 3. precio_evento_linea_excepcion ────────────────────────
CREATE TABLE IF NOT EXISTS precio_evento_linea_excepcion (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    caso_id  bigint NOT NULL REFERENCES precio_evento_caso(id),
    linea_id bigint NOT NULL REFERENCES linea(id)
);

-- ── 4. precio_lista ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS precio_lista (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evento_id      bigint  NOT NULL REFERENCES precio_evento(id),
    caso_id        bigint  NOT NULL REFERENCES precio_evento_caso(id),
    marca          text    NOT NULL,
    linea_id       bigint  NOT NULL REFERENCES linea(id),
    referencia_id  bigint  NOT NULL REFERENCES referencia(id),
    material_id    bigint  NOT NULL REFERENCES material(id),
    fob_fabrica    numeric NOT NULL,
    fob_ajustado   numeric NOT NULL,
    lpn            numeric NOT NULL,
    lpc02          numeric NULL,
    lpc03          numeric NULL,
    lpc04          numeric NULL,
    vigente        boolean NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- ── 5. precio_auditoria ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS precio_auditoria (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evento_id        bigint      NOT NULL REFERENCES precio_evento(id),
    tabla_afectada   text        NOT NULL,
    campo_modificado text        NOT NULL,
    valor_anterior   text        NULL,
    valor_nuevo      text        NULL,
    justificacion    text        NULL,
    usuario_id       bigint      NULL REFERENCES usuario_v2(id_usuario),
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- ── Índices de performance ───────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_precio_lista_evento    ON precio_lista(evento_id);
CREATE INDEX IF NOT EXISTS idx_precio_lista_vigente   ON precio_lista(vigente) WHERE vigente = true;
CREATE INDEX IF NOT EXISTS idx_precio_lista_referencia ON precio_lista(referencia_id);
CREATE INDEX IF NOT EXISTS idx_precio_evento_caso_evento ON precio_evento_caso(evento_id);
