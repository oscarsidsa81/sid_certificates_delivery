# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    certificate_id = fields.Many2one('inventory.certificate', string='Certificado', ondelete='cascade')
    certificate_ids = fields.Many2many('inventory.certificate', string='Certificados', copy=False)
    certificate_ids_name = fields.Char(string='Certificados Nombres', compute='_compute_certificate_ids_name')
    certificate_line_id = fields.Many2one('inventory.certificate.line', string='Linea Certificado')
    certificate_qty_received = fields.Float(string='Cantidad Certificados', required=True, default=0.0)
    certificate_date = fields.Datetime(string='Fecha Creación', compute='_compute_certificate_date')
    update_certificate_value = fields.Boolean(string='Update Certificate Value')

    @api.depends('certificate_id', 'certificate_ids', 'certificate_ids.name')
    def _compute_certificate_ids_name(self):
        for line in self:
            certs = line.certificate_ids
            if line.certificate_id and line.certificate_id not in certs:
                certs |= line.certificate_id
            line.certificate_ids_name = ', '.join(certs.mapped('name'))

    @api.depends('certificate_id', 'certificate_id.create_date')
    def _compute_certificate_date(self):
        for line in self:
            line.certificate_date = line.certificate_id.create_date if line.certificate_id else False

    def _is_certificate_context_line(self):
        self.ensure_one()
        picking = self.picking_id
        ptype = picking.picking_type_id if picking else self.picking_type_id
        return bool(
            picking and (
                picking.is_certificate_picking or
                picking.certificate_needed or
                picking.certificate_needed_in or
                (ptype and ptype.is_certificate_type)
            )
        )

    def _certificate_flow(self):
        self.ensure_one()
        picking = self.picking_id
        ptype = picking.picking_type_id if picking else self.picking_type_id
        if ptype and ptype.code == 'incoming':
            return 'receipt', 'in'
        return 'delivery', 'out'

    def _certificate_qty(self):
        self.ensure_one()
        return self.certificate_qty_received or self.qty_done or self.product_uom_qty or 0.0

    def _find_matching_certificates(self):
        self.ensure_one()
        Cert = self.env['inventory.certificate'].sudo()
        domain = []
        if self.lot_id:
            domain = ['|', ('lot_ids', 'in', self.lot_id.id), ('certificate_lots.lot_id', '=', self.lot_id.id)]
        elif self.product_id:
            domain = [('product_id', '=', self.product_id.id)]
        return Cert.search(domain) if domain else Cert.browse()

    def _prepare_certificate_vals(self):
        self.ensure_one()
        cert_type, _line_type = self._certificate_flow()
        qty = self._certificate_qty()
        vals = {
            'name': self.lot_id.name or self.product_id.display_name,
            'type': cert_type,
            'product_id': self.product_id.id,
            'state': 'draft',
        }
        if self.lot_id:
            vals['lot_ids'] = [(6, 0, [self.lot_id.id])]
        if cert_type == 'receipt':
            vals['quantity_received'] = qty
        return vals

    def _prepare_certificate_line_vals(self, certificate):
        self.ensure_one()
        _cert_type, line_type = self._certificate_flow()
        return {
            'certificate_id': certificate.id,
            'move_line_id': self.id,
            'picking_id': self.picking_id.id,
            'lot_id': self.lot_id.id,
            'fabricante': certificate.fabricante.id,
            'description_picking': self.description_picking,
            'origin': self.origin or self.picking_id.origin,
            'qty': self._certificate_qty(),
            'type': line_type,
        }

    def _sync_certificate_lot(self, certificate):
        self.ensure_one()
        if not self.lot_id:
            return self.env['inventory.certificate.lot'].browse()
        CertLot = self.env['inventory.certificate.lot'].sudo()
        cert_type, _line_type = self._certificate_flow()
        qty = self._certificate_qty()
        existing = CertLot.search([
            ('certificate_id', '=', certificate.id),
            ('lot_id', '=', self.lot_id.id),
        ], limit=1)
        vals = {
            'certificate_id': certificate.id,
            'lot_id': self.lot_id.id,
        }
        if cert_type == 'receipt':
            vals['quantity_received'] = qty
        else:
            vals['quantity_done'] = qty
        if existing:
            existing.write(vals)
            return existing
        return CertLot.create(vals)

    def _sync_certificate_line(self, certificate):
        self.ensure_one()
        CertLine = self.env['inventory.certificate.line'].sudo()
        existing = self.certificate_line_id or CertLine.search([
            ('certificate_id', '=', certificate.id),
            ('move_line_id', '=', self.id),
        ], limit=1)
        vals = self._prepare_certificate_line_vals(certificate)
        if existing:
            existing.write(vals)
            return existing
        return CertLine.create(vals)

    def action_assign_certificate_id(self):
        """Replacement for OV - Asigna CERT ID / OV - Asignar Certificate ID."""
        for line in self:
            certs = line.certificate_ids
            if line.certificate_id:
                certs |= line.certificate_id
            elif certs:
                line.certificate_id = certs[:1].id
            elif line.lot_id or line.product_id:
                found = line._find_matching_certificates()
                if found:
                    line.certificate_id = found[:1].id
                    certs |= found
            if certs:
                line.write({'certificate_ids': [(6, 0, certs.ids)]})
        return True

    def action_find_certificates_by_line(self):
        """Replacement for OV - Encontrar Certificados por línea."""
        for line in self:
            certs = line._find_matching_certificates()
            if certs:
                vals = {'certificate_ids': [(6, 0, certs.ids)]}
                if not line.certificate_id:
                    vals['certificate_id'] = certs[:1].id
                line.write(vals)
        return True

    def action_create_certificates_for_all(self):
        """Replacement for OV - Crear Certificados 1 para todos."""
        Cert = self.env['inventory.certificate'].sudo()
        for line in self:
            if not line.product_id:
                continue
            certificate = line.certificate_id
            if not certificate:
                certificate = Cert.create(line._prepare_certificate_vals())
            cert_line = line._sync_certificate_line(certificate)
            line._sync_certificate_lot(certificate)
            certs = line.certificate_ids | certificate
            line.write({
                'certificate_id': certificate.id,
                'certificate_ids': [(6, 0, certs.ids)],
                'certificate_line_id': cert_line.id,
                'certificate_qty_received': line._certificate_qty(),
            })
        return True

    def action_certificate_only_moves(self):
        """Replacement for OV - Certificados sólo en movimientos de certificado."""
        for line in self:
            line.update_certificate_value = line._is_certificate_context_line()
        return True

    def action_control_certificate_pdf(self):
        """Replacement for OV - Control PDF Certificados."""
        for line in self:
            if not line._is_certificate_context_line():
                continue
            certs = line.certificate_ids | line.certificate_id
            missing = certs.filtered(lambda c: not c.certificate_file and not c.message_main_attachment_id)
            if missing and hasattr(line, 'message_post'):
                line.message_post(body=_('Certificados sin PDF: %s') % ', '.join(missing.mapped('display_name')))
        return True

    def write(self, vals):
        res = super().write(vals)
        trigger_fields = {'certificate_id', 'certificate_ids', 'lot_id', 'qty_done', 'product_uom_qty', 'certificate_qty_received'}
        if trigger_fields.intersection(vals):
            # Keeps the one2many line/lot summaries aligned without throwing errors in automated flows.
            for line in self.filtered(lambda l: l.certificate_id):
                try:
                    cert_line = line._sync_certificate_line(line.certificate_id)
                    line._sync_certificate_lot(line.certificate_id)
                    if line.certificate_line_id != cert_line:
                        super(StockMoveLine, line).write({'certificate_line_id': cert_line.id})
                except Exception:
                    pass
        return res
