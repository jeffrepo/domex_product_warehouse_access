# Domex: Productos por almacén

Módulo independiente para Odoo 19. Nombre técnico:
`domex_product_warehouse_access`. Versión `19.0.1.0.2`. Depende de `stock`.

## Reglas de acceso

| Producto | Usuario | Acceso |
| --- | --- | --- |
| Cualquier producto | Cuenta principal de administrador | Sí, dentro de las compañías seleccionadas |
| No contable, con almacenes | Tiene al menos uno de esos almacenes en una compañía seleccionada | Sí |
| No contable, con almacenes | No comparte ningún almacén aplicable | No |
| No contable, sin almacenes | Usuario habitual | No |
| Contable, sin almacenes | Pertenece al grupo **Producto contable** | Sí, aunque el usuario no tenga almacenes |
| Contable | Usuario habitual sin el grupo **Producto contable** | No, aunque tenga almacenes |

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

La cuenta principal de administrador (`base.user_admin`) ve **todos los productos**
de las compañías seleccionadas, contables y no contables, incluso sin almacenes
ni el grupo Producto contable. La excepción identifica esa cuenta por su ID
externo, no por su nombre o login. Los demás usuarios siguen las reglas aunque
tengan la función **Administrador** (`base.group_system`) o sean responsables de
Inventario o Contabilidad. Las asignaciones de grupos existentes se conservan
al actualizar. Los permisos de Ajustes permiten administrar la configuración
de seguridad; esta restricción de catálogo no retira esos permisos.

## Cuándo se aplican las reglas

Se aplican desde que el módulo está instalado y actualizado en la base de datos,
en cada búsqueda de productos o variantes, incluidas las listas de Productos y
los selectores de productos en facturas. No dependen de validar la factura ni
de una tarea programada. Después de modificar permisos, volver a abrir la vista
o el selector para descartar resultados que el navegador ya tenía cargados.

Si un usuario ve todos los productos:

1. Comprobar que no sea la cuenta principal `base.user_admin`. En `19.0.1.0.0`
   la excepción alcanzaba a cualquier usuario con función Administrador;
   desde `19.0.1.0.1` se limita a la cuenta principal.
2. Comprobar que no está usando el modo superusuario; el modo desarrollador
   por sí solo no omite las reglas.
3. Verificar en Aplicaciones que `domex_product_warehouse_access` está instalado
   y actualizado a `19.0.1.0.2`. El push a GitHub por sí solo no instala el módulo
   ni actualiza los registros de seguridad de una base existente.
4. En modo desarrollador, revisar en **Ajustes → Técnico → Seguridad → Reglas de
   registro** las dos reglas cuyo nombre comienza por **Domex:**. Deben estar
   activas, ser globales (sin grupos) y aplicar a `product.template` y
   `product.product`, con lectura habilitada.
5. Para una prueba controlada, usar un usuario normal sin almacenes ni grupo
   Producto contable: no debe encontrar ningún producto. Asignarle un almacén
   y verificar que encuentra exclusivamente productos vinculados a él, de las
   compañías seleccionadas. El grupo contable añade únicamente los contables.

Si esta prueba falla con un usuario normal, revisar la instalación, las reglas
efectivas y posibles personalizaciones que utilicen `sudo()`. No debe añadirse
un filtro visual como sustituto de las reglas de seguridad del servidor.

## Categorías restringidas por compañía

El acceso al producto no concede acceso a su categoría. Si otro módulo limita
`product.category` a la compañía principal activa, un producto compartido que
tenga categoría de otra compañía puede aparecer en la lista y fallar al abrir
la ficha. La excepción de este módulo para la cuenta principal tampoco anula
las reglas de otros modelos.

En Odoo 19, un error de acceso con una compañía sugerida puede provocar una
recarga automática del formulario. Odoo agrega esa compañía al conjunto de
seleccionadas sin convertirla en la principal. Una regla que exige la compañía
principal seguirá rechazando la categoría y puede provocar recargas repetidas.

Desde `19.0.1.0.1`, para errores de productos, variantes y categorías, el módulo
retira la indicación de recarga cuando la compañía sugerida ya está seleccionada.
Conserva la denegación de acceso y su mensaje. Si la compañía aún no estaba
seleccionada, conserva el intento nativo; si ese intento no resuelve el permiso,
se muestra el error al volver a cargar, sin repetir indefinidamente. No concede
acceso a categorías ni cambia automáticamente la compañía principal.

Corregir la categoría del producto para el uso previsto o revisar la política
de categorías compartidas. Un producto estándar tiene una sola categoría: no
puede ofrecer una categoría distinta por cada almacén o compañía. Seleccionar
la compañía de la categoría como principal sirve para comprobar el origen del
error, siempre que el producto también sea accesible allí. Este módulo no
modifica ni relaja las reglas del módulo de categorías.

## Error de Contacto al abrir otro usuario

El formulario estándar de Odoo 19 muestra las compañías permitidas mediante
etiquetas de colores. Para obtener `res.company.color`, Odoo lee el color del
contacto de la compañía raíz (`root_id.partner_id.color`). Un administrador
de usuarios puede leer esas compañías sin tener acceso a sus contactos:
pueden pertenecer a compañías no seleccionadas o no permitidas para él.
En ese caso, la carga de `res.users/web_read` falla con un error de
`res.partner`, aunque el contacto del usuario que está abriendo sea accesible.

Desde `19.0.1.0.2`, las etiquetas del campo **Empresas** de ese formulario se
muestran sin colores. Así se elimina esa lectura decorativa de contactos;
se conserva la posibilidad de consultar y asignar compañías según los permisos
nativos. No se cambian las compañías de los contactos ni se amplía su acceso.

La protección contra recargas repetidas también cubre errores de `res.users`
y `res.partner`. Solo retira la sugerencia de recarga cuando esa compañía ya
está seleccionada; conserva el error y los demás datos de la excepción.

El módulo no crea reglas de acceso para Contactos. Si el error persiste,
identificar los contactos del log y las reglas que fallan en esa base. Los IDs
del log no demuestran que se trate del contacto del usuario: pueden corresponder
a compañías u otras relaciones. Revisar el dominio de las reglas activas de
`res.partner` y las compañías seleccionadas; no resolverlo concediendo acceso
general a todos los contactos. La corrección de las etiquetas evita una causa
concreta, pero no suprime otras denegaciones legítimas o personalizadas.

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
habilitar la operación habitual. Preparar las nuevas plantillas desde la cuenta
principal permite configurar esos campos antes de dar acceso al producto.
Los demás usuarios conservan sus permisos nativos para los productos que
pueden ver; los campos de configuración requieren permisos de Ajustes.

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
También se cubren la excepción exclusiva de la cuenta principal y la prevención
de recargas repetidas en errores de acceso con una compañía ya seleccionada.
Para la administración de usuarios se incluye una prueba de lectura del
formulario con contactos de compañías restringidos, tanto de una compañía
permitida sin seleccionar como de otra no permitida al administrador.

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
