from odoo import models, fields

class BlockRoutesRoute(models.Model):
    _name = 'block_routes.route'
    _description = 'Ruta de Ecuador'

    name = fields.Char(string="Nombre de Ruta", required=True)
    business_unit = fields.Char(
        string="Unidad de Negocio / Zona",
        help="Zona a la que pertenece esta ruta"
    )
    geojson = fields.Text(
        string="GeoJSON",
        required=True,
        help="Geometría del polígono en formato GeoJSON"
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'El nombre de la ruta debe ser único.')
    ]


