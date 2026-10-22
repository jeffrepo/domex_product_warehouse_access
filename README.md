# Domex: Productos por almacén

Módulo independiente para Odoo 19. Nombre técnico:
`domex_product_warehouse_access`. Versión `19.0.1.2.1`. Depende de `stock` y `sale`.
Incluye el control de categorías Vinyasa; no depende de `product_category_company`.

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

El grupo **Vinyasa** selecciona un catálogo exclusivo: sus miembros ven solo
categorías marcadas y productos de esas categorías. Los usuarios sin ese grupo
ven las categorías sin marcar y sus productos, además de productos sin
categoría. El grupo **Todas las categorías** permite ambos catálogos y productos
sin categoría, tenga o no el usuario el grupo Vinyasa. La cuenta principal de
administrador conserva ambos catálogos sin requerir estos grupos.
Las categorías no se filtran por compañía, almacenes, grupo contable ni por la
marca de una categoría padre. Los productos conservan sus requisitos de acceso.

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
5. En **Categorías de producto**, marcar **Vinyasa** exclusivamente en las
   categorías que deban restringirse. También puede editarse desde la lista.
6. Asignar el grupo **Vinyasa**, en **Domex: Categorías Vinyasa**, a los usuarios
   que deban trabajar exclusivamente con ese catálogo
   (`domex_product_warehouse_access.group_vinyasa`).
7. Para quienes necesiten consultar Vinyasa y las categorías comunes, asignar
   **Todas las categorías**, en **Domex: Todas las categorías**
   (`domex_product_warehouse_access.group_all_product_categories`). Se puede
   conservar su grupo Vinyasa y su grupo Producto contable. Este permiso no
   sustituye los almacenes ni las compañías permitidas/seleccionadas.

Al marcar **Producto contable** en el formulario se vacían los almacenes. La
validación del servidor rechaza productos contables con almacenes también en
importaciones/API. En una importación que convierta productos existentes,
enviar el booleano y la eliminación de sus almacenes en la misma operación.

Solo Ajustes puede modificar los almacenes permitidos de un usuario y las
marcas Producto contable y Vinyasa. Los usuarios con **Creación de productos**
pueden asignar sus almacenes permitidos a productos accesibles, como se explica
a continuación. No pueden asignarse almacenes adicionales en su usuario ni
cambiar la clasificación para ampliar su acceso. Las asignaciones y cambios
de grupo surten efecto sin reiniciar Odoo.

### Crear y asignar productos desde un usuario habitual

Desde `19.0.1.2.1`, los usuarios con **Productos → Creación de productos**
(`product.group_product_manager`) tienen la pestaña **Acceso Domex** en productos
y variantes. Pueden elegir uno o varios de sus almacenes permitidos al crear
un producto y modificar esas asignaciones en productos a los que ya tienen
acceso de escritura. No necesitan permisos de Ajustes ni de Inventario.

El selector ofrece únicamente almacenes activos, permitidos al usuario y de
compañías seleccionadas. Si el producto tiene compañía, los almacenes deben
pertenecer a ella; si es compartido, puede combinar almacenes permitidos de
las compañías seleccionadas. Por ejemplo, para crear un producto de APLYTEK
S.A. (38), se necesita un almacén cuya compañía sea APLYTEK S.A. (38): el
nombre comercial del almacén no determina su compañía.

Un producto normal necesita al menos uno de esos almacenes. Dejar el campo
vacío no evita la restricción: ahora se muestra un aviso para completar
**Acceso Domex**. Si no hay opciones, Ajustes debe asignar al usuario el almacén
correspondiente y el usuario debe seleccionar su compañía en Odoo. No se
asignan almacenes automáticamente. En creación rápida, utilizar **Crear y
editar** para completar la pestaña antes de guardar.

Los cambios se validan también en importaciones, API y valores predeterminados.
El usuario puede agregar o retirar únicamente almacenes autorizados para ese
producto y debe conservar al menos uno que le permita acceder. No puede
retirar asignaciones ajenas, archivadas o de compañías no seleccionadas, ni
agregar un almacén propio a un producto que ya tenía restringido. Esos casos
requieren un administrador de Ajustes con acceso al producto. Las operaciones
de reemplazo en una importación deben conservar las asignaciones protegidas.
El campo no permite crear, modificar ni eliminar registros de almacenes.

Las reglas de categorías, compañías y productos contables se mantienen.
Tener **Producto contable** no convierte automáticamente los productos nuevos
en contables. Esa clasificación sigue reservada a Ajustes y los productos
contables continúan sin almacenes. La cuenta principal de administrador puede
seguir preparando productos normales sin asignaciones.

Actualizar **domex_product_warehouse_access** a `19.0.1.2.1` en Aplicaciones
después de desplegar el código. Se utiliza el permiso nativo de creación;
no hay que asignar un grupo nuevo. La actualización no modifica almacenes,
compañías, categorías ni permisos existentes.

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
   y actualizado a `19.0.1.2.1`. El push a GitHub por sí solo no instala el módulo
   ni actualiza los registros de seguridad de una base existente.
