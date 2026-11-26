--
-- PostgreSQL database dump
--

\restrict cWtRFbnFCPypWZPg7WYEfVU7ce3jxkOf5AdvbYqslrSMKBIkUga7AWkmro45g24

-- Dumped from database version 14.24
-- Dumped by pg_dump version 14.24

-- Started on 2026-11-26 14:57:33

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 228 (class 1259 OID 60573)
-- Name: aporte_meta; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aporte_meta (
    id_aporte integer NOT NULL,
    uuid_operacion uuid NOT NULL,
    id_usuario integer NOT NULL,
    id_meta integer NOT NULL,
    id_cuenta integer NOT NULL,
    tipo character varying(10) NOT NULL,
    monto numeric(15,2) NOT NULL,
    fecha_operacion date NOT NULL,
    estado character varying(10) NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_aporte_meta_estado CHECK (((estado)::text = 'ACTIVO'::text)),
    CONSTRAINT ck_aporte_meta_monto CHECK ((monto > (0)::numeric)),
    CONSTRAINT ck_aporte_meta_tipo CHECK (((tipo)::text = ANY ((ARRAY['RESERVA'::character varying, 'LIBERACION'::character varying])::text[])))
);


--
-- TOC entry 227 (class 1259 OID 60572)
-- Name: aporte_meta_id_aporte_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.aporte_meta ALTER COLUMN id_aporte ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.aporte_meta_id_aporte_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 216 (class 1259 OID 60404)
-- Name: categoria_movimiento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categoria_movimiento (
    id_categoria integer NOT NULL,
    id_usuario integer,
    nombre_categoria character varying(60) NOT NULL,
    tipo_categoria character varying(10) NOT NULL,
    es_sistema boolean DEFAULT false NOT NULL,
    estado character varying(10) DEFAULT 'ACTIVA'::character varying NOT NULL,
    CONSTRAINT ck_categoria_estado CHECK (((estado)::text = ANY ((ARRAY['ACTIVA'::character varying, 'INACTIVA'::character varying])::text[]))),
    CONSTRAINT ck_categoria_propietario CHECK ((((es_sistema = true) AND (id_usuario IS NULL)) OR ((es_sistema = false) AND (id_usuario IS NOT NULL)))),
    CONSTRAINT ck_categoria_tipo CHECK (((tipo_categoria)::text = ANY ((ARRAY['GASTO'::character varying, 'INGRESO'::character varying])::text[])))
);


--
-- TOC entry 215 (class 1259 OID 60403)
-- Name: categoria_movimiento_id_categoria_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.categoria_movimiento ALTER COLUMN id_categoria ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.categoria_movimiento_id_categoria_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 214 (class 1259 OID 60390)
-- Name: cuenta_financiera; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cuenta_financiera (
    id_cuenta integer NOT NULL,
    id_usuario integer NOT NULL,
    nombre_cuenta character varying(80) NOT NULL,
    tipo_cuenta character varying(10) NOT NULL,
    institucion character varying(80),
    saldo_inicial numeric(15,2) NOT NULL,
    estado character varying(10) DEFAULT 'ACTIVA'::character varying NOT NULL,
    CONSTRAINT ck_cuenta_estado CHECK (((estado)::text = ANY ((ARRAY['ACTIVA'::character varying, 'INACTIVA'::character varying])::text[]))),
    CONSTRAINT ck_cuenta_tipo CHECK (((tipo_cuenta)::text = ANY ((ARRAY['AHORROS'::character varying, 'CORRIENTE'::character varying, 'EFECTIVO'::character varying])::text[])))
);


--
-- TOC entry 213 (class 1259 OID 60389)
-- Name: cuenta_financiera_id_cuenta_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cuenta_financiera ALTER COLUMN id_cuenta ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.cuenta_financiera_id_cuenta_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 229 (class 1259 OID 60601)
-- Name: estado_rdf_usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.estado_rdf_usuario (
    id_usuario integer NOT NULL,
    revision bigint DEFAULT 0 NOT NULL,
    revision_publicada bigint DEFAULT 0 NOT NULL,
    actualizacion_en timestamp with time zone DEFAULT now() NOT NULL,
    publicacion_en timestamp with time zone,
    CONSTRAINT estado_rdf_usuario_check CHECK (((revision_publicada >= 0) AND (revision_publicada <= revision))),
    CONSTRAINT estado_rdf_usuario_revision_check CHECK ((revision >= 0))
);


