# SID Inventory Certificates

Módulo de consolidación de las personalizaciones de certificados detectadas en producción.

## Alcance cubierto

- Modelos: `inventory.certificate`, `inventory.certificate.line`, `inventory.certificate.lot`.
- Wizards: `certificate.request_wizard`, `certificate.import.wizard`, `certificate.reception.request_wizard`.
- Campos en `stock.move.line`: `certificate_id`, `certificate_ids`, `certificate_ids_name`, `certificate_line_id`, `certificate_qty_received`, `certificate_date`, `update_certificate_value`.
- Campos en `stock.picking`: `certificate_needed`, `certificate_needed_in`, `certificate_issued`, `certificate_add_watermark`, `certificate_count`, `is_certificate_picking`.
- Campo en `stock.picking.type`: `is_certificate_type`.
- Campos en `stock.production.lot`: `certificate_ids`, `certificate_quantity_ids`.
- Campo en `stock.picking.batch`: `certificate_add_watermark`.
- Acciones de servidor migradas a métodos Python para asignar certificados, crear certificados, buscar certificados por línea, controlar PDFs y crear documentos.

## Pendiente de verificar contra producción

Para una migración 100% fiel hay que comparar el código original de `ir.actions.server`, `base.automation`, vistas completas, menús, reports y nombres reales de tablas many2many. Se incluye `scripts/extract_certificate_customizations.py` para ejecutarlo en `odoo shell`.

## Instalación segura recomendada

1. Ejecutar el extractor en staging/producción y guardar el resultado.
2. Instalar este módulo en staging sobre copia reciente.
3. Comparar `04_server_actions.json` y `05_automations.json` contra los métodos Python de `models/stock_move_line.py` y `models/inventory_certificate.py`.
4. Solo después de validar, desactivar Studio/server actions originales para evitar doble ejecución.

No se exportan registros históricos de `inventory.certificate`; se conserva la estructura para que los registros existentes sigan vivos en la base.
