# Ejecutar dentro de odoo shell en producción/staging:
# exec(open('/tmp/extract_certificate_customizations.py').read())
import json
import os
from datetime import datetime

OUT = f"/tmp/certificados_inventory_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
os.makedirs(OUT, exist_ok=True)

def write(name, data):
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8') as f:
        if isinstance(data, (dict, list)):
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        else:
            f.write(str(data))
    return path

MODELS = [
    'inventory.certificate', 'inventory.certificate.line', 'inventory.certificate.lot',
    'certificate.request_wizard', 'certificate.import.wizard', 'certificate.reception.request_wizard',
    'stock.move.line', 'stock.picking', 'stock.picking.type', 'stock.production.lot', 'stock.picking.batch',
]
TOKENS = ['certificate', 'certificado', 'inventory.certificate']

# Modelos y campos completos
models = env['ir.model'].sudo().search(['|', ('model', 'in', MODELS), ('model', 'ilike', 'certificate')])
write('01_models.json', [{
    'id': m.id, 'model': m.model, 'name': m.name, 'state': m.state,
} for m in models])

fields = env['ir.model.fields'].sudo().search([
    '|', '|', '|', '|',
    ('model', 'in', MODELS),
    ('relation', 'in', ['inventory.certificate', 'inventory.certificate.line', 'inventory.certificate.lot']),
    ('name', 'ilike', 'certificate'),
    ('field_description', 'ilike', 'certificado'),
    ('field_description', 'ilike', 'certificate'),
])
write('02_fields.json', [{
    'id': f.id, 'model': f.model, 'name': f.name, 'field_description': f.field_description,
    'ttype': f.ttype, 'relation': f.relation, 'relation_field': f.relation_field,
    'required': f.required, 'readonly': f.readonly, 'store': f.store, 'index': f.index,
    'copied': f.copied, 'compute': f.compute, 'depends': f.depends,
    'related': f.related, 'domain': f.domain, 'on_delete': f.on_delete,
    'state': f.state,
} for f in fields])

# Vistas con arquitectura completa
views = env['ir.ui.view'].sudo().search([
    '|', '|', '|', '|', '|',
    ('model', 'in', MODELS),
    ('name', 'ilike', 'certificate'),
    ('name', 'ilike', 'certificado'),
    ('arch_db', 'ilike', 'inventory.certificate'),
    ('arch_db', 'ilike', 'certificate_'),
    ('arch_db', 'ilike', 'certificado'),
])
write('03_views.json', [{
    'id': v.id, 'name': v.name, 'model': v.model, 'type': v.type,
    'inherit_id': v.inherit_id.id if v.inherit_id else False,
    'inherit_xml_id': v.inherit_id.get_external_id().get(v.inherit_id.id) if v.inherit_id else False,
    'xml_id': v.get_external_id().get(v.id),
    'arch_db': v.arch_db,
} for v in views])

# Acciones de servidor completas
acts = env['ir.actions.server'].sudo().search([
    '|', '|', '|', '|',
    ('model_name', 'in', MODELS),
    ('name', 'ilike', 'certificate'),
    ('name', 'ilike', 'certificado'),
    ('code', 'ilike', 'certificate'),
    ('code', 'ilike', 'certificado'),
])
write('04_server_actions.json', [{
    'id': a.id, 'name': a.name, 'model_name': a.model_name, 'state': a.state,
    'usage': a.usage, 'binding_model': a.binding_model_id.model if a.binding_model_id else False,
    'binding_type': a.binding_type, 'code': a.code,
} for a in acts])

# Automatizaciones completas
Auto = env['base.automation'].sudo()
autos = Auto.search([
    '|', '|', '|', '|', '|',
    ('model_name', 'in', MODELS),
    ('name', 'ilike', 'certificate'),
    ('name', 'ilike', 'certificado'),
    ('filter_domain', 'ilike', 'certificate'),
    ('filter_pre_domain', 'ilike', 'certificate'),
    ('filter_domain', 'ilike', 'certificado'),
])
write('05_automations.json', [{
    'id': a.id, 'name': a.name, 'model_name': a.model_name, 'active': a.active,
    'trigger': getattr(a, 'trigger', False),
    'trigger_field_ids': getattr(a, 'trigger_field_ids', env['ir.model.fields']).mapped('name') if 'trigger_field_ids' in a._fields else [],
    'filter_domain': a.filter_domain, 'filter_pre_domain': a.filter_pre_domain,
    'action_server_id': a.action_server_id.id if a.action_server_id else False,
    'action_server_name': a.action_server_id.name if a.action_server_id else False,
    'action_server_code': a.action_server_id.code if a.action_server_id else False,
} for a in autos])

# Acciones ventana, menús, reports
win_actions = env['ir.actions.act_window'].sudo().search([
    '|', '|', '|',
    ('res_model', 'in', MODELS),
    ('name', 'ilike', 'certificate'),
    ('name', 'ilike', 'certificado'),
    ('domain', 'ilike', 'certificate'),
])
write('06_window_actions.json', [{
    'id': a.id, 'name': a.name, 'res_model': a.res_model, 'view_mode': a.view_mode,
    'domain': a.domain, 'context': a.context,
    'xml_id': a.get_external_id().get(a.id),
} for a in win_actions])

menus = env['ir.ui.menu'].sudo().search(['|', ('name', 'ilike', 'certificate'), ('name', 'ilike', 'certificado')])
write('07_menus.json', [{
    'id': m.id, 'name': m.name, 'parent_id': m.parent_id.id if m.parent_id else False,
    'parent_name': m.parent_id.complete_name if m.parent_id else False,
    'action': str(m.action) if m.action else False,
    'sequence': m.sequence,
    'xml_id': m.get_external_id().get(m.id),
} for m in menus])

reports = env['ir.actions.report'].sudo().search([
    '|', '|', '|',
    ('model', 'in', MODELS),
    ('name', 'ilike', 'certificate'),
    ('name', 'ilike', 'certificado'),
    ('report_name', 'ilike', 'certificate'),
])
write('08_reports.json', [{
    'id': r.id, 'name': r.name, 'model': r.model, 'report_type': r.report_type,
    'report_name': r.report_name, 'report_file': r.report_file,
    'print_report_name': r.print_report_name,
    'xml_id': r.get_external_id().get(r.id),
} for r in reports])

# XML IDs relevantes, sin volcar miles de certificados históricos por defecto
xmlids = env['ir.model.data'].sudo().search([
    '|', '|', '|',
    ('model', 'in', ['ir.model', 'ir.model.fields', 'ir.ui.view', 'ir.actions.server', 'ir.actions.act_window', 'ir.ui.menu', 'ir.actions.report']),
    ('name', 'ilike', 'certificate'),
    ('name', 'ilike', 'certificado'),
    ('module', 'ilike', 'certificate'),
])
write('09_xmlids_config.json', [{
    'module': x.module, 'name': x.name, 'model': x.model, 'res_id': x.res_id,
    'complete_name': f'{x.module}.{x.name}',
} for x in xmlids])

# M2M relation table names from DB catalog / ir_model_relation if available
try:
    env.cr.execute("""
        SELECT name, model, module FROM ir_model_relation
        WHERE name ILIKE '%%certificate%%' OR model IN %s
        ORDER BY name
    """, (tuple(MODELS),))
    write('10_ir_model_relation.json', [dict(zip(['name','model','module'], row)) for row in env.cr.fetchall()])
except Exception as e:
    write('10_ir_model_relation_error.txt', repr(e))

print('OK ->', OUT)
