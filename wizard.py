from openerp import models, fields, api
from datetime import datetime
from pprint import pprint
import StringIO
import base64
import csv

m = {
    'aire': {
        'id': 0,
        'date': 1,
        'origin': 2,
        'destiny': 3,
        'network': 4,
        'duration': 5,
        'cost': 6
    }
}

class WizardImportCDR(models.TransientModel):
    _name = 'telephony_isp.import.cdr'
    _description = 'CDR file impport'

    @api.onchange('cdr_data')
    def cdr_data_onchange(self):
        # read rates in memory
        if not self.cdr_data or not self.supplier_id:
            return {} #TODO: add message

        rates = dict((i.prefix, i) for i in self.env['telephony_isp.rate'].search([['supplier_id', '=', self.supplier_id.id]]))

        def get_rate(number):
            """get rate searching in prefixes"""
            last = None
            for i in xrange(len(number) + 1, 0, -1):
                if rates.has_key(number[:i]):
                    last = rates[number[:i]]
                    break

            if not last:
                print 'ERROR:', number
            #    last = 0
            return last

        contracts = {}
        if self.cdr_data:
            f = StringIO.StringIO(base64.decodestring(self.cdr_data))
            reader = csv.reader(f, delimiter=';')
            next(reader, None)  # skip header
            #c = 0
            for row in reader:
                origin = row[m[self.cdr_type]['origin']].replace('->', '')
                destiny = row[m[self.cdr_type]['destiny']]
                duration = float(row[m[self.cdr_type]['duration']])
                data = {
                    'time': datetime.strptime(row[m[self.cdr_type]['date']], '%d/%m/%y %H:%M:%S'),
                    'origin': origin, # TODO: check ->
                    'destiny': destiny,
                    'duration': duration,
                    'cost': float(row[m[self.cdr_type]['cost']]),
                }

                # don't repeat searches with contracts
                if contracts.has_key(data['origin']) and contracts[data['origin']]:
                    data['contract_id'] = contracts[data['origin']]
                    data['status'] = 'draft'
                elif not contracts.has_key(data['origin']):
                    contract = self.env['account.analytic.invoice.line'].search([['name', '=', data['origin']]])
                    if len(contract) == 1 :
                        contracts[data['origin']] = contract[0].analytic_account_id.id
                        data['contract_id'] = contract[0].analytic_account_id.id
                        data['status'] = 'draft'
                    else:
                        contracts[data['origin']] = None
                        data['status'] = 'error'
                else:
                    data['status'] = 'error'

                rate = get_rate(destiny)
                if rate:
                    data['final_price'] = rate.price / 60. * duration
                    data['rate_id'] = rate.id
                    if data['final_price'] == 0:
                        data['status'] = 'free'
                else:
                    data['final_price'] = 0
                    data['status'] = 'error'

                # don't repeat searchs with rates

                call_detail = self.env['telephony_isp.call_detail']
                call_detail.create(data)

        return {'type': 'ir.actions.act_window_close'}

    supplier_id = fields.Many2one('telephony_isp.supplier')
    cdr_type = fields.Selection([('aire', 'Aire Networks')], string='CDR type', default='aire', required=True)
    cdr_data = fields.Binary('File')

class WizardImportRate(models.TransientModel):
    _name = 'telephony_isp.import.rate'
    _description = 'Rate file impport'

    @api.onchange('rate_data')
    def _onchange_rate_data(self):
        if self.rate_data and self.supplier_id:
            f = StringIO.StringIO(base64.decodestring(self.rate_data))
            dialect = csv.Sniffer().sniff(f.read(1024))
            f.seek(0)
            reader = csv.reader(f, dialect)
            #reader = csv.reader(f, delimiter=',')
            next(reader, None)  # skip header
            for row in reader:
                rate = self.env['telephony_isp.rate']
                if not rate.search((['prefix', '=', row[0]], ['supplier_id', '=', self.supplier_id.id])):
                    data = {
                        'prefix': row[0],
                        'name': row[1],
                        'price': float(row[3]),
                        'supplier_id': self.supplier_id.id
                    }
                    rate.create(data)

            #return {
            #    'type': 'ir.actions.client',
            #    'tag': 'reload',
            #}
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'telephony_isp.supplier',
                'view_type': 'tree',
                'view_mode': 'tree',
            }

    supplier_id = fields.Many2one('telephony_isp.supplier', required=True)
    rate_data = fields.Binary('File')