4. En modo desarrollador, revisar en **Ajustes → Técnico → Seguridad → Reglas de
   registro** las reglas **Domex:** de productos, variantes y categorías.
   Deben estar activas, ser globales (sin grupos) y aplicar a
   `product.template`, `product.product` y `product.category`, con lectura habilitada.
5. Para una prueba controlada, usar un usuario normal sin almacenes ni grupo
   Producto contable: no debe encontrar ningún producto. Asignarle un almacén
   y verificar que encuentra exclusivamente productos vinculados a él, de las
   compañías seleccionadas. El grupo contable añade únicamente los contables.

Si esta prueba falla con un usuario normal, revisar la instalación, las reglas
efectivas y posibles personalizaciones que utilicen `sudo()`. No debe añadirse
un filtro visual como sustituto de las reglas de seguridad del servidor.

## Categorías compartidas y Vinyasa

| Categoría | Sin ninguno de los dos grupos | Solo Vinyasa | Todas las categorías, con o sin Vinyasa | Cuenta principal |
| --- | --- | --- | --- | --- |
| Vinyasa desmarcado | Visible | Oculta | Visible | Visible |
| Vinyasa marcado | Oculta | Visible | Visible | Visible |

Se conservan las ACL nativas de categorías. El grupo Vinyasa no concede
permisos de administración ni acceso a compañías adicionales. Los demás
administradores de Ajustes siguen la misma separación según sus grupos Vinyasa
y Todas las categorías; la excepción automática es solo para `base.user_admin`.

La marca es **individual**, no se hereda. Una hija sin marcar sigue compartida
entre compañías para usuarios sin el grupo, aunque su padre sea Vinyasa. Los
miembros que tengan únicamente Vinyasa no ven esa hija sin marcar. Marcar una
hija no cambia el acceso a su padre ni a sus hermanas. Para clasificar varias categorías,
marcarlas individualmente o desde la edición en bloque de la lista. No se
deduce la marca por el nombre de la categoría ni por una compañía llamada Vinyasa.

Los productos y variantes siguen esa misma separación, también en selectores
de facturas y lecturas por API. Sin Todas las categorías, un miembro de Vinyasa
no ve productos de categorías sin marcar ni productos sin categoría; un usuario
sin Vinyasa no ve productos de categorías marcadas. En ambos catálogos continúan
aplicándose los requisitos de almacenes, Producto contable y compañías seleccionadas.
Un producto contable de una categoría Vinyasa requiere Producto contable y
además Vinyasa o Todas las categorías. Los productos sin categoría son accesibles
para usuarios sin Vinyasa o con Todas las categorías, sujetos a sus almacenes
o al grupo Producto contable.

Solo Ajustes puede editar el booleano, también por importación/API. Los demás
usuarios no pueden quitar la protección cambiando un producto a una categoría
sin marcar, ni eliminando una categoría padre que arrastraría una categoría
Vinyasa. Los usuarios sin el grupo pueden crear, duplicar y compartir
categorías comunes con los permisos nativos. Las categorías Vinyasa deben
ser clasificadas por un administrador de Ajustes con acceso a ellas.
Cambiar un padre no cambia la marca de sus hijas.

### Usuarios que necesitan ambos catálogos

Desde `19.0.1.2.0`, **Todas las categorías** permite acceder a las categorías
Vinyasa y comunes sin cambiar sus marcas. Por ejemplo, un usuario con Vinyasa
y Producto contable puede necesitar abrir una factura de proveedor de otra
compañía que contiene un servicio contable en **Gastos de Operación**, una
categoría sin marca Vinyasa. Asignar Todas las categorías permite leer ese
producto y su categoría, siempre que la compañía del producto esté seleccionada
y el usuario tenga los permisos nativos de la factura.

El grupo es independiente: no añade ni retira Vinyasa, Producto contable,
almacenes ni permisos de Ajustes. Si se retira Todas las categorías, vuelve a
aplicarse el catálogo definido por el grupo Vinyasa que el usuario conserve.
Los cambios de grupo invalidan las reglas sin reiniciar Odoo. Los productos
normales siguen requiriendo un almacén coincidente y activo; los contables
siguen requiriendo Producto contable. Las restricciones globales de otros
módulos y las protecciones de configuración permanecen vigentes.

Para actualizar desde `19.0.1.1.2`, desplegar el código y actualizar
**domex_product_warehouse_access** a `19.0.1.2.1` en Aplicaciones. Después,
en **Ajustes → Usuarios → Permisos de acceso**, asignar **Todas las categorías**
a cada usuario que necesite ambos catálogos. No se asigna automáticamente a
ningún usuario ni a todos los administradores. Volver a abrir la factura o
el selector para descartar datos que el navegador ya tenía cargados.

### Actualizar desde `19.0.1.1.0`

