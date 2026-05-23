from odoo import models, fields

class BlockRoutesBlocked(models.Model):
    _name = 'block_routes.blocked'
    _description = 'Registro de Ruta Bloqueada'

    route_id = fields.Many2one(
        'block_routes.route',
        string="Ruta",
        required=True,
        ondelete='cascade'
    )
    reason = fields.Char(string="Motivo del Bloqueo")
    date_blocked = fields.Datetime(
        string="Fecha de Bloqueo",
        default=fields.Datetime.now
    )
