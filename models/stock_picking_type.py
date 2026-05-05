# -*- coding: utf-8 -*-
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    is_certificate_type = fields.Boolean(string='Es certificado?')
