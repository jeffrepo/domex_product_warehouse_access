# Domex: Productos por almacén

Módulo independiente para Odoo 19. Nombre técnico:
`domex_product_warehouse_access`. Versión `19.0.1.0.0`. Depende de `stock`.

## Reglas de acceso

| Producto | Usuario | Acceso |
| --- | --- | --- |
| No contable, con almacenes | Tiene al menos uno de esos almacenes en una compañía seleccionada | Sí |
| No contable, con almacenes | No comparte ningún almacén aplicable | No |
| No contable, sin almacenes | Usuario habitual | No |
| Contable, sin almacenes | Pertenece al grupo **Producto contable** | Sí, aunque el usuario no tenga almacenes |
| Contable | No pertenece al grupo **Producto contable** | No, aunque tenga almacenes |

En todos los casos se respetan las compañías seleccionadas y las demás reglas
de Odoo. El grupo de productos contables no concede permisos de Contabilidad.
Un usuario puede combinar el grupo contable con varios almacenes y obtener
ambos conjuntos de productos.

Las reglas globales se aplican a productos y variantes, búsquedas, selectores,
lectura directa, creación, edición y eliminación mediante el ORM/API. Otros
grupos con reglas permisivas no anulan esta restricción. Todas las variantes
comparten los almacenes y la clasificación de su plantilla.

## Multicompañía

- Un usuario puede tener varios almacenes de varias compañías permitidas.
- Solo conceden acceso los almacenes activos de las compañías **seleccionadas**
  en el selector de Odoo. Si hay varias seleccionadas, se consideran todas.
- Un producto con compañía definida solo admite almacenes de esa compañía.
- Un producto compartido, sin compañía, puede tener almacenes de varias compañías.
- El mismo almacén debe coincidir con el producto, el usuario y una compañía
  seleccionada; coincidencias separadas no conceden acceso.
- Los productos contables con compañía definida solo son visibles cuando esa
  compañía está seleccionada. Los contables compartidos son visibles para el
  grupo contable dentro de las restricciones nativas restantes.
- Antes de retirar una compañía a un usuario, retirar sus almacenes de esa
  compañía; ambas modificaciones también pueden hacerse en una misma escritura.

## Configuración

1. Instalar el módulo y abrir **Ajustes → Usuarios → Permisos de acceso**.
2. En **Domex: acceso a productos**, asignar los almacenes permitidos al usuario.
   Seleccionar también las compañías correspondientes en el selector del
   administrador para que sus almacenes estén disponibles al configurar.
3. Para quien deba consultar productos de gastos, asignar el grupo
   **Producto contable**, en **Domex: Productos contables**
   (`domex_product_warehouse_access.group_accounting_product`).
4. Abrir un producto y su pestaña **Acceso Domex**. Asignar varios almacenes o
   marcar **Producto contable**.

Al marcar **Producto contable** en el formulario se vacían los almacenes. La
validación del servidor rechaza productos contables con almacenes también en
importaciones/API. En una importación que convierta productos existentes,
enviar el booleano y la eliminación de sus almacenes en la misma operación.

Los campos de configuración están protegidos en el servidor para que solo
los administradores de Ajustes puedan editarlos. Los usuarios no pueden
asignarse almacenes ni cambiar la clasificación de un producto para ampliar
su acceso. Las asignaciones y cambios de grupo surten efecto sin reiniciar Odoo.

Los administradores de Ajustes pueden ver productos **no contables** sin
restricción por almacén, dentro de las compañías seleccionadas. Para ver
productos **contables** también necesitan el grupo nuevo. La instalación
asigna inicialmente ese grupo al administrador principal (`base.user_admin`);
otros administradores deben recibirlo explícitamente. Si se retira al
administrador principal, una actualización no vuelve a añadirlo.

## Instalación y catálogo existente

Colocar este repositorio como una carpeta llamada
`domex_product_warehouse_access` dentro de una ruta de addons, junto a los
demás módulos. En Odoo.sh, integrarlo como carpeta o submódulo del proyecto.
Actualizar la lista de aplicaciones, quitar el filtro **Aplicaciones**, buscar
el nombre técnico e instalarlo. No requiere modificar ni instalar `gdomex`.

La instalación no deduce ni rellena asignaciones. Los productos existentes
quedan inicialmente sin almacenes y con **Producto contable** desmarcado;
los usuarios habituales no los verán hasta configurarlos. Preparar las
asignaciones del catálogo y de los usuarios con un administrador antes de
habilitar la operación habitual. La creación de nuevas plantillas queda en
manos de los administradores, que pueden configurar esos campos; los demás
usuarios conservan sus permisos nativos para los productos que pueden ver.

El alcance es el acceso al catálogo. No agrega restricciones a documentos,
movimientos ni existencias de cada almacén, ni sustituye sus permisos nativos.
Las reglas también alcanzan usuarios externos si acceden mediante el ORM sin
elevación de permisos. Como en las reglas nativas de Odoo, el modo superusuario
y `sudo()` las omiten; los controladores o reportes que eleven permisos deben
revisarse aparte si se usan para exponer el catálogo.

## Validación

Se incluyen pruebas de integración de productos y variantes, ambos tipos de
acceso, usuarios sin almacenes, multicompañía, coincidencia del mismo almacén,
permisos por API, cambios de grupo/asignación, almacenes archivados y formularios.

```sh
odoo-bin -d BASE_DE_PRUEBAS -i domex_product_warehouse_access --test-enable --test-tags /domex_product_warehouse_access --stop-after-init
```

Para actualizar una instalación, sustituir `-i` por `-u`. Ejecutar en una base
de pruebas de Odoo 19. La revisión local cubre sintaxis Python, esquema XML,
referencias y XPath contra el código nativo de Odoo 19; las pruebas de
integración requieren un servidor Odoo con PostgreSQL y no se ejecutaron en
este entorno.

Las reglas siguen el modelo de [seguridad de Odoo 19](https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html).

Licencia: LGPL-3.
