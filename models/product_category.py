from odoo import fields, models
from odoo.exceptions import AccessError


class ProductCategory(models.Model):
    _inherit = "product.category"

    domex_vinyasa = fields.Boolean(
        string="Vinyasa",
        default=False,
        copy=False,
        index=True,
        groups="base.group_system",
        help="Solo los usuarios del grupo Vinyasa y la cuenta principal de "
             "administrador pueden acceder a esta categoría y sus productos. "
             "Sin marcar, la categoría sigue compartida entre compañías. "
             "La marca no se hereda a las subcategorías.",
    )

    def unlink(self):
        if not self.env.su and not self.env.user.has_group("base.group_system"):
            self.check_access("unlink")
            # Native deletion cascades to children and clears product categories.
            # Prevent deleting a shared parent to remove a child's protection.
            if self.sudo().search_count([
                ("id", "child_of", self.ids), ("domex_vinyasa", "=", True),
            ]):
                raise AccessError(self.env._(
                    "Solo un administrador de Ajustes puede eliminar categorías "
                    "Vinyasa o categorías que contengan subcategorías Vinyasa."
                ))
        return super().unlink()

    def copy_data(self, default=None):
        can_classify = self.env.su or self.env.user.has_group("base.group_system")
        if not can_classify:
            self.check_access("read")
            if any(self.sudo().mapped("domex_vinyasa")):
                raise AccessError(self.env._(
                    "Solo un administrador de Ajustes puede duplicar categorías Vinyasa."
                ))
        values_list = super().copy_data(default)
        if can_classify and "domex_vinyasa" not in (default or {}):
            # Preserve classification for administrators; copy=False lets other
            # users copy shared categories without reading a protected field.
            for category, values in zip(self, values_list):
                if values is not None:
                    values["domex_vinyasa"] = category.domex_vinyasa
        return values_list
