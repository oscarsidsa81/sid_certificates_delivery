# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    certificate_add_watermark = fields.Boolean(string='Añadir Marca de agua (Batch)?')
