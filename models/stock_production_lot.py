# -*- coding: utf-8 -*-
from odoo import fields, models


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    certificate_ids = fields.One2many('inventory.certificate.lot', 'lot_id', string='Certificates')
    certificate_quantity_ids = fields.Many2many('inventory.certificate', string='Certificados')
