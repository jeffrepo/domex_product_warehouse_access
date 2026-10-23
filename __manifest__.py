{
    "name": "Domex: Productos por almacén",
    "summary": "Productos por almacén, productos contables y categorías Vinyasa, multicompañía",
    "version": "19.0.1.2.2",
    "category": "Inventory/Inventory",
    "author": "Silva Technologies",
    "license": "LGPL-3",
    "depends": ["stock", "sale"],
    "data": [
        "security/groups.xml",
        "security/product_warehouse_rules.xml",
        "security/product_category_rules.xml",
        "views/res_users_views.xml",
        "views/product_views.xml",
        "views/product_category_views.xml",
    ],
    "installable": True,
    "application": False,
}
