from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.tools import pycompat, DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError

import io
import base64
import csv
import sys

# TODO: explain this
m = {
    'aire': {
        'id': 0,
        'date': 1,
        'origin': 2,
        'destiny': 3,
        'network': 4,
        'duration': 5,
        'cost': 6
    },
    'telcia': {
        'id': 0,
        'date': 1,
        'origin': 2,
        'destiny': 3,
        'network': 4,
        'duration': 5,
        'cost': 6
    },
    'misc': {
        'id': 1,
        'date': 0,
        'origin': 3,
        'destiny': 4,
        'duration': 2,
        'cost': None
    },
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
        rates_spain = dict((i.prefix, i) for i in self.env['telephony_isp.rate'].search([['supplier_id', '=', self.supplier_id.id],['name', 'ilike', 'spain']]))
        def get_rate(number):
            """get rate searching in prefixes"""
            last = None
            for i in range(len(number) + 1, 0, -1):
                if number[:i] in rates:
                    last = rates[number[:i]]
                    break

            if not last:
                print ('ERROR:', number)
            #    last = 0
            return last

        def get_rate_without_cc(number):
            """get rate searching in prefixes without Country Code"""
            last = None
            if len(number) == 9 and number[0] in ['9','8','6']:
                #do stuff
                for i in range(len(number) + 1, 0, -1):
                    if number[:i] in rates_spain:
                        last = rates_spain[number[:i]]
                        break
                if not last:
                    print ('ERROR:', number)
                return last
            else:
                return get_rate(number)

        contracts = {}
        if self.cdr_data:
            if self.cdr_type == 'aire':
                f = io.BytesIO(base64.decodestring(self.cdr_data))
                reader = pycompat.csv_reader(f, delimiter=';')
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
                    if data['origin'] in contracts and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not data['origin'] in contracts:
                        # search numbers related to pool_number
                        #contract_line = self.env['account.analytic.invoice.line'].search([['name', '=', data['origin']]])
                        # contract_number = self.env['account.analytic.account.number'].search([['name', '=', data['origin']]])
                        # if len(contract_number) == 1 :
                        #     contracts[data['origin']] = contract_number[0].contract_line_id.analytic_account_id.id
                        #     data['contract_line_id'] = contract_number[0].contract_line_id.analytic_account_id.id
                        #     data['status'] = 'draft'
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
                    # apply rates or default
                    if rate:
                        if rate.special:
                            data['amount'] = data['cost'] + data['cost'] * rate.ratio / 100.
                        else:
                            data['amount'] = rate.price / 60. * duration # seconds -> minute
                            data['rate_id'] = rate.id
                            if data['amount'] == 0:
                                data['status'] = 'free'
                    else:
                        data['amount'] = data['cost'] + data['cost'] * self.supplier_id.ratio / 100.
                        data['status'] = 'default'

                    # don't repeat searchs with rates
                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

            elif self.cdr_type == 'telcia':
                f = io.BytesIO(base64.decodestring(self.cdr_data))
                reader = pycompat.csv_reader(f, delimiter=';')
                next(reader, None)  # skip header
                #c = 0
                for row in reader:
                    origin = row[m[self.cdr_type]['origin']].replace('->', '')
                    destiny = row[m[self.cdr_type]['destiny']]
                    duration = float(row[m[self.cdr_type]['duration']])
                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%Y-%m-%d %H:%M:%S'),
                        'origin': origin, # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'cost': float(row[m[self.cdr_type]['cost']]),
                    }

                    # don't repeat searches with contracts
                    if data['origin'] in contracts and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not data['origin'] in contracts:
                        # search numbers related to pool_number
                        #contract_line = self.env['account.analytic.invoice.line'].search([['name', '=', data['origin']]])
                        # contract_number = self.env['account.analytic.account.number'].search([['name', '=', data['origin']]])
                        # if len(contract_number) == 1 :
                        #     contracts[data['origin']] = contract_number[0].contract_line_id.analytic_account_id.id
                        #     data['contract_line_id'] = contract_number[0].contract_line_id.analytic_account_id.id
                        #     data['status'] = 'draft'
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
                    # apply rates or default
                    if rate:
                        if rate.special:
                            data['amount'] = data['cost'] + data['cost'] * rate.ratio / 100.
                        else:
                            data['amount'] = rate.price / 60. * duration # seconds -> minute
                            data['rate_id'] = rate.id
                            if data['amount'] == 0:
                                data['status'] = 'free'
                    else:
                        data['amount'] = data['cost'] + data['cost'] * self.supplier_id.ratio / 100.
                        data['status'] = 'default'

                    # don't repeat searchs with rates

                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)
            elif self.cdr_type == 'misc':
                # print (self.cdr_data)
                f = io.BytesIO(base64.decodestring(self.cdr_data))
                # print (f)
                reader = pycompat.csv_reader(f, delimiter='\x09')
                next(reader, None)  # skip header
                # c = 1
                for row in reader:
                    # print c, row
                    # c +=1
                    origin = row[m[self.cdr_type]['origin']]
                    destiny = str(row[m[self.cdr_type]['destiny']])
                    duration = float(row[m[self.cdr_type]['duration']])
                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%d/%m/%Y %H:%M:%S'),
                        'origin': origin, # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                    }

                    # don't repeat searches with contracts
                    if data['origin'] in contracts:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not data['origin'] in contracts:
                        # search numbers related to pool_number
                        number = self.env['telephony_isp.pool.number'].search([['name', '=', data['origin']]])
                        if number:
                            contract_number = self.env['account.analytic.account.number'].search([['number_id', '=', number[0].id]])
                            if len(contract_number) == 1 :
                                contracts[data['origin']] = contract_number[0].contract_line_id.id
                                data['contract_line_id'] = contract_number[0].contract_line_id.id
                                data['status'] = 'draft'
                            else:
                                data['status'] = 'error'
                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'
                        print ('ERRRORRRRRRR')


                    if destiny.startswith('00'):
                        rate = get_rate_without_cc(destiny[2:])
                    else:
                        rate = get_rate_without_cc(destiny)
                    # apply rates or default
                    if rate:
                        if rate.special:
                            #not implemented
                            continue
                            # data['amount'] = data['cost'] + data['cost'] * rate.ratio / 100.
                        else:
                            data['amount'] = rate.price * duration
                            data['cost'] = data['amount']
                            data['rate_id'] = rate.id
                            if data['amount'] == 0:
                                data['status'] = 'free'
                    else:
                        data['status'] = 'error'
                        # data['amount'] = data['cost'] + data['cost'] * self.supplier_id.ratio / 100.
                        # data['status'] = 'default'

                    # print data
                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

        return {'type': 'ir.actions.act_window_close'}

    supplier_id = fields.Many2one('telephony_isp.supplier')
    cdr_type = fields.Selection([('aire', 'Aire Networks'),('telcia', 'Telcia'),('misc', 'Misc')], string='CDR type', default='aire', required=True)
    cdr_data = fields.Binary('File')

