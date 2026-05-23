from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    business_unit = fields.Char(
        string="Unidad de Negocio / Zona",
        help="Zona de Ecuador a la que pertenece esta empresa para filtrar las rutas del mapa."
    )
