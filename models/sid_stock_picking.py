# -*- coding: utf-8 -*-
import io
import os
import gc
import base64
import zipfile
import tempfile
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from PyPDF2 import PdfFileWriter, PdfFileReader
from reportlab.pdfgen import canvas

_logger = logging.getLogger(__name__)

try:
    # PyPDF2 >= 2.x
    from PyPDF2.errors import PdfReadError
except Exception:
    # PyPDF2 old
    try:
        from PyPDF2.utils import PdfReadError
    except Exception:
        PdfReadError = Exception


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    certificate_needed = fields.Boolean(string='Certificado Obligatorio', default=False)
    certificate_issued = fields.Boolean(string='Certificado Emitido', default=False)
    certificate_add_watermark = fields.Boolean(string='Añadir Marca de agua?', default=True)
    document_attachment_id = fields.Many2one('ir.attachment', string='Adjunto')

    # =========================================================
    # STUBS: para que la vista valide SIEMPRE
    # =========================================================
    def action_print_merged_report(self):
        """Método requerido por la vista (button type="object")."""
        return self._action_print_merged_report_impl()

    def action_zip_certificates(self):
        """Método requerido por la vista (button type="object")."""
        return self._action_zip_certificates_impl()

    # =========================================================
    # NUEVO: encadenar partes en la misma acción
    # =========================================================
    def action_zip_certificates_all_parts(self, cert_batch_size=8, max_zip_mb=20, max_parts=500):
        """
        Encadena la generación del ZIP por PARTES dentro del mismo request:
          - Parte 1..N
          - commit tras cada parte
          - liberación agresiva de RAM (del + gc.collect)
        """
        for picking in self:
            if picking.certificate_issued:
                continue

            offset = 0
            part = 1

            while part <= max_parts:
                res = picking.with_context(
                    cert_offset=offset,
                    cert_batch_size=cert_batch_size,
                    max_zip_mb=max_zip_mb,
                    batch_part=part,
                    include_picking_pdf=True,
                    skip_bad_pdfs=True,
                )._action_zip_certificates_impl()

                if not isinstance(res, dict):
                    picking.message_post(body="Error: _action_zip_certificates_impl no devolvió dict.")
                    break

                done = bool(res.get("done"))
                next_offset = int(res.get("next_offset", offset))
                total = int(res.get("total", 0))
                certs_added = int(res.get("certs_added", 0))
                zip_size_mb = res.get("zip_size_mb")

                # Log útil para debug
                picking.message_post(
                    body=f"DEBUG: Parte {part} | offset {offset} -> {next_offset} | añadidos {certs_added} | total {total} | zip ~ {zip_size_mb} MB"
                )

                # Commit para persistir attachment + chatter
                try:
                    picking.env.cr.commit()
                except Exception:
                    pass

                # Liberación agresiva
                del res
                gc.collect()

                if done or next_offset >= total:
                    picking.message_post(
                        body=f"✅ Certificados generados en {part} parte(s). (Último ZIP ~ {zip_size_mb} MB)"
                    )
                    break

                if next_offset <= offset:
                    picking.message_post(
                        body="⚠️ Error: next_offset no avanza, se detiene para evitar bucle infinito."
                    )
                    break

                offset = next_offset
                part += 1

            if part > max_parts:
                picking.message_post(body="⚠️ Se alcanzó el máximo de partes permitidas, se detuvo el proceso.")

        return True

    # =========================================================
    # HELPERS
    # =========================================================
    @staticmethod
    def _append_pdf(reader, writer):
        for page_num in range(reader.getNumPages()):
            writer.addPage(reader.getPage(page_num))

    # =========================================================
    # WATERMARK (igual que lo tenías)
    # =========================================================
    def add_watermark(self, pdf_file, watermark_text):
        try:
            watermark = PdfFileReader(io.BytesIO(base64.b64decode(pdf_file)))
            output_pdf = PdfFileWriter()

            for page_num in range(watermark.getNumPages()):
                page = watermark.getPage(page_num)
                page_width = float(page.mediaBox.getWidth())
                page_height = float(page.mediaBox.getHeight())

                rotation = page.get('/Rotate') or 0

                watermark_text_lines = watermark_text.split("\n") if watermark_text else []
                watermark_line1 = watermark_text_lines[0] if watermark_text_lines else ""
                watermark_line2 = watermark_text_lines[1] if len(watermark_text_lines) > 1 else ""

                watermark_canvas = io.BytesIO()
                c = canvas.Canvas(watermark_canvas, pagesize=(page_width, page_height))
                c.setFont("Helvetica", 10)
                c.setFillGray(0.2)

                text_x_position = 10
                text_y_position = 20

                if rotation == 90:
                    c.translate(page_height, 0)
                    c.rotate(90)
                elif rotation == 180:
                    c.translate(page_width, page_height)
                    c.rotate(180)
                elif rotation == 270:
                    c.translate(0, page_width)
                    c.rotate(270)

                if watermark_line1:
                    c.drawString(text_x_position, text_y_position, watermark_line1)
                if watermark_line2:
                    c.drawString(text_x_position, text_y_position - 12, watermark_line2)

                c.save()

                watermark_pdf = PdfFileReader(io.BytesIO(watermark_canvas.getvalue()))
                watermark_page = watermark_pdf.getPage(0)
                page.mergePage(watermark_page)

                output_pdf.addPage(page)

            output_stream = io.BytesIO()
            output_pdf.write(output_stream)
            return output_stream.getvalue()

        except Exception as e:
            raise UserError(
                f"Ocurrió un error al intentar modificar el PDF. "
                f"Por favor, compruebe que no está dañado.\nError: {e}"
            )

    # =========================================================
    # DOCUMENTS helper (igual que lo tenías)
    # =========================================================
    def _update_or_create_document(self, attachment_id):
        values = {
            'folder_id': self.env.ref('oct_certificate_management.documents_certificate_done_folder').id,
            'partner_id': self.partner_id.id,
            'owner_id': self.create_uid.id,
        }
        Documents = self.env['documents.document'].with_context(default_type='empty').sudo()
        doc = Documents.search([('attachment_id', '=', attachment_id)], limit=1)
        if doc:
            doc.write(values)
            document = doc
        else:
            values.update({'attachment_id': attachment_id})
            document = Documents.create(values)
        return document

    # =========================================================
    # IMPLEMENTACIÓN: action_print_merged_report (TU original)
    # =========================================================
    def _action_print_merged_report_impl(self):
        self.ensure_one()

        if self.certificate_issued:
            raise UserError(_('El albarán ya tiene los certificados emitidos'))

        picking_pdf = self.env.ref('stock.action_report_delivery')._render_qweb_pdf(self.ids)[0]
        output = PdfFileWriter()
        self._append_pdf(PdfFileReader(io.BytesIO(picking_pdf)), output)

        for line in self.move_line_ids:
            origin = line.move_id._get_source_document()
            for certificate in line.with_context(active_test=False).certificate_ids:
                if certificate.certificate_file:
                    watermark_text = (
                        "SIDSA: %s  Cliente: %s N°Pedido: %s \n "
                        "Albarán: %s Item: %s Cantidad: %s Colada: %s"
                    ) % (
                        origin.name,
                        origin.partner_id.name,
                        origin.client_order_ref,
                        self.name,
                        line.move_id.item,
                        line.qty_done,
                        line.lot_id.name,
                    ) if self.certificate_add_watermark else ""

                    certificate_with_watermark = self.add_watermark(certificate.certificate_file, watermark_text)
                    self._append_pdf(PdfFileReader(io.BytesIO(certificate_with_watermark)), output)

        output_byte = io.BytesIO()
        output.write(output_byte)

        attachment = self.env['ir.attachment'].sudo().create({
            'name': "Albarán de Entrega - %s" % (self.name),
            'datas': base64.b64encode(output_byte.getvalue()),
            'res_model': 'stock.picking',
            'res_id': self.id,
            'type': 'binary',
            'url': 'url',
            'mimetype': 'application/pdf',
        })

        self._update_or_create_document(attachment.id)

        self.message_post(
            body="Albarán con certificados %s" % (attachment.name),
            attachment_ids=[attachment.id],
            author_id=self.env.user.partner_id.id
        )

        self.write({'certificate_issued': True})
        return True

    # =========================================================
    # IMPLEMENTACIÓN: action_zip_certificates (OPTIMIZADA)
    # =========================================================
    def _action_zip_certificates_impl(self):
        """
        ZIP optimizado para evitar picos de RAM (tipo 9):
        - Crea el ZIP en DISCO (tempfile), no en BytesIO
        - Soporta procesamiento por PARTES (batch) usando contexto:
            - cert_offset: índice global de certificado desde el que empezar
            - cert_batch_size: nº máximo de certificados por parte
            - max_zip_mb: tamaño máximo aproximado del ZIP por parte
            - safety_margin_mb: margen para poder cerrar el ZIP sin Errno 28
            - min_free_mb: espacio mínimo libre en /tmp para iniciar
            - batch_part: número de parte
            - include_picking_pdf: incluir el PDF del albarán (solo en parte 1)
            - skip_bad_pdfs: si True, salta PDFs corruptos y sigue
        - Mantiene watermark, documents, chatter y campos originales
        """
        self.ensure_one()

        if self.certificate_issued:
            raise UserError(_('El albarán ya tiene los certificados emitidos'))

        ctx = self.env.context

        cert_offset = int(ctx.get("cert_offset", 0))
        cert_batch_size = int(ctx.get("cert_batch_size", 20))
        max_zip_mb = float(ctx.get("max_zip_mb", 60))
        safety_margin_mb = float(ctx.get("safety_margin_mb", 10))
        min_free_mb = float(ctx.get("min_free_mb", 500))

        batch_part = int(ctx.get("batch_part", 1))
        include_picking_pdf = bool(ctx.get("include_picking_pdf", True))
        skip_bad_pdfs = bool(ctx.get("skip_bad_pdfs", True))

        # -----------------------------------------
        # GUARD: espacio libre en /tmp
        # -----------------------------------------
        try:
            stat = os.statvfs("/tmp")
            free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
        except Exception:
            free_mb = 999999

        if free_mb < min_free_mb:
            raise UserError(_(
                "No hay espacio suficiente en /tmp para generar el ZIP.\n"
                "Libre: %.2f MB | Mínimo requerido: %.2f MB\n\n"
                "Solución: reduce max_zip_mb (p.ej. 20), reduce cert_batch_size (p.ej. 10) "
                "o libera espacio en el entorno."
            ) % (free_mb, min_free_mb))

        max_zip_bytes = int(max_zip_mb * 1024 * 1024)
        safety_margin_bytes = int(safety_margin_mb * 1024 * 1024)

        # Lista plana (ligera): (line, origin, certificate)
        tasks = []
        for line in self.move_line_ids.sorted(key=lambda l: l.id):
            origin = line.move_id._get_source_document()
            certs = line.with_context(active_test=False).certificate_ids.sorted(key=lambda c: c.create_date)
            for cert in certs:
                if cert.certificate_file:
                    tasks.append((line, origin, cert))

        total = len(tasks)
        if total == 0:
            raise UserError(_("No hay certificados con archivo PDF para este albarán."))

        if cert_offset >= total:
            return {"done": True, "next_offset": cert_offset, "total": total}

        fd, tmp_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)

        certs_added = 0
        next_offset = cert_offset
        failed = []

        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zip_file:

                # PDF del albarán solo en parte 1
                if include_picking_pdf and batch_part == 1:
                    picking_pdf = self.env.ref('stock.action_report_delivery')._render_qweb_pdf(self.ids)[0]
                    zip_file.writestr("%s.pdf" % self.name.replace("/", "-"), picking_pdf)
                    del picking_pdf
                    gc.collect()

                i = cert_offset
                while i < total and certs_added < cert_batch_size:
                    line, origin, certificate = tasks[i]

                    try:
                        watermark_text = (
                            "SIDSA: %s  Cliente: %s N°Pedido: %s \n "
                            "Albarán: %s Item: %s Cantidad: %s Colada: %s"
                        ) % (
                            origin.name or "",
                            origin.partner_id.name or "",
                            origin.client_order_ref or "",
                            self.name or "",
                            line.move_id.item or "",
                            line.qty_done or 0,
                            line.lot_id.name or "",
                        ) if self.certificate_add_watermark else ""

                        if watermark_text:
                            pdf_bytes = self.add_watermark(certificate.certificate_file, watermark_text)
                        else:
                            pdf_bytes = base64.b64decode(certificate.certificate_file)

                        filename = f"{certificate.name}-{line.move_id.item}.pdf"
                        zip_file.writestr(filename, pdf_bytes)

                        del pdf_bytes
                        gc.collect()

                        certs_added += 1
                        i += 1
                        next_offset = i

                        # Control por tamaño real del ZIP con margen de seguridad
                        try:
                            zip_file.fp.flush()
                        except Exception:
                            pass

                        # Cortamos antes para dejar margen de cierre
                        if os.path.getsize(tmp_path) >= (max_zip_bytes - safety_margin_bytes):
                            break

                    except Exception as e:
                        _logger.exception(
                            "Error procesando certificado %s en picking %s",
                            certificate.name, self.name
                        )
                        failed.append(
                            f"{certificate.name} / item {line.move_id.item}: {repr(e)}"
                        )

                        if not skip_bad_pdfs:
                            raise

                        i += 1
                        next_offset = i
                        continue

            # Leer ZIP y base64
            with open(tmp_path, "rb") as f:
                zip_bin = f.read()

            zip_b64 = base64.b64encode(zip_bin)

            del zip_bin
            gc.collect()

            attach_name = "Albarán de Entrega - %s - Parte %s" % (self.name, batch_part)
            attachment = self.env['ir.attachment'].sudo().create({
                'name': attach_name,
                'datas': zip_b64,
                'res_model': 'stock.picking',
                'res_id': self.id,
                'type': 'binary',
                'url': 'url',
                'mimetype': 'application/zip',
            })

            document = self._update_or_create_document(attachment.id)
            document_url = '<a href="#" data-oe-model="%s" data-oe-id="%s">%s</a>' % (
                "documents.document", document.id, attachment.name
            )

            msg = "Albarán con certificados: %s" % (document_url)
            msg += (
                f"<br/><br/>DEBUG: offset_inicial={cert_offset} | next_offset={next_offset} | "
                f"añadidos={certs_added} | total={total} | tamañoZIP={round(os.path.getsize(tmp_path)/(1024*1024),2)}MB"
            )

            if failed:
                msg += "<br/><br/><b>Certificados fallidos (saltados):</b><br/>"
                msg += "<br/>".join(failed[:30])
                if len(failed) > 30:
                    msg += "<br/>... (%s más)" % (len(failed) - 30)

            self.message_post(
                body=msg,
                author_id=self.env.user.partner_id.id
            )

            done = next_offset >= total
            if done:
                self.write({'certificate_issued': True})

            return {
                "done": done,
                "next_offset": next_offset,
                "total": total,
                "part": batch_part,
                "certs_added": certs_added,
                "zip_size_mb": round(os.path.getsize(tmp_path) / (1024 * 1024), 2),
                "failed": len(failed),
            }

        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
