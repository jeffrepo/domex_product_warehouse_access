# Domex: Productos por almacén

Módulo independiente para Odoo 19. Nombre técnico:
`domex_product_warehouse_access`. Versión `19.0.1.1.0`. Depende de `stock`.
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

Si la categoría del producto está marcada **Vinyasa**, se requiere además el
grupo **Vinyasa**, salvo para la cuenta principal de administrador. Las
categorías sin marcar permanecen compartidas: no se filtran por compañía,
almacenes, grupo contable ni por la marca de una categoría padre. Compartir
una categoría no elimina los requisitos de acceso de sus productos.

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
   autorizados (`domex_product_warehouse_access.group_vinyasa`).

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
   y actualizado a `19.0.1.1.0`. El push a GitHub por sí solo no instala el módulo
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

| Categoría | Sin grupo Vinyasa | Con grupo Vinyasa | Cuenta principal |
| --- | --- | --- | --- |
| Vinyasa desmarcado | Visible | Visible | Visible |
| Vinyasa marcado | Oculta | Visible | Visible |

Se conservan las ACL nativas de categorías. El grupo Vinyasa no concede
permisos de administración ni acceso a compañías adicionales. Los demás
administradores de Ajustes también necesitan el grupo para ver las categorías
marcadas; la excepción automática es solo para `base.user_admin`.

La marca es **individual**, no se hereda. Una hija sin marcar sigue compartida
aunque su padre sea Vinyasa; marcar una hija no restringe su padre ni sus
hermanas. Para restringir varias categorías, marcarlas individualmente o desde
la edición en bloque de la lista. No se deduce la marca por el nombre de la
categoría ni por una compañía llamada Vinyasa.

Los productos y variantes cuya categoría está marcada se ocultan a quienes
no tienen el grupo, también en selectores de facturas y lecturas por API.
Esto evita ofrecer un producto cuya categoría no se pueda abrir. Para los
miembros del grupo continúan aplicándose los requisitos de almacenes,
Producto contable y compañías seleccionadas. Un producto contable de una
categoría Vinyasa requiere ambos grupos. Los productos de categorías sin
marcar, o sin categoría, mantienen las reglas anteriores de productos.

Solo Ajustes puede editar el booleano, también por importación/API. Los demás
usuarios no pueden quitar la protección cambiando un producto a una categoría
sin marcar, ni eliminando una categoría padre que arrastraría una categoría
Vinyasa. Las categorías comunes sí pueden crearse, duplicarse y compartirse
con los permisos nativos. Cambiar un padre no cambia la marca de sus hijas.

### Retirar `product_category_company`

Si ese módulo sigue instalado, sus reglas y validaciones también se aplican;
este módulo no las modifica ni las desactiva automáticamente. Para usar
exclusivamente el control solicitado:

1. Actualizar **domex_product_warehouse_access** a `19.0.1.1.0` en la base de
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

La suite Vinyasa cubre categorías compartidas entre compañías, marcas
individuales sin herencia, lectura del formulario de una hija compartida,
permisos por grupo, cambios de clasificación, búsquedas y lectura directa de
productos/variantes, selectores de facturas, importaciones protegidas,
valores predeterminados, expansión de grupos y conservación de la protección
al editar o eliminar. Ejecutarla sin `product_category_company` instalado.

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