--
-- TOC entry 220 (class 1259 OID 60438)
-- Name: meta_financiera; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.meta_financiera (
    id_meta integer NOT NULL,
    id_usuario integer NOT NULL,
    nombre_meta character varying(80) NOT NULL,
    monto_objetivo numeric(15,2) NOT NULL,
    monto_acumulado numeric(15,2) DEFAULT 0 NOT NULL,
    fecha_objetivo date NOT NULL,
    descripcion character varying(255),
    estado character varying(10) DEFAULT 'ACTIVA'::character varying NOT NULL,
    CONSTRAINT ck_meta_acumulado CHECK ((monto_acumulado >= (0)::numeric)),
    CONSTRAINT ck_meta_estado CHECK (((estado)::text = ANY ((ARRAY['ACTIVA'::character varying, 'CUMPLIDA'::character varying, 'CANCELADA'::character varying, 'INACTIVA'::character varying])::text[]))),
    CONSTRAINT ck_meta_objetivo CHECK ((monto_objetivo > (0)::numeric))
);


--
-- TOC entry 219 (class 1259 OID 60437)
-- Name: meta_financiera_id_meta_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.meta_financiera ALTER COLUMN id_meta ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.meta_financiera_id_meta_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 226 (class 1259 OID 60496)
-- Name: movimiento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movimiento (
    id_movimiento integer NOT NULL,
    uuid_local uuid NOT NULL,
    id_cuenta integer NOT NULL,
    id_categoria integer,
    id_transferencia integer,
    id_obligacion integer,
    tipo character varying(10) NOT NULL,
    origen character varying(15) NOT NULL,
    monto numeric(15,2) NOT NULL,
    fecha_movimiento date NOT NULL,
    descripcion character varying(255),
    aplica_gmf boolean DEFAULT false NOT NULL,
    monto_gmf numeric(15,2) DEFAULT 0 NOT NULL,
    estado character varying(10) DEFAULT 'ACTIVO'::character varying NOT NULL,
    fecha_actualizacion timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_movimiento_estado CHECK (((estado)::text = ANY ((ARRAY['ACTIVO'::character varying, 'ANULADO'::character varying])::text[]))),
    CONSTRAINT ck_movimiento_fecha CHECK ((fecha_movimiento <= CURRENT_DATE)),
    CONSTRAINT ck_movimiento_gmf CHECK ((((aplica_gmf = false) AND (monto_gmf = (0)::numeric)) OR ((aplica_gmf = true) AND (monto_gmf > (0)::numeric)))),
    CONSTRAINT ck_movimiento_monto CHECK ((monto > (0)::numeric)),
    CONSTRAINT ck_movimiento_origen CHECK (((origen)::text = ANY ((ARRAY['NORMAL'::character varying, 'TRANSFERENCIA'::character varying, 'OBLIGACION'::character varying])::text[]))),
    CONSTRAINT ck_movimiento_relacion_origen CHECK (((((origen)::text = 'NORMAL'::text) AND (id_categoria IS NOT NULL) AND (id_transferencia IS NULL) AND (id_obligacion IS NULL)) OR (((origen)::text = 'TRANSFERENCIA'::text) AND (id_categoria IS NULL) AND (id_transferencia IS NOT NULL) AND (id_obligacion IS NULL)) OR (((origen)::text = 'OBLIGACION'::text) AND (id_categoria IS NULL) AND (id_transferencia IS NULL) AND (id_obligacion IS NOT NULL)))),
    CONSTRAINT ck_movimiento_tipo CHECK (((tipo)::text = ANY ((ARRAY['INGRESO'::character varying, 'GASTO'::character varying])::text[])))
);


--
-- TOC entry 225 (class 1259 OID 60495)
-- Name: movimiento_id_movimiento_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.movimiento ALTER COLUMN id_movimiento ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.movimiento_id_movimiento_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 218 (class 1259 OID 60422)
-- Name: obligacion_financiera; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.obligacion_financiera (
    id_obligacion integer NOT NULL,
    id_usuario integer NOT NULL,
    nombre_obligacion character varying(80) NOT NULL,
    tipo_obligacion character varying(12) NOT NULL,
    monto_original numeric(15,2) NOT NULL,
    fecha_inicio date NOT NULL,
    fecha_vencimiento date,
    descripcion character varying(255),
    estado character varying(10) DEFAULT 'ACTIVA'::character varying NOT NULL,
    CONSTRAINT ck_obligacion_estado CHECK (((estado)::text = ANY ((ARRAY['ACTIVA'::character varying, 'SALDADA'::character varying, 'CANCELADA'::character varying, 'INACTIVA'::character varying])::text[]))),
    CONSTRAINT ck_obligacion_fechas CHECK (((fecha_vencimiento IS NULL) OR (fecha_vencimiento >= fecha_inicio))),
    CONSTRAINT ck_obligacion_monto CHECK ((monto_original > (0)::numeric)),
    CONSTRAINT ck_obligacion_tipo CHECK (((tipo_obligacion)::text = ANY ((ARRAY['POR_PAGAR'::character varying, 'POR_COBRAR'::character varying])::text[])))
);


