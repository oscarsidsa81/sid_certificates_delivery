# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    certificate_needed = fields.Boolean(string='Certificado Obligatorio')
    certificate_needed_in = fields.Boolean(string='Certificado Obligatorio')
    certificate_issued = fields.Boolean(string='Certificado Emitido')
    certificate_add_watermark = fields.Boolean(string='Añadir Marca de agua?')
    is_certificate_picking = fields.Boolean(string='Is Certificate Picking', compute='_compute_is_certificate_picking', store=True)
    certificate_count = fields.Integer(string='Certificados', compute='_compute_certificate_count')

    @api.depends('picking_type_id', 'picking_type_id.is_certificate_type', 'certificate_needed', 'certificate_needed_in')
    def _compute_is_certificate_picking(self):
        for picking in self:
            picking.is_certificate_picking = bool(
                picking.certificate_needed or
                picking.certificate_needed_in or
                (picking.picking_type_id and picking.picking_type_id.is_certificate_type)
            )

    def _compute_certificate_count(self):
        for picking in self:
            certs = picking.move_line_ids.mapped('certificate_ids') | picking.move_line_ids.mapped('certificate_id')
            picking.certificate_count = len(certs)

    def action_view_certificates(self):
        self.ensure_one()
        certs = self.move_line_ids.mapped('certificate_ids') | self.move_line_ids.mapped('certificate_id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Certificados'),
            'res_model': 'inventory.certificate',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', certs.ids)],
            'target': 'current',
        }

    def action_certificate_find_all(self):
        return self.mapped('move_line_ids').action_find_certificates_by_line()

    def action_certificate_create_all(self):
        return self.mapped('move_line_ids').action_create_certificates_for_all()

    def action_certificate_assign_all(self):
        return self.mapped('move_line_ids').action_assign_certificate_id()
