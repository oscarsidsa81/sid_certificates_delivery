# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class InventoryCertificate(models.Model):
    _name = 'inventory.certificate'
    _description = 'Certificates'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Name')
    active = fields.Boolean(string='Active', default=True)
    type = fields.Selection([
        ('receipt', 'Recepción'),
        ('delivery', 'Entrega'),
    ], string='Tipo', default='receipt', tracking=True)
    state = fields.Selection([
        ('draft', 'Pendiente subir'),
        ('done', 'Validado'),
    ], string='Estado', default='draft', tracking=True)
    product_id = fields.Many2one('product.product', string='Producto')
    fabricante = fields.Many2one('res.partner', string='Fabricante')
    lot_ids = fields.Many2many('stock.production.lot', string='Lotes')
    certificate_lots = fields.One2many('inventory.certificate.lot', 'certificate_id', string='Certificate Lots', readonly=True)
    certificate_moves = fields.One2many('inventory.certificate.line', 'certificate_id', string='Movimientos de certificado')
    quantity_received = fields.Float(string='Cantidad Recibida', compute='_compute_certificate_quantities', store=True)
    quantity_done = fields.Float(string='Cantidad Entregada', compute='_compute_certificate_quantities', store=True)
    quantity_certificate = fields.Float(string='Cantidad Disponible', compute='_compute_certificate_quantities', store=True)
    certificate_file = fields.Binary(string='Certificado')
    certificate_file_name = fields.Char(string='Nombre del archivo')
    note = fields.Text(string='Datos adicionales')

    @api.depends(
        'certificate_lots.quantity_received', 'certificate_lots.quantity_done',
        'certificate_moves.qty', 'certificate_moves.type',
    )
    def _compute_certificate_quantities(self):
        for cert in self:
            received = sum(cert.certificate_lots.mapped('quantity_received'))
            done = sum(cert.certificate_lots.mapped('quantity_done'))
            if not received:
                received = sum(cert.certificate_moves.filtered(lambda l: l.type == 'in').mapped('qty'))
            if not done:
                done = sum(cert.certificate_moves.filtered(lambda l: l.type == 'out').mapped('qty'))
            cert.quantity_received = received
            cert.quantity_done = done
            cert.quantity_certificate = received - done

    def action_validate_certificate(self):
        self.write({'state': 'done'})
        return True

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
        return True

    def _get_certificate_documents_folder(self):
        """Best-effort folder resolver for certificate PDFs.

        The original Studio/server action used production configuration. This method first
        tries stable XML IDs commonly used by SID dossier/certificate modules, then falls back
        to folders whose name contains Certificados.
        """
        xmlids = [
            'sid_projects_dossier.sid_workspace_quality_dossiers',
            'sid_projects_dossier.folder_root_dossieres_calidad',
            'oct_certificate_management.documents_folder_certificates',
            'oct_certificate_receptions.documents_folder_certificates',
        ]
        for xmlid in xmlids:
            folder = self.env.ref(xmlid, raise_if_not_found=False)
            if folder and folder._name == 'documents.folder':
                return folder
        return self.env['documents.folder'].sudo().search([('name', 'ilike', 'Certificados')], limit=1)

    def action_create_documents(self):
        """Replacement for OV - Certificados crea doc en Certificados Inventario.

        Creates/updates ir.attachment and, when documents is available, a documents.document
        linked to the attachment. The exact original folder can be forced by overriding
        _get_certificate_documents_folder or adding one of the XML IDs above.
        """
        Attachment = self.env['ir.attachment'].sudo()
        Document = self.env['documents.document'].sudo()
        folder = self._get_certificate_documents_folder()
        for cert in self:
            if not cert.certificate_file:
                continue
            filename = cert.certificate_file_name or cert.name or _('Certificado')
            att_vals = {
                'name': filename,
                'type': 'binary',
                'datas': cert.certificate_file,
                'res_model': cert._name,
                'res_id': cert.id,
                'mimetype': 'application/pdf',
            }
            attachment = Attachment.search([
                ('res_model', '=', cert._name),
                ('res_id', '=', cert.id),
                ('name', '=', filename),
            ], limit=1)
            if attachment:
                attachment.write(att_vals)
            else:
                attachment = Attachment.create(att_vals)
            doc = Document.search([('attachment_id', '=', attachment.id)], limit=1)
            doc_vals = {'name': filename, 'attachment_id': attachment.id, 'res_model': cert._name, 'res_id': cert.id}
            if folder:
                doc_vals['folder_id'] = folder.id
            if doc:
                doc.write(doc_vals)
            else:
                Document.create(doc_vals)
        return True


class InventoryCertificateLine(models.Model):
    _name = 'inventory.certificate.line'
    _description = 'Certificate Lines'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    certificate_id = fields.Many2one('inventory.certificate', string='Certificado', ondelete='cascade')
    move_line_id = fields.Many2one('stock.move.line', string='Movimiento')
    picking_id = fields.Many2one('stock.picking', string='Picking')
    lot_id = fields.Many2one('stock.production.lot', string='Lote')
    product_id = fields.Many2one('product.product', string='Product', related='lot_id.product_id')
    fabricante = fields.Many2one('res.partner', string='Fabricante')
    description_picking = fields.Text(string='Descripción')
    origin = fields.Char(string='Origen')
    qty = fields.Float(string='Cantidad')
    type = fields.Selection([('in', 'Entrada'), ('out', 'Salida')], string='Tipo')
    # Campo Studio detectado en producción. Se define como Char simple para evitar dependencia
    # dura contra x_item si esa personalización vive en otro módulo.
    x_studio_related_field_IFYW5 = fields.Char(string='New Campo relacionado', readonly=True)


class InventoryCertificateLot(models.Model):
    _name = 'inventory.certificate.lot'
    _description = 'Certificate Lots'
    _order = 'id desc'

    certificate_id = fields.Many2one('inventory.certificate', string='Certificados', ondelete='cascade')
    lot_id = fields.Many2one('stock.production.lot', string='Lote')
    product_id = fields.Many2one('product.product', string='Product', related='lot_id.product_id')
    quantity_received = fields.Float(string='Cantidad Recibida')
    quantity_done = fields.Float(string='Cantidad Entregada')
    quantity_available = fields.Float(string='Cantidad Disponible', compute='_compute_quantity_available', store=True)

    @api.depends('quantity_received', 'quantity_done')
    def _compute_quantity_available(self):
        for rec in self:
            rec.quantity_available = rec.quantity_received - rec.quantity_done

    def action_find_move_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Movimientos del lote'),
            'res_model': 'stock.move.line',
            'view_mode': 'tree,form',
            'domain': [('lot_id', '=', self.lot_id.id)] if self.lot_id else [('id', '=', 0)],
            'target': 'current',
        }