--
-- TOC entry 217 (class 1259 OID 60421)
-- Name: obligacion_financiera_id_obligacion_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.obligacion_financiera ALTER COLUMN id_obligacion ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.obligacion_financiera_id_obligacion_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 222 (class 1259 OID 60454)
-- Name: presupuesto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.presupuesto (
    id_presupuesto integer NOT NULL,
    id_usuario integer NOT NULL,
    id_categoria integer NOT NULL,
    anio smallint NOT NULL,
    mes smallint NOT NULL,
    monto_limite numeric(15,2) NOT NULL,
    CONSTRAINT ck_presupuesto_anio CHECK ((anio >= 2000)),
    CONSTRAINT ck_presupuesto_mes CHECK (((mes >= 1) AND (mes <= 12))),
    CONSTRAINT ck_presupuesto_monto CHECK ((monto_limite > (0)::numeric))
);


--
-- TOC entry 221 (class 1259 OID 60453)
-- Name: presupuesto_id_presupuesto_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.presupuesto ALTER COLUMN id_presupuesto ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.presupuesto_id_presupuesto_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 212 (class 1259 OID 60376)
-- Name: token_recuperacion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.token_recuperacion (
    id_token integer NOT NULL,
    id_usuario integer NOT NULL,
    token_hash character varying(255) NOT NULL,
    fecha_expiracion timestamp with time zone NOT NULL,
    usado boolean DEFAULT false NOT NULL
);


--
-- TOC entry 211 (class 1259 OID 60375)
-- Name: token_recuperacion_id_token_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.token_recuperacion ALTER COLUMN id_token ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.token_recuperacion_id_token_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 224 (class 1259 OID 60475)
-- Name: transferencia; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transferencia (
    id_transferencia integer NOT NULL,
    id_cuenta_origen integer NOT NULL,
    id_cuenta_destino integer NOT NULL,
    monto numeric(15,2) NOT NULL,
    fecha_transferencia date NOT NULL,
    motivo character varying(150) DEFAULT 'Movimiento interno'::character varying NOT NULL,
    estado character varying(10) DEFAULT 'ACTIVA'::character varying NOT NULL,
    CONSTRAINT ck_transferencia_cuentas CHECK ((id_cuenta_origen <> id_cuenta_destino)),
    CONSTRAINT ck_transferencia_estado CHECK (((estado)::text = ANY ((ARRAY['ACTIVA'::character varying, 'ANULADA'::character varying])::text[]))),
    CONSTRAINT ck_transferencia_monto CHECK ((monto > (0)::numeric))
);


--
-- TOC entry 223 (class 1259 OID 60474)
-- Name: transferencia_id_transferencia_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.transferencia ALTER COLUMN id_transferencia ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.transferencia_id_transferencia_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 210 (class 1259 OID 60367)
-- Name: usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario (
    id_usuario integer NOT NULL,
    nombre_1 character varying(50) NOT NULL,
    nombre_2 character varying(50),
    apellido_1 character varying(50) NOT NULL,
    apellido_2 character varying(50),
    email character varying(100) NOT NULL,
    password_hash character varying(255) NOT NULL,
    version_sesion integer DEFAULT 0 NOT NULL,
    CONSTRAINT usuario_version_sesion_check CHECK ((version_sesion >= 0))
);


--
-- TOC entry 209 (class 1259 OID 60366)
-- Name: usuario_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.usuario ALTER COLUMN id_usuario ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.usuario_id_usuario_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 3291 (class 2606 OID 60581)
-- Name: aporte_meta aporte_meta_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aporte_meta
    ADD CONSTRAINT aporte_meta_pkey PRIMARY KEY (id_aporte);


--
-- TOC entry 3273 (class 2606 OID 60413)
-- Name: categoria_movimiento categoria_movimiento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria_movimiento
    ADD CONSTRAINT categoria_movimiento_pkey PRIMARY KEY (id_categoria);