Actualizar **domex_product_warehouse_access** a `19.0.1.2.1` en Aplicaciones.
Se conservan el mismo grupo, sus usuarios y las marcas existentes. La diferencia
es que los miembros del grupo pasan de ver ambos catálogos a ver únicamente
Vinyasa, salvo que se les asigne Todas las categorías. No es necesario quitar y
volver a asignar Vinyasa. Volver a abrir las listas y selectores después de
actualizar para descartar datos ya cargados.

### Retirar `product_category_company`

Si ese módulo sigue instalado, sus reglas y validaciones también se aplican;
este módulo no las modifica ni las desactiva automáticamente. Para usar
exclusivamente el control solicitado:

1. Actualizar **domex_product_warehouse_access** a `19.0.1.2.1` en la base de
   pruebas. No basta con descargar el código o reiniciar.
2. Si ya se configuraron categorías con la primera implementación de Vinyasa
   en `product_category_company`, mantener ese módulo disponible durante esta
   actualización. El nuevo módulo declara el mismo campo `domex_vinyasa` para
   conservar sus marcas al retirar el anterior. El grupo ahora pertenece a
   **domex_product_warehouse_access**: asignar los usuarios a este nuevo grupo.
3. Desinstalar **product_category_company** desde Aplicaciones. No borrar
   primero la carpeta de un módulo todavía instalado. Se retira su separación
   por compañía; las categorías conservan el comportamiento compartido nativo.
4. Verificar las categorías marcadas y los miembros del nuevo grupo antes de
   pasar a producción. La restricción heredada de padres de aquella primera
   implementación desaparece: únicamente cuentan las marcas individuales.

La nueva función no asigna grupos automáticamente ni marca categorías
existentes que no lo estuvieran. Se conservan las asignaciones de almacenes
y Producto contable. Las propiedades contables dependientes de compañía
continúan con el comportamiento nativo de Odoo.

## Errores de categoría por reglas de otros módulos

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
error, siempre que el producto también sea accesible allí. Las reglas de
módulos externos deben revisarse o retirarse según la política de categorías
compartidas; la regla Vinyasa de este módulo no las sustituye.

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

## Fecha prevista en la lista de Ventas

Desde `19.0.1.1.2`, el cálculo nativo de `sale.order.expected_date` se ejecuta
con `compute_sudo=True`. Odoo consulta el tipo de producto de las líneas al
calcular esa fecha. Si una venta existente contiene productos que el usuario
ya no puede leer, mostrar la columna **Fecha prevista** podía bloquear toda
la lista con un error de acceso a `product.product`.

La elevación se limita al cálculo de la fecha de una venta accesible. Se
conservan las reglas de acceso a ventas, las compañías seleccionadas y las
restricciones del catálogo, incluidos almacenes, Producto contable y Vinyasa.
No se omiten líneas para calcular una fecha parcial. El cálculo sigue siendo
el nativo, con las políticas de entrega de `sale_stock`, pedidos cancelados y
exclusión de servicios. El cambio no concede acceso a las fichas ni a los
selectores de los productos restringidos. Abrir una venta y leer sus líneas
puede seguir requiriendo acceso a esos productos.

Actualizar el módulo en Aplicaciones después de desplegar el código.
Desde `19.0.1.1.2` se incluye la dependencia explícita de Ventas (`sale`) para
extender su campo. No cambia asignaciones, compañías ni grupos existentes.

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
pueden ver. Creación de productos permite asignar sus almacenes autorizados;
la configuración de usuarios y las marcas contable/Vinyasa requieren Ajustes.

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
Se cubren también la creación desde ambos formularios con y sin categoría,
asignaciones permitidas en creación y edición, importación, valores por contexto,
revocaciones, comandos relacionales y conservación de almacenes de otras compañías.
También se cubren la excepción exclusiva de la cuenta principal y la prevención
de recargas repetidas en errores de acceso con una compañía ya seleccionada.
Para la administración de usuarios se incluye una prueba de lectura del
formulario con contactos de compañías restringidos, tanto de una compañía
permitida sin seleccionar como de otra no permitida al administrador.

La suite Vinyasa cubre catálogos exclusivos por grupo, categorías compartidas entre compañías, marcas
individuales sin herencia, lectura del formulario de una hija compartida,
permisos por grupo, cambios de clasificación, búsquedas y lectura directa de
productos/variantes, selectores de facturas, importaciones protegidas,
valores predeterminados, expansión de grupos y conservación de la protección
al editar o eliminar. Ejecutarla sin `product_category_company` instalado.

También cubre Todas las categorías con y sin Vinyasa, concesión y revocación
sin perder la asignación previa, lectura del servicio contable y su categoría
común, productos sin categoría, requisitos contables y de almacenes,
compañías seleccionadas/permitidas, reglas globales adicionales y protección
contra cambios de clasificación o escaladas de permisos.

La suite de Ventas reproduce el fallo de `web_search_read` al calcular la fecha
con productos restringidos y comprueba el acceso posterior al catálogo, las
reglas por vendedor y compañía, productos contables y categorías Vinyasa,
ventas vacías/canceladas y las dos políticas de entrega cuando está instalado
`sale_stock`.

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
