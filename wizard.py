from openerp import models, fields, api
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
import StringIO
import base64
import csv
import sys

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

    #@api.onchange('cdr_data')
    @api.multi
    def import_cdr(self):
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
                    'supplier_id': self.supplier_id.id,
                    'time': datetime.strptime(row[m[self.cdr_type]['date']], '%d/%m/%y %H:%M:%S'),
                    'origin': origin, # TODO: check ->
                    'destiny': destiny,
                    'duration': duration,
                    'cost': float(row[m[self.cdr_type]['cost']]),
                }

                # don't repeat searches with contracts
                if contracts.has_key(data['origin']) and contracts[data['origin']]:
                    data['contract_line_id'] = contracts[data['origin']]
                    data['status'] = 'draft'
                elif not contracts.has_key(data['origin']):
                    contract_line = self.env['account.analytic.invoice.line'].search([['name', '=', data['origin']]])
                    if len(contract_line) == 1 :
                        contracts[data['origin']] = contract_line[0].id
                        data['contract_line_id'] = contract_line[0].id
                        data['status'] = 'draft'
                    else:
                        contracts[data['origin']] = None
                        data['status'] = 'error'
                else:
                    data['status'] = 'error'

                rate = get_rate(destiny)
                if rate:
                    data['amount'] = rate.price / 60. * duration # seconds -> minute
                    data['rate_id'] = rate.id
                    if data['amount'] == 0:
                        data['status'] = 'free'
                else:
                    data['amount'] = 0
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

    #@api.onchange('rate_data')
    @api.multi
    def import_rate(self):
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

class WizardCreateInvoices(models.TransientModel):
    _name = 'telephony_isp.create.invoice'
    _description = 'Create invoice from call detail'

    def get_minutes_free(self, origin, product_id):
        """get telephony data from products"""
        product_telephony = self.env['product.product'].search([('id', '=', product_id)])
        minutes = {}
        #print '>>>', product_telephony, product_telephony.telephony_ids
        for j in product_telephony.telephony_ids:
            minutes[origin][j.segment] = float(j.minutes_free)

        return minutes # could be {}

    @api.multi
    def create_invoice(self):
        # search records
        call_details = self.env['telephony_isp.call_detail'].search([
            ('status', 'in', ['draft', 'invoiced', 'free']),
            ('time', '>=',  self.date_start),
            ('time', '<', (datetime.strptime(self.date_end, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=1)).strftime(DEFAULT_SERVER_DATE_FORMAT))
        ], order='time')

        # group by contract
        contracts = {}
        for i in call_details:
            # contracts
            if not contracts.has_key(i.contract.id):
                # first origin
                contracts[i.contract.id] = {
                    'contract': i.contract,
                    'origins': {
                        i.origin: {
                            'product': i.product,
                            'calls': [i],
                            'minutes': self.get_minutes_free(i.origin, i.product.id)
                        }
                    }
                }

                # check for free calls
                if i.rate_id.segment and contracts[i.contract.id]['origins'][i.origin]['minutes'].has_key(i.rate_id.segment):
                    contracts[i.contract.id]['origins'][i.origin]['minutes'][i.segment] -= i.duration / 60.
                    d = contracts[i.contract.id]['origins'][i.origin]['minutes'][i.segment]
                    if d > 0:
                        amount = 0
                    elif d > i.duration:
                        amount = i.amount / i.duration * abs(d)
                    else:
                        amount = i.amount
                else:
                    amount = i.amount
                contracts[i.contract.id]['origins'][i.origin]['total'] = amount

            elif contracts[i.contract.id]['origins'].has_key(i.origin):
                contracts[i.contract.id]['origins'][i.origin]['calls'].append(i)
                contracts[i.contract.id]['origins'][i.origin]['total'] += i.amount
            else:
                # TODO: KISS (refactor this!)
                # new origin
                contracts[i.contract.id]['origins'][i.origin] = {
                    'calls': [i],
                    'minutes': self.get_minutes_free(i.origin, i.product.id)
                }

                # check for free calls
                if i.rate_id.segment and contracts[i.contract.id]['origins'][i.origin]['minutes'].has_key(i.rate_id.segment):
                    contracts[i.contract.id]['origins'][i.origin]['minutes'][i.segment] -= i.duration / 60.
                    d = contracts[i.contract.id]['origins'][i.origin]['minutes'][i.segment]
                    if d > 0:
                        amount = 0
                    elif d > i.duration:
                        amount = i.amount / i.duration * abs(d)
                    else:
                        amount = i.amount
                else:
                    amount = i.amount
                contracts[i.contract.id]['origins'][i.origin]['total'] = amount

        # create invoices with lines
        print len(call_details)
        invoices = []
        amount = 0
        for i in contracts.values():
            # invoice lines
            lines = []
            for j in i['origins']:
                product = i['origins'][j]['calls'][0]['supplier_id'].product_id
                lines.append((0,0, {
                    'product_id': product.id,
                    'name': 'Consumo de %s' % j,
                    'account_id': product.property_account_income.id,
                    'account_analytic_id': i['contract'].id,
                    'invoice_line_tax_id': [(6,0, [k.id for k in product.taxes_id])],
                    'price_unit': i['origins'][j]['total']
                }))
                amount += i['origins'][j]['total']

                # invoice
                data =  {
                    'is_telephony': True,
                    'date_invoice': self.date_invoice,
                    'partner_id': i['contract'].partner_id.id,
                    'journal_id': self.journal_id.id,
                    'account_id': i['contract'].partner_id.property_account_receivable.id,
                    'payment_mode_id': i['contract'].payment_mode.id,
                    'invoice_line': lines
                }

                invoice = self.env['account.invoice'].create(data)

                # link calls with its invoice
                for k in i['origins'][j]['calls']:
                    k.write({'invoice_id': invoice.id})

                # recalc taxes
                invoice.button_reset_taxes()

                # append invoice to period
                invoices.append(invoice)

        data = {
            'date_start': self.date_start,
            'date_end': self.date_end,
            'invoice_ids': [(6,0, [k.id for k in invoices])],
            'call_details_ids': [(6,0, [k.id for k in call_details])],
            'amount': amount
        }
        print data
        self.env['telephony_isp.period'].create(data)

    journal_id = fields.Many2one('account.journal', 'Journal', required=True)
    date_invoice = fields.Date('Date invoice', required=True)
    date_start= fields.Date('From', required=True)
    date_end = fields.Date('To', required=True)