--
-- TOC entry 3271 (class 2606 OID 60397)
-- Name: cuenta_financiera cuenta_financiera_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_financiera
    ADD CONSTRAINT cuenta_financiera_pkey PRIMARY KEY (id_cuenta);


--
-- TOC entry 3297 (class 2606 OID 60610)
-- Name: estado_rdf_usuario estado_rdf_usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_rdf_usuario
    ADD CONSTRAINT estado_rdf_usuario_pkey PRIMARY KEY (id_usuario);


--
-- TOC entry 3279 (class 2606 OID 60447)
-- Name: meta_financiera meta_financiera_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meta_financiera
    ADD CONSTRAINT meta_financiera_pkey PRIMARY KEY (id_meta);


--
-- TOC entry 3287 (class 2606 OID 60511)
-- Name: movimiento movimiento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento
    ADD CONSTRAINT movimiento_pkey PRIMARY KEY (id_movimiento);


--
-- TOC entry 3289 (class 2606 OID 60513)
-- Name: movimiento movimiento_uuid_local_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento
    ADD CONSTRAINT movimiento_uuid_local_key UNIQUE (uuid_local);


--
-- TOC entry 3277 (class 2606 OID 60431)
-- Name: obligacion_financiera obligacion_financiera_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligacion_financiera
    ADD CONSTRAINT obligacion_financiera_pkey PRIMARY KEY (id_obligacion);


--
-- TOC entry 3281 (class 2606 OID 60461)
-- Name: presupuesto presupuesto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuesto
    ADD CONSTRAINT presupuesto_pkey PRIMARY KEY (id_presupuesto);


--
-- TOC entry 3267 (class 2606 OID 60381)
-- Name: token_recuperacion token_recuperacion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_recuperacion
    ADD CONSTRAINT token_recuperacion_pkey PRIMARY KEY (id_token);


--
-- TOC entry 3269 (class 2606 OID 60383)
-- Name: token_recuperacion token_recuperacion_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_recuperacion
    ADD CONSTRAINT token_recuperacion_token_hash_key UNIQUE (token_hash);


--
-- TOC entry 3285 (class 2606 OID 60484)
-- Name: transferencia transferencia_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia
    ADD CONSTRAINT transferencia_pkey PRIMARY KEY (id_transferencia);


--
-- TOC entry 3295 (class 2606 OID 60583)
-- Name: aporte_meta uq_aporte_meta_uuid; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aporte_meta
    ADD CONSTRAINT uq_aporte_meta_uuid UNIQUE (uuid_operacion);


--
-- TOC entry 3283 (class 2606 OID 60463)
-- Name: presupuesto uq_presupuesto_periodo; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuesto
    ADD CONSTRAINT uq_presupuesto_periodo UNIQUE (id_usuario, id_categoria, anio, mes);


--
-- TOC entry 3264 (class 2606 OID 60373)
-- Name: usuario usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_pkey PRIMARY KEY (id_usuario);


--
-- TOC entry 3265 (class 1259 OID 60832)
-- Name: idx_token_recuperacion_usuario_expiracion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_token_recuperacion_usuario_expiracion ON public.token_recuperacion USING btree (id_usuario, fecha_expiracion);


--
-- TOC entry 3292 (class 1259 OID 60600)
-- Name: ix_aporte_meta_usuario_cuenta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aporte_meta_usuario_cuenta ON public.aporte_meta USING btree (id_usuario, id_cuenta);


--
-- TOC entry 3293 (class 1259 OID 60599)
-- Name: ix_aporte_meta_usuario_meta; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aporte_meta_usuario_meta ON public.aporte_meta USING btree (id_usuario, id_meta);


--
-- TOC entry 3274 (class 1259 OID 60419)
-- Name: uq_categoria_sistema_nombre_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_categoria_sistema_nombre_tipo ON public.categoria_movimiento USING btree (lower(TRIM(BOTH FROM nombre_categoria)), tipo_categoria) WHERE (es_sistema = true);


--
-- TOC entry 3275 (class 1259 OID 60420)
-- Name: uq_categoria_usuario_nombre_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_categoria_usuario_nombre_tipo ON public.categoria_movimiento USING btree (id_usuario, lower(TRIM(BOTH FROM nombre_categoria)), tipo_categoria) WHERE (es_sistema = false);


--
-- TOC entry 3262 (class 1259 OID 60374)
-- Name: uq_usuario_email_normalizado; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_usuario_email_normalizado ON public.usuario USING btree (lower(TRIM(BOTH FROM email)));


