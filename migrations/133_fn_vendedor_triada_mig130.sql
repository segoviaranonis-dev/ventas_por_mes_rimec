-- MIG-133 — fn_es_usuario_vendedor_o_admin alineada a triada MIG-130
-- Tras MIG-130 el rol orgánico es GERENTE/ADMINISTRADOR/EJECUTOR/EXTERNO;
-- el poder de venta mayorista vive en usuario_categoria (VENDEDOR, ADMIN, DIOS).
-- ATI/HUGO: rol EJECUTOR + cat VENDEDOR deben poder cerrar pedido_venta_rimec.

CREATE OR REPLACE FUNCTION public.fn_es_usuario_vendedor_o_admin(usr_id bigint)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_rol text;
  v_cat text;
BEGIN
  SELECT r.nombre_rol,
         upper(trim(COALESCE(c.codigo, u.categoria, '')))
    INTO v_rol, v_cat
  FROM public.usuario_v2 u
  JOIN public.maestro_rol_acceso r ON u.rol_id = r.id
  LEFT JOIN public.usuario_categoria c ON c.id_categoria = u.categoria_id
  WHERE u.id_usuario = usr_id;

  IF v_rol IS NULL THEN
    RETURN false;
  END IF;

  -- Legacy RBAC (MIG-066): nombre_rol era VENDEDOR/ADMIN
  IF upper(v_rol) IN ('VENDEDOR', 'ADMIN') THEN
    RETURN true;
  END IF;

  -- Triada MIG-130: categoría de acceso apps
  IF v_cat IN ('VENDEDOR', 'ADMIN', 'DIOS') THEN
    RETURN true;
  END IF;

  -- Gerentes/admins orgánicos con categoría de poder
  IF upper(v_rol) IN ('GERENTE', 'ADMINISTRADOR') AND v_cat IN ('ADMIN', 'DIOS') THEN
    RETURN true;
  END IF;

  RETURN false;
END;
$function$;

COMMENT ON FUNCTION public.fn_es_usuario_vendedor_o_admin(bigint) IS
  'Pedidos/FI: usuario puede firmar venta si cat VENDEDOR/ADMIN/DIOS (triada 130) o rol legacy VENDEDOR/ADMIN.';
