# -*- coding: utf-8 -*-

import base64

from odoo import fields, models, _


class CertificateRequestWizard(models.TransientModel):
    _name = 'certificate.request_wizard'
    _description = 'Document Request'

    name = fields.Char(string='Name')
    document_ids = fields.Many2many('documents.document', string='Documents')
    image = fields.Binary(string='Marca de agua', required=True)
    max_height = fields.Integer(string='Max Height')
    max_width = fields.Integer(string='Max Width')
    position_x = fields.Integer(string='Position X')
    position_y = fields.Integer(string='Position Y')

    def action_apply_watermark(self):
        # Placeholder compatible con el wizard histórico. La aplicación real de marca
        # de agua depende de librerías PDF/imagen y de la acción original.
        return {'type': 'ir.actions.act_window_close'}


class CertificateImportWizard(models.TransientModel):
    _name = 'certificate.import.wizard'
    _description = 'Certificate Request'

    name = fields.Char(string='Name')
    attachment_ids = fields.Many2many('ir.attachment', string='Adjuntos (PDF)')
    partner_id = fields.Many2one('res.partner', string='Fabricante')
    state = fields.Selection([
        ('draft', 'Pendiente subir'),
        ('done', 'Validado'),
    ], string='Estado', default='draft')

    def action_import_certificates(self):
        Cert = self.env['inventory.certificate'].sudo()
        for wiz in self:
            for att in wiz.attachment_ids:
                Cert.create({
                    'name': att.name,
                    'fabricante': wiz.partner_id.id,
                    'certificate_file': att.datas,
                    'certificate_file_name': att.name,
                    'state': wiz.state or 'draft',
                })
        return {'type': 'ir.actions.act_window_close'}


class CertificateReceptionRequestWizard(models.TransientModel):
    _name = 'certificate.reception.request_wizard'
    _description = 'Certificate Request'

    name = fields.Char(string='Name')
    certificate_id = fields.Many2one('inventory.certificate', string='Certificado')

    def action_assign_to_active_move_lines(self):
        lines = self.env['stock.move.line'].browse(self.env.context.get('active_ids', []))
        for wiz in self:
            if wiz.certificate_id and lines:
                lines.write({
                    'certificate_id': wiz.certificate_id.id,
                    'certificate_ids': [(4, wiz.certificate_id.id)],
                })
                lines.action_create_certificates_for_all()
        return {'type': 'ir.actions.act_window_close'}