--
-- TOC entry 3311 (class 2606 OID 60594)
-- Name: aporte_meta aporte_meta_id_cuenta_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aporte_meta
    ADD CONSTRAINT aporte_meta_id_cuenta_fkey FOREIGN KEY (id_cuenta) REFERENCES public.cuenta_financiera(id_cuenta);


--
-- TOC entry 3312 (class 2606 OID 60589)
-- Name: aporte_meta aporte_meta_id_meta_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aporte_meta
    ADD CONSTRAINT aporte_meta_id_meta_fkey FOREIGN KEY (id_meta) REFERENCES public.meta_financiera(id_meta);


--
-- TOC entry 3313 (class 2606 OID 60584)
-- Name: aporte_meta aporte_meta_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aporte_meta
    ADD CONSTRAINT aporte_meta_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario);


--
-- TOC entry 3314 (class 2606 OID 60611)
-- Name: estado_rdf_usuario estado_rdf_usuario_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_rdf_usuario
    ADD CONSTRAINT estado_rdf_usuario_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE CASCADE;


--
-- TOC entry 3300 (class 2606 OID 60414)
-- Name: categoria_movimiento fk_categoria_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categoria_movimiento
    ADD CONSTRAINT fk_categoria_usuario FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario);


--
-- TOC entry 3299 (class 2606 OID 60398)
-- Name: cuenta_financiera fk_cuenta_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cuenta_financiera
    ADD CONSTRAINT fk_cuenta_usuario FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario);


--
-- TOC entry 3302 (class 2606 OID 60448)
-- Name: meta_financiera fk_meta_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.meta_financiera
    ADD CONSTRAINT fk_meta_usuario FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario);


--
-- TOC entry 3307 (class 2606 OID 60519)
-- Name: movimiento fk_movimiento_categoria; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento
    ADD CONSTRAINT fk_movimiento_categoria FOREIGN KEY (id_categoria) REFERENCES public.categoria_movimiento(id_categoria);


--
-- TOC entry 3308 (class 2606 OID 60514)
-- Name: movimiento fk_movimiento_cuenta; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento
    ADD CONSTRAINT fk_movimiento_cuenta FOREIGN KEY (id_cuenta) REFERENCES public.cuenta_financiera(id_cuenta);


--
-- TOC entry 3309 (class 2606 OID 60529)
-- Name: movimiento fk_movimiento_obligacion; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento
    ADD CONSTRAINT fk_movimiento_obligacion FOREIGN KEY (id_obligacion) REFERENCES public.obligacion_financiera(id_obligacion);


--
-- TOC entry 3310 (class 2606 OID 60524)
-- Name: movimiento fk_movimiento_transferencia; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimiento
    ADD CONSTRAINT fk_movimiento_transferencia FOREIGN KEY (id_transferencia) REFERENCES public.transferencia(id_transferencia);


--
-- TOC entry 3301 (class 2606 OID 60432)
-- Name: obligacion_financiera fk_obligacion_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligacion_financiera
    ADD CONSTRAINT fk_obligacion_usuario FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario);


--
-- TOC entry 3303 (class 2606 OID 60469)
-- Name: presupuesto fk_presupuesto_categoria; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuesto
    ADD CONSTRAINT fk_presupuesto_categoria FOREIGN KEY (id_categoria) REFERENCES public.categoria_movimiento(id_categoria);


--
-- TOC entry 3304 (class 2606 OID 60464)
-- Name: presupuesto fk_presupuesto_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.presupuesto
    ADD CONSTRAINT fk_presupuesto_usuario FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario);


--
-- TOC entry 3298 (class 2606 OID 60384)
-- Name: token_recuperacion fk_token_usuario; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.token_recuperacion
    ADD CONSTRAINT fk_token_usuario FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario);


--
-- TOC entry 3305 (class 2606 OID 60490)
-- Name: transferencia fk_transferencia_destino; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia
    ADD CONSTRAINT fk_transferencia_destino FOREIGN KEY (id_cuenta_destino) REFERENCES public.cuenta_financiera(id_cuenta);


--
-- TOC entry 3306 (class 2606 OID 60485)
-- Name: transferencia fk_transferencia_origen; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transferencia
    ADD CONSTRAINT fk_transferencia_origen FOREIGN KEY (id_cuenta_origen) REFERENCES public.cuenta_financiera(id_cuenta);


-- Completed on 2026-11-26 14:57:35

--
-- PostgreSQL database dump complete
--

\unrestrict cWtRFbnFCPypWZPg7WYEfVU7ce3jxkOf5AdvbYqslrSMKBIkUga7AWkmro45g24

