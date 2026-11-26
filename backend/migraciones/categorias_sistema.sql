BEGIN;

BEGIN;

INSERT INTO public.categoria_movimiento
(id_usuario, nombre_categoria, tipo_categoria, es_sistema, estado)
VALUES (NULL, 'Alimentación', 'GASTO', TRUE, 'ACTIVA');

INSERT INTO public.categoria_movimiento
(id_usuario, nombre_categoria, tipo_categoria, es_sistema, estado)
VALUES (NULL, 'Transporte', 'GASTO', TRUE, 'ACTIVA');

INSERT INTO public.categoria_movimiento
(id_usuario, nombre_categoria, tipo_categoria, es_sistema, estado)
VALUES (NULL, 'Restaurantes', 'GASTO', TRUE, 'ACTIVA');

INSERT INTO public.categoria_movimiento
(id_usuario, nombre_categoria, tipo_categoria, es_sistema, estado)
VALUES (NULL, 'Salario', 'INGRESO', TRUE, 'ACTIVA');

COMMIT;

COMMIT;