class WizardImportCDRWithoutSupplier(models.TransientModel):
    _name = 'telephony_isp.import.cdr.ws'
    _description = 'CDR file impport with supplier'

    #@api.onchange('cdr_data')
    @api.multi
    def import_cdr_ws(self):
        # read rates in memory
        if not self.cdr_data:
            return {} #TODO: add message

        suppliers = self.env['telephony_isp.supplier'].search([])
        rates_by_supplier = {}
        rates_spain_by_supplier = {}
        for i in suppliers:
            rates_by_supplier[i.id] = dict((i.prefix, i) for i in self.env['telephony_isp.rate'].search([['supplier_id', '=', i.id]]))
            rates_spain_by_supplier[i.id] = dict((i.prefix, i) for i in self.env['telephony_isp.rate'].search([['supplier_id', '=', i.id],['name', 'ilike', 'spain']])) 
        # rates = dict((i.prefix, i) for i in self.env['telephony_isp.rate'].search([['supplier_id', '=', self.supplier_id.id]]))
        # rates_spain = dict((i.prefix, i) for i in self.env['telephony_isp.rate'].search([['supplier_id', '=', self.supplier_id.id],['name', 'ilike', 'spain']]))
        
        def get_rate(number, supplier_id):
            """get rate searching in prefixes"""
            last = None
            for i in range(len(number) + 1, 0, -1):
                if number[:i] in rates_by_supplier[supplier_id]:
                    last = rates_by_supplier[supplier_id][number[:i]]
                    break

            if not last:
                print ('ERROR:', number)
            #    last = 0
            return last

        def get_rate_without_cc(number, supplier_id):
            """get rate searching in prefixes without Country Code"""
            last = None
            if len(number) == 9 and number[0] in ['9','8','6']:
                #do stuff
                for i in range(len(number) + 1, 0, -1):
                    if number[:i] in rates_spain_by_supplier[supplier_id]:
                        last = rates_spain_by_supplier[supplier_id][number[:i]]
                        break
                if not last:
                    print ('ERROR:', number)
                return last
            else:
                return get_rate(number, supplier_id)

        contracts = {}
        if self.cdr_data:
            if self.cdr_type == 'misc':
                # print (self.cdr_data)
                f = io.BytesIO(base64.decodestring(self.cdr_data))
                # print (f)
                reader = pycompat.csv_reader(f, delimiter='\x09')
                next(reader, None)  # skip header
                # c = 1
                for row in reader:
                    # print c, row
                    # c +=1
                    origin = row[m[self.cdr_type]['origin']]
                    destiny = str(row[m[self.cdr_type]['destiny']])
                    duration = float(row[m[self.cdr_type]['duration']])
                    supplier = self.env['telephony_isp.pool.number'].search([('name', '=', origin)])
                    supplier_id = False
                    if supplier:
                        supplier_id = supplier[0].pool_id.supplier_id.id
                    data = {
                        'supplier_id': supplier_id,
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%d/%m/%Y %H:%M:%S'),
                        'origin': origin, # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                    }

                    # don't repeat searches with contracts
                    if data['origin'] in contracts:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not data['origin'] in contracts:
                        # search numbers related to pool_number
                        number = self.env['telephony_isp.pool.number'].search([['name', '=', data['origin']]])
                        if number:
                            contract_number = self.env['account.analytic.account.number'].search([['number_id', '=', number[0].id]])
                            if len(contract_number) == 1 :
                                contracts[data['origin']] = contract_number[0].contract_line_id.id
                                data['contract_line_id'] = contract_number[0].contract_line_id.id
                                data['status'] = 'draft'
                            else:
                                data['status'] = 'error'
                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'
                        print ('ERRRORRRRRRR')

                    if supplier_id:
                        if destiny.startswith('00'):
                            rate = get_rate_without_cc(destiny[2:], supplier_id)
                        else:
                            rate = get_rate_without_cc(destiny, supplier_id)
                        # apply rates or default
                        if rate:
                            if rate.special:
                                #not implemented
                                continue
                                # data['amount'] = data['cost'] + data['cost'] * rate.ratio / 100.
                            else:
                                data['amount'] = rate.price * duration
                                data['cost'] = data['amount']
                                data['rate_id'] = rate.id
                                if data['amount'] == 0:
                                    data['status'] = 'free'
                        else:
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'
                        # data['amount'] = data['cost'] + data['cost'] * self.supplier_id.ratio / 100.
                        # data['status'] = 'default'

                    # print data
                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

        return {'type': 'ir.actions.act_window_close'}

    cdr_type = fields.Selection([('misc', 'Misc')], string='CDR type', default='misc', required=True)
    cdr_data = fields.Binary('File')

class WizardImportRate(models.TransientModel):
    _name = 'telephony_isp.import.rate'
    _description = 'Rate file impport'

    #@api.onchange('rate_data')
    @api.multi
    def import_rate(self):
        if self.rate_data and self.supplier_id:
            f = io.BytesIO(base64.decodestring(self.rate_data))
            reader = pycompat.csv_reader(f, delimiter=',')
            #reader = csv.reader(f, delimiter=',')
            # next(reader, None)  # skip header
            for row in reader:
                rate = self.env['telephony_isp.rate']
                if not rate.search((['prefix', '=', row[0]], ['supplier_id', '=', self.supplier_id.id])):
                    data = {
                        'prefix': row[0],
                        'name': row[1],
                        'cost': float(row[2]),
                        'price': float(row[3]),
                        'supplier_id': self.supplier_id.id
                    }
                    rate.create(data)

            #return {
            #    'type': 'ir.actions.client',
            #    'tag': 'reload',
            #}
            return 

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
            minutes[j.segment] = float(j.minutes_free)

        return minutes # could be {}

    def get_amount_status(self, call):
        # check for free calls
        call_origin = self.contracts[call.contract.id]['origins'][call.origin]

        if call.rate_id.segment and call.rate_id.segment in call_origin['minutes']:
            self.contracts[call.contract.id]['origins'][call.origin]['minutes'][call.rate_id.segment] -= call.duration / 60.
            d = call_origin['minutes'][call.rate_id.segment]
            if d > 0:
                amount = 0
                status = 'free'
            elif d > call.duration:
                amount = call.amount / call.duration * abs(d)
                status = 'special'
            else:
                amount = call.amount
                status = 'invoiced'
        else:
            amount = call.amount
            status = 'invoiced'

        call_origin['calls'].append(call)
        call_origin['status'].append(status)
        call_origin['total'] += amount


    @api.multi
    def create_invoice(self):
        # search records
        # TODO: get a better way to recalc invoices
        if self.partner_id and self.recalc:
            call_details = self.env['telephony_isp.call_detail'].search([
                ('partner.id', '=', self.partner_id.id),
                ('status', '!=', 'error'),
                ('time', '>=',  self.date_start),
                ('time', '<', (datetime.strptime(self.date_end, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=1)).strftime(DEFAULT_SERVER_DATE_FORMAT))
            ], order='time')
        elif self.partner_id:
            call_details = self.env['telephony_isp.call_detail'].search([
                ('partner.id', '=', self.partner_id.id),
                ('status', '=', 'draft'),
                ('time', '>=',  self.date_start),
                ('time', '<', (datetime.strptime(self.date_end, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=1)).strftime(DEFAULT_SERVER_DATE_FORMAT))
            ], order='time')
        else:
            call_details = self.env['telephony_isp.call_detail'].search([
                ('status', '=', 'draft'),
                ('time', '>=',  self.date_start),
                ('time', '<', (datetime.strptime(self.date_end, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=1)).strftime(DEFAULT_SERVER_DATE_FORMAT))
            ], order='time')
        # create period
        data = {
            'date_start': self.date_start,
            'date_end': self.date_end,
        }

        # create new period to group invoices
        period = self.env['telephony_isp.period'].create(data)

        # group by contract
        self.contracts = {}
        for i in call_details:
            # contracts
            if not i.contract.id in self.contracts:
                # first origin
                self.contracts[i.contract.id] = {
                    'contract': i.contract,
                    'origins': {
                        i.origin: {
                            'product': i.product,
                            'calls': [],
                            'status': [],
                            'total': 0,
                            'minutes': self.get_minutes_free(i.origin, i.contract_line_id.product_id.id)
                        }
                    }
                }

                self.get_amount_status(i)

            elif i.origin in self.contracts[i.contract.id]['origins']:
                self.get_amount_status(i)
            else:
                # TODO: KISS (refactor this!)
                # new origin
                self.contracts[i.contract.id]['origins'][i.origin] = {
                    'product': i.product,
                    'calls': [],
                    'status': [],
                    'total': 0,
                    'minutes': self.get_minutes_free(i.origin, i.contract_line_id.product_id.id)
                }

                self.get_amount_status(i)

        # create invoices with lines
        invoices = []
        amount = 0
        for i in self.contracts.values():
            # invoice lines
            # print (i)
            lines = []
            for j in i['origins']:
                #default_product = i['origins'][j]['calls'][0]['supplier_id'].product_id
                product = i['origins'][j]['product']
                lines.append((0,0, {
                    'product_id': product.id,
                    'name': _('Consum of %s') % j,
                    'account_id': product.property_account_income_id.id or product.categ_id.property_account_income_categ_id.id,
                    'account_analytic_id': i['contract'].id,
                    'invoice_line_tax_ids': [(6,0, [k.id for k in product.taxes_id])],
                    'price_unit': i['origins'][j]['total']
                }))

            # data for invoice
            data =  {
                'is_telephony': True,
                'origin': i['contract'].code,
                'date_invoice': self.date_invoice,
                'partner_id': i['contract'].partner_id.id,
                'journal_id': self.journal_id.id,
                'telephony_period_id': period.id,
                'account_id': i['contract'].partner_id.property_account_receivable_id.id,
                'invoice_line_ids': lines
            }
            if hasattr(i['contract'], 'payment_mode'):
                data['payment_mode'] = i['contract'].payment_mode.id,

            # recover or create invoice to add lines
            if data['partner_id']:
                # first of all, search for draft invoices for this partner and contract
                invoice_obj = self.env['account.invoice'].search([
                    ('state', '=', 'draft'),
                    ('partner_id', '=', data['partner_id']),
                    ('origin', '=', data['origin'])
                ])
                if len(invoice_obj) == 1 and self.existing_invoice:
                    invoice = invoice_obj[0]
                    data = {
                        'is_telephony': True,
                        'telephony_period_id': period.id,
                        'invoice_line_ids': lines
                    }
                    invoice.write(data)
                elif len(invoice_obj) == 0 or not self.existing_invoice:
                    invoice = self.env['account.invoice'].create(data)
                else:
                    raise ValidationError('Error processing contract for %s. Many draft invoices.' % ', '.join(i['origins'].keys()))
            else:
                raise ValidationError('Error processing contract for %s' % ', '.join(i['origins'].keys()))

            amount += i['origins'][j]['total']

            # link calls with its invoice and set new status
            for k in range(len(i['origins'][j]['calls'])):
                call = i['origins'][j]['calls'][k]
                status = i['origins'][j]['status'][k]
                data = {
                    'invoice_id': invoice.id,
                    'status': status
                }
                # check free calls
                if 'free' in status:
                    data['amount'] = 0
                call.write(data)
                #print(lines)
                #print(invoice)
                #print(invoice.invoice_line_ids)

                # recalc taxes
                # invoice.button_reset_taxes()

                # append invoice to period
                invoices.append(invoice)

        # update period data
        data = {
            'invoice_ids': [(6,0, [k.id for k in invoices])],
            'call_details_ids': [(6,0, [k.id for k in call_details])],
            'amount': amount
        }
        # stop()
        period.write(data)

    journal_id = fields.Many2one('account.journal', 'Journal', required=True)
    partner_id = fields.Many2one('res.partner')
    date_invoice = fields.Date('Date invoice', required=True)
    date_start= fields.Date('From', required=True)
    date_end = fields.Date('To', required=True)
    recalc = fields.Boolean(help='Override previus calcs in calls') # override invoiced status
    existing_invoice = fields.Boolean('Add to existing invoices') 
