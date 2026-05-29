from odoo import models, fields, api
from odoo.exceptions import ValidationError

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
    
    date_start = fields.Datetime(
        string="Fecha de Inicio",
        required=True,
        default=fields.Datetime.now,
        help="Momento en el que entra en vigor el bloqueo"
    )
    
    date_end = fields.Datetime(
        string="Fecha de Fin",
        required=True,
        help="Momento en el que expira el bloqueo"
    )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end <= record.date_start:
                raise ValidationError("La fecha de fin debe ser posterior a la fecha de inicio del bloqueo.")

    @api.model
    def cron_import_excel_blocked_routes(self):
        """
        Acción planificada (Cron) para importar de forma automatizada los bloqueos
        desde archivos Excel guardados en la ubicación física configurada.
        """
        from ..tools.excel_importer import import_excel_blocked_routes
        import_excel_blocked_routes(self.env)

    @api.model
    def cron_import_shapes_to_routes(self):
        """
        Acción planificada (Cron) para importar/actualizar geometrías de rutas
        desde archivos Shapefile guardados en la ubicación física configurada.
        """
        from ..tools.shape_importer import import_shapes_to_routes
        import_shapes_to_routes(self.env)
