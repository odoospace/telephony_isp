from openerp import models, fields, api
from datetime import datetime, timedelta
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.exceptions import ValidationError
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
    'carrier-enabler': {
        'id': 3,
        'date': 0,
        'origin': 2,
        'destiny': 4,
        'network': 14,
        'duration': 6,
        'cost': None
    },
    'miscellaneous': {
        'id': 2,
        'date': 0,
        'origin': 1,
        'destiny': 3,
        'network': None,
        'duration': 4,
        'cost': 5
    },
    'zargotel': {
        'id': None,
        'date': 0,
        'time': 1,
        'origin': 2,
        'destiny': 3,
        'network': None,
        'duration': 5,
        'cost': 6
    },

    'lemonvil': {
        'id': 0,
        'date': 12,
        'origin': 6,
        'destiny': 10,
        'network': 23,
        'duration': 15,
        'cost': 17,
        'otherdestiny': 20,
    },
    'ion': {
        'id': 0,
        'date': 1,
        'origin': 2,
        'destiny': 3,
        'network': 4,
        'duration': 5,
        'cost': 6
    },
    'masmovil': {
        'id': 1,
        'date': 5,
        'date2': 6,
        'origin': 2,
        'destiny': 4,
        'network': 10,
        'duration': 7,
        'cost': 11,
        'type': 0

    },
    'ptv': {
        'id': 0,
        'date': 3,
        'date2': 4,
        'origin': 5,
        'destiny': 15,
        'network': 19,
        'duration': 9,
        'cost': 14,
        'type': 10

    },
}


class WizardImportCDR(models.TransientModel):
    _name = 'telephony_isp.import.cdr'
    _description = 'CDR file impport'

    # @api.onchange('cdr_data')
    @api.multi
    def import_cdr(self):
        # read rates in memory
        if not self.cdr_data or not self.supplier_id:
            return {}  # TODO: add message

        rates = dict(
            (i.prefix, i) for i in self.env['telephony_isp.rate'].search([['supplier_id', '=', self.supplier_id.id]]))
        rates_spain = dict((i.prefix, i) for i in self.env['telephony_isp.rate'].search(
            [['supplier_id', '=', self.supplier_id.id], ['name', 'ilike', 'spain']]))

        def get_rate(number):
            """get rate searching in prefixes"""
            last = None
            for i in xrange(len(number) + 1, 0, -1):
                if rates.has_key(number[:i]):
                    last = rates[number[:i]]
                    break

            if not last:
                print
                'ERROR:', number
            #    last = 0
            return last

        def get_rate_without_cc(number):
            """get rate searching in prefixes without Country Code"""
            last = None
            if len(number) == 9 and number[0] in ['9', '8', '6']:
                # do stuff
                for i in xrange(len(number) + 1, 0, -1):
                    if rates_spain.has_key(number[:i]):
                        last = rates_spain[number[:i]]
                        break
                if not last:
                    print
                    'ERROR:', number
                return last
            else:
                return get_rate(number)

        contracts = {}
        if self.cdr_data:
            if self.cdr_type == 'aire':
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header
                # c = 0
                for row in reader:
                    origin = row[m[self.cdr_type]['origin']].replace('->', '')
                    destiny = row[m[self.cdr_type]['destiny']]
                    duration = float(row[m[self.cdr_type]['duration']])
                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%d/%m/%y %H:%M:%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'cost': float(row[m[self.cdr_type]['cost']]),
                        'company_id': self.company_id.id,
                    }

                    # don't repeat searches with contracts
                    if contracts.has_key(data['origin']) and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        # search numbers related to pool_number
                        # contract_line = self.env['account.analytic.invoice.line'].search([['name', '=', data['origin']]])
                        contract_number = self.env['account.analytic.account.number'].search(
                            [['name', '=', data['origin']]])
                        if len(contract_number) == 1:
                            contracts[data['origin']] = contract_number[0].contract_line_id.analytic_account_id.id
                            data['contract_line_id'] = contract_number[0].contract_line_id.analytic_account_id.id
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
                            data['amount'] = rate.price / 60. * duration  # seconds -> minute
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
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header
                # c = 0
                for row in reader:
                    origin = row[m[self.cdr_type]['origin']].replace('->', '')
                    destiny = row[m[self.cdr_type]['destiny']]
                    duration = float(row[m[self.cdr_type]['duration']])
                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%Y-%m-%d %H:%M:%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'cost': float(row[m[self.cdr_type]['cost']]),
                        'company_id': self.company_id.id,
                    }

                    # don't repeat searches with contracts
                    if contracts.has_key(data['origin']) and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        # search numbers related to pool_number
                        contract_line = self.env['account.analytic.invoice.line'].search(
                            [['name', '=', data['origin']]])
                        if len(contract_line) == 1:
                            contracts[data['origin']] = contract_line[0].id
                            data['contract_line_id'] = contract_line[0].id
                            data['status'] = 'draft'
                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'

                    rate = get_rate_without_cc(destiny)
                    # apply rates or default
                    if rate:
                        if rate.special:
                            data['amount'] = data['cost'] + data['cost'] * rate.ratio / 100.
                        else:
                            data['amount'] = rate.price / 60. * duration  # seconds -> minute
                            data['rate_id'] = rate.id
                            if data['amount'] == 0:
                                data['status'] = 'free'
                    else:
                        data['amount'] = data['cost'] + data['cost'] * self.supplier_id.ratio / 100.
                        data['status'] = 'default'

                    # don't repeat searchs with rates

                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

            elif self.cdr_type == 'carrier-enabler':
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
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
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%Y-%m-%d %H:%M:%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'company_id': self.company_id.id,
                    }

                    # don't repeat searches with contracts
                    if contracts.has_key(data['origin']):
                        data['contract_line_id'] = contracts[data['origin']]['contract_id']
                        data['origin'] = contracts[data['origin']]['number']
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        # search numbers related to pool_number
                        contract_number = self.env['account.analytic.account.number'].search(
                            [['login', '=', data['origin']]])
                        if len(contract_number) == 1:
                            contracts[data['origin']] = {
                                'contract_id': contract_number[0].contract_line_id.id,
                                'number': contract_number[0].number_id.name
                            }
                            data['contract_line_id'] = contract_number[0].contract_line_id.id
                            data['status'] = 'draft'
                            data['origin'] = contract_number[0].number_id.name
                        else:
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'
                        print
                        'ERRRORRRRRRR'

                    if destiny.startswith('00'):
                        rate = get_rate_without_cc(destiny[2:])
                    else:
                        rate = get_rate_without_cc(destiny)
                    # apply rates or default
                    if rate:
                        if rate.special:
                            # not implemented
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

            elif self.cdr_type == 'miscellaneous':
                # no rates, direct cost
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=',')
                next(reader, None)  # skip header
                for row in reader:
                    origin = row[m[self.cdr_type]['origin']]
                    destiny = str(row[m[self.cdr_type]['destiny']])
                    duration = float(row[m[self.cdr_type]['duration']])
                    cost = float(row[m[self.cdr_type]['cost']])
                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%Y-%m-%d %H:%M:%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'company_id': self.company_id.id,
                        'cost': cost,
                        'amount': cost
                    }

                    # don't repeat searches with contracts
                    if contracts.has_key(data['origin']) and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        # search numbers related to pool_number
                        number = self.env['telephony_isp.pool.number'].search([['name', '=', data['origin']]])
                        if number:
                            contract_number = self.env['account.analytic.account.number'].search(
                                [['number_id', '=', number[0].id]])
                            if len(contract_number) == 1:
                                contracts[data['origin']] = contract_number[0].contract_line_id.id
                                data['contract_line_id'] = contract_number[0].contract_line_id.id
                                data['status'] = 'draft'
                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'

                    # print data
                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

            elif self.cdr_type == 'zargotel':
                # no rates, direct cost
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header
                for row in reader:
                    origin = row[m[self.cdr_type]['origin']]
                    destiny = str(row[m[self.cdr_type]['destiny']])
                    duration = float(row[m[self.cdr_type]['duration']])
                    cost = float(row[m[self.cdr_type]['cost']].replace(',', '.'))
                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(
                            '%s %s' % (row[m[self.cdr_type]['date']], row[m[self.cdr_type]['time']]),
                            '%d/%m/%Y %H:%M:%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'company_id': self.company_id.id,
                        'cost': cost,
                        'amount': cost
                    }

                    # don't repeat searches with contracts
                    if contracts.has_key(data['origin']) and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        # search numbers related to pool_number
                        number = self.env['telephony_isp.pool.number'].search([['name', '=', data['origin']]])
                        if number:
                            contract_number = self.env['account.analytic.account.number'].search(
                                [['number_id', '=', number[0].id]])
                            if len(contract_number) == 1:
                                contracts[data['origin']] = contract_number[0].contract_line_id.id
                                data['contract_line_id'] = contract_number[0].contract_line_id.id
                                data['status'] = 'draft'
                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'

                    if destiny.startswith('00'):
                        rate = get_rate_without_cc(destiny[2:])
                    else:
                        rate = get_rate_without_cc(destiny)
                    # apply rates or default
                    if rate:
                        if rate.special:
                            # not implemented
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

            elif self.cdr_type == 'lemonvil':
                if not self.data_type:
                    raise ValidationError('Error! This supplier requires a data type')

                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header

                for row in reader:
                    origin = row[m[self.cdr_type]['origin']]
                    destiny = row[m[self.cdr_type]['destiny']]
                    duration = float(row[m[self.cdr_type]['duration']])
                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%Y-%m-%d %H:%M:%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'cost': float(row[m[self.cdr_type]['cost']]),
                        'data_type': self.data_type,
                        'company_id': self.company_id.id,
                    }
                    if self.data_type == 'data':
                        data['duration'] = 0
                    if self.data_type == 'other':
                        # if 'otherdestiny' in row[m[self.cdr_type]]:
                        data['destiny'] = row[m[self.cdr_type]['otherdestiny']]
                    if contracts.has_key(data['origin']) and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        contract_line = self.env['account.analytic.invoice.line'].search(
                            [['name', '=', data['origin']]])
                        if len(contract_line) == 1:
                            contracts[data['origin']] = contract_line[0].id
                            data['contract_line_id'] = contract_line[0].id
                            data['status'] = 'draft'
                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'

                    data['amount'] = data['cost']

                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

            elif self.cdr_type == 'ion':
                if not self.data_type:
                    raise ValidationError('Error! This supplier requires a data type')
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header

                for row in reader:
                    origin = row[m[self.cdr_type]['origin']]
                    destiny = row[m[self.cdr_type]['destiny']]
                    duration = float(row[m[self.cdr_type]['duration']])
                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(row[m[self.cdr_type]['date']], '%d/%m/%y %H:%M:%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'cost': float(row[m[self.cdr_type]['cost']]),
                        'data_type': self.data_type,
                        'company_id': self.company_id.id,
                    }
                    if self.data_type == 'data':
                        data['duration'] = 0
                    if contracts.has_key(data['origin']) and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        number = self.env['telephony_isp.pool.number'].search([['name', '=', data['origin']]])
                        if number:
                            contract_number = self.env['account.analytic.account.number'].search(
                                [['number_id', '=', number[0].id]])
                            if len(contract_number) == 1:
                                contracts[data['origin']] = contract_number[0].contract_line_id.id
                                data['contract_line_id'] = contract_number[0].contract_line_id.id
                                data['status'] = 'draft'
                            else:
                                contracts[data['origin']] = None
                                data['status'] = 'error'

                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'

                    data['amount'] = data['cost']

                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

            elif self.cdr_type == 'masmovil':
                # this type mixes voice,data and sms at the same cdr
                # if not self.data_type:
                #     raise ValidationError('Error! This supplier requires a data type')
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header

                for row in reader:
                    origin = row[m[self.cdr_type]['origin']]
                    destiny = row[m[self.cdr_type]['destiny']]
                    duration = float(row[m[self.cdr_type]['duration']])
                    if row[m[self.cdr_type]['type']] == 'DAT':
                        self.data_type = 'data'
                    if row[m[self.cdr_type]['type']] == 'VOZ':
                        self.data_type = 'calls'
                    if row[m[self.cdr_type]['type']] == 'SMS':
                        self.data_type = 'sms'

                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(
                            (row[m[self.cdr_type]['date']] + ' ' + row[m[self.cdr_type]['date2']]),
                            '%d-%m-%Y %H:%M:%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'cost': float(row[m[self.cdr_type]['cost']]),
                        'data_type': self.data_type,
                        'company_id': self.company_id.id,
                    }
                    if self.data_type == 'data':
                        data['duration'] = int(int(row[8]) / 1000)
                    if contracts.has_key(data['origin']) and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        number = self.env['telephony_isp.pool.number'].search([['name', '=', data['origin']]])
                        if number:
                            contract_number = self.env['account.analytic.account.number'].search(
                                [['number_id', '=', number[0].id]])
                            if len(contract_number) == 1:
                                contracts[data['origin']] = contract_number[0].contract_line_id.id
                                data['contract_line_id'] = contract_number[0].contract_line_id.id
                                data['status'] = 'draft'
                            else:
                                contracts[data['origin']] = None
                                data['status'] = 'error'

                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'

                    data['amount'] = data['cost']

                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

            elif self.cdr_type == 'ptv':
                # this type mixes voice,data and sms at the same cdr from landline and mobileline
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header

                for row in reader:

                    origin = row[m[self.cdr_type]['origin']]
                    if origin[0] == '9':
                        line_type = 'landline'
                    else:
                        line_type = 'mobileline'
                    destiny = row[m[self.cdr_type]['destiny']]
                    duration = float(row[m[self.cdr_type]['duration']])
                    if row[m[self.cdr_type]['type']] == 'bytes':
                        self.data_type = 'data'
                    if row[m[self.cdr_type]['type']] == 'segundos':
                        self.data_type = 'calls'
                    if row[m[self.cdr_type]['type']] == 'sms':
                        self.data_type = 'sms'

                    data = {
                        'supplier_id': self.supplier_id.id,
                        'time': datetime.strptime(
                            (row[m[self.cdr_type]['date']] + ' ' + row[m[self.cdr_type]['date2']]), '%Y%m%d %H%M%S'),
                        'origin': origin,  # TODO: check ->
                        'destiny': destiny,
                        'duration': duration,
                        'cost': float(row[m[self.cdr_type]['cost']].replace(',', '.')),
                        'data_type': self.data_type,
                        'company_id': self.company_id.id,
                    }
                    if self.data_type == 'data':
                        data['duration'] = 0
                    if contracts.has_key(data['origin']) and contracts[data['origin']]:
                        data['contract_line_id'] = contracts[data['origin']]
                        data['status'] = 'draft'
                    elif not contracts.has_key(data['origin']):
                        number = self.env['telephony_isp.pool.number'].search([['name', '=', data['origin']]])
                        if number:
                            contract_number = self.env['account.analytic.account.number'].search(
                                [['number_id', '=', number[0].id]])
                            if len(contract_number) == 1:
                                contracts[data['origin']] = contract_number[0].contract_line_id.id
                                data['contract_line_id'] = contract_number[0].contract_line_id.id
                                data['status'] = 'draft'
                            else:
                                contracts[data['origin']] = None
                                data['status'] = 'error'

                        else:
                            contracts[data['origin']] = None
                            data['status'] = 'error'
                    else:
                        data['status'] = 'error'

                    # if line_type == 'mobileline':
                    #     #apply default cost
                    #     data['amount'] = data['cost']
                    # else:
                    #     rate = get_rate(destiny)
                    #     # apply rates or default
                    #     if rate:
                    #         if rate.special:
                    #             data['amount'] = data['cost'] + data['cost'] * rate.ratio / 100.

                    #             data['rate_id'] = rate.id
                    #         else:
                    #             data['amount'] = rate.price / 60. * duration # seconds -> minute
                    #             data['rate_id'] = rate.id

                    #         if data['amount'] == 0:
                    #             data['status'] = 'free'
                    #     else:
                    #         data['amount'] = data['cost'] + data['cost'] * self.supplier_id.ratio / 100.
                    #         data['status'] = 'default'

                    data['amount'] = data['cost']

                    call_detail = self.env['telephony_isp.call_detail']
                    call_detail.create(data)

            elif self.cdr_type == 'vadavo' and self.data_type:
                # this type mixes voice,data and sms at the same cdr
                # if not self.data_type:
                #     raise ValidationError('Error! This supplier requires a data type')
                f = StringIO.StringIO(base64.decodestring(self.cdr_data))
                reader = csv.reader(f, delimiter=';')
                next(reader, None)  # skip header

                for row in reader:
                    ignore_line = False
                    origin = row[1]
                    if self.data_type == 'data':
                        destiny = ''
                        duration = float(1)
                        cost = float(row[4])
                        ignore_line = True if not cost or cost and cost == 0 else False
                    elif self.data_type == 'sms':
                        destiny = row[2]
                        duration = float(1)
                        cost = float(row[4])
                    else:
                        # calls, other
                        destiny = row[2]
                        duration = float(row[4])
                        cost = float(row[5])

                    if not ignore_line:
                        data = {
                            'supplier_id': self.supplier_id.id,
                            'time': datetime.strptime((row[0]), '%Y-%m-%d %H:%M:%S'),
                            'origin': origin,  # TODO: check ->
                            'destiny': destiny,
                            'duration': duration,
                            'cost': cost,
                            'data_type': self.data_type,
                            'company_id': self.company_id.id,
                        }

                        # if self.data_type == 'data':
                        #     data['duration'] = int(int(row[8]) / 1000)
                        if contracts.has_key(data['origin']) and contracts[data['origin']]:
                            data['contract_line_id'] = contracts[data['origin']]
                            data['status'] = 'draft'
                        elif not contracts.has_key(data['origin']):
                            number = self.env['telephony_isp.pool.number'].search([['name', '=', data['origin']]])
                            if number:
                                contract_number = self.env['account.analytic.account.number'].search(
                                    [['number_id', '=', number[0].id]])
                                if len(contract_number) == 1:
                                    contracts[data['origin']] = contract_number[0].contract_line_id.id
                                    data['contract_line_id'] = contract_number[0].contract_line_id.id
                                    data['status'] = 'draft'
                                else:
                                    contracts[data['origin']] = None
                                    data['status'] = 'error'

                            else:
                                contracts[data['origin']] = None
                                data['status'] = 'error'
                        else:
                            data['status'] = 'error'

                        data['amount'] = data['cost']

                        call_detail = self.env['telephony_isp.call_detail']
                        call_detail.create(data)

        return {'type': 'ir.actions.act_window_close'}

    supplier_id = fields.Many2one('telephony_isp.supplier')
    cdr_type = fields.Selection([
        ('aire', 'Aire Networks'),
        ('telcia', 'Telcia'),
        ('carrier-enabler', 'Carrier Enabler'),
        ('miscellaneous', 'Miscellaneous'),
        ('zargotel', 'Zargotel'),
        ('lemonvil', 'Lemonvil'),
        ('ion', 'ION'),
        ('masmovil', 'Masmovil'),
        ('ptv', 'PTV'),
        ('vadavo', 'Vadavo')
    ], string='CDR type', default='aire', required=True)
    cdr_data = fields.Binary('File')
    company_id = fields.Many2one('res.company', required=True)
    data_type = fields.Selection([('data', 'Data'), ('calls', 'Calls'), ('sms', 'SMS'), ('other', 'Other')])


class WizardImportRate(models.TransientModel):
    _name = 'telephony_isp.import.rate'
    _description = 'Rate file impport'

    @api.multi
    def import_rate(self):
        if self.rate_data and self.supplier_id:
            f = StringIO.StringIO(base64.decodestring(self.rate_data))
            dialect = csv.Sniffer().sniff(f.read(1024))
            f.seek(0)
            reader = csv.reader(f, dialect)
            # reader = csv.reader(f, delimiter=',')
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

        # print '>>>', product_telephony, product_telephony.telephony_ids
        for j in product_telephony.telephony_ids:
            minutes[j.segment] = float(j.minutes_free)

        return minutes  # could be {}

    def get_amount_status(self, call):
        # check for free calls
        call_origin = self.contracts[call.contract.id]['origins'][call.origin]

        # add logic to domestic(landline and mobileline) calls
        if call.rate_id:
            if call.rate_id.segment and self.contracts[call.contract.id]['origins'][call.origin]['minutes'].has_key(
                    'domestic'):
                if call.rate_id.segment in ['domestic_number', 'domestic_mobile']:
                    self.contracts[call.contract.id]['origins'][call.origin]['minutes'][
                        'domestic'] -= call.duration / 60.
                    d = call_origin['minutes']['domestic']
                    if d > 0:
                        amount = 0
                        status = 'free'
                    elif d > call.duration:
                        amount = call.amount / call.duration * abs(d)
                        stauts = 'special'
                    else:
                        amount = call.amount
                        status = 'invoiced'

                elif call.rate_id.segment and call_origin['minutes'].has_key(call.rate_id.segment):
                    self.contracts[call.contract.id]['origins'][call.origin]['minutes'][
                        call.rate_id.segment] -= call.duration / 60.
                    d = call_origin['minutes'][call.rate_id.segment]
                    if d > 0:
                        amount = 0
                        status = 'free'
                    elif d > call.duration:
                        amount = call.amount / call.duration * abs(d)
                        stauts = 'special'
                    else:
                        amount = call.amount
                        status = 'invoiced'

                else:
                    amount = call.amount
                    status = 'invoiced'

            else:
                if call.rate_id.segment and call_origin['minutes'].has_key(call.rate_id.segment):
                    self.contracts[call.contract.id]['origins'][call.origin]['minutes'][
                        call.rate_id.segment] -= call.duration / 60.
                    d = call_origin['minutes'][call.rate_id.segment]
                    if d > 0:
                        amount = 0
                        status = 'free'
                    elif d > call.duration:
                        amount = call.amount / call.duration * abs(d)
                        stauts = 'special'
                    else:
                        amount = call.amount
                        status = 'invoiced'
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
        filters = []
        filters.append(('time', '>=', self.date_start))
        filters.append(('time', '<',
                        (datetime.strptime(self.date_end, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=1)).strftime(
                            DEFAULT_SERVER_DATE_FORMAT)))
        if self.company_id:
            filters.append(('company_id', '=', self.company_id.id))

        if self.partner_id:
            filters.append(('partner.id', '=', self.partner_id.id))
        if self.recalc:
            filters.append(('status', '!=', 'error'))
        else:
            filters.append(('status', '=', 'draft'))
        if self.supplier_id:
            filters.append(('supplier_id', '=', self.supplier_id.id))

        print
        filters

        call_details = self.env['telephony_isp.call_detail'].search(filters, order='time')

        # if self.partner_id and recalc
        #     call_details = self.env['telephony_isp.call_detail'].search([
        #         ('supplier_id', '=', self.supplier_id.id),
        #         ('company_id', '=', self.company_id.id),
        #         ('partner.id', '=', self.partner_id.id),
        #         ('status', '!=', 'error'),
        #         ('time', '>=',  self.date_start),
        #         ('time', '<', (datetime.strptime(self.date_end, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=1)).strftime(DEFAULT_SERVER_DATE_FORMAT))
        #     ], order='time')
        # elif self.partner_id:
        #     call_details = self.env['telephony_isp.call_detail'].search([
        #         ('supplier_id', '=', self.supplier_id.id),
        #         ('company_id', '=', self.company_id.id),
        #         ('partner.id', '=', self.partner_id.id),
        #         ('status', '=', 'draft'),
        #         ('time', '>=',  self.date_start),
        #         ('time', '<', (datetime.strptime(self.date_end, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=1)).strftime(DEFAULT_SERVER_DATE_FORMAT))
        #     ], order='time')
        # else:
        #     call_details = self.env['telephony_isp.call_detail'].search([
        #         ('supplier_id', '=', self.supplier_id.id),
        #         ('company_id', '=', self.company_id.id),
        #         ('status', '=', 'draft'),
        #         ('time', '>=',  self.date_start),
        #         ('time', '<', (datetime.strptime(self.date_end, DEFAULT_SERVER_DATE_FORMAT) + timedelta(days=1)).strftime(DEFAULT_SERVER_DATE_FORMAT))
        #     ], order='time')
        # create period
        data = {
            'date_start': self.date_start,
            'date_end': self.date_end,
            'company_id': self.company_id.id,
        }
        if self.supplier_id:
            data['supplier_id'] = self.supplier_id.id

        period = self.env['telephony_isp.period'].create(data)

        # group by contract
        self.contracts = {}
        for i in call_details:
            # contracts
            if not self.contracts.has_key(i.contract.id):
                # first origin
                # get data type to show in the invoice report:
                if i.supplier_id.data_type:
                    data_type = i.supplier_id.data_type
                else:
                    data_type = 'calls'

                self.contracts[i.contract.id] = {
                    'contract': i.contract,
                    'origins': {
                        i.origin: {
                            'product': i.product,
                            'calls': [],
                            'status': [],
                            'total': 0,
                            'minutes': self.get_minutes_free(i.origin, i.contract_line_id.product_id.id),
                            'data_type': data_type
                        }
                    },
                }

                self.get_amount_status(i)

            elif self.contracts[i.contract.id]['origins'].has_key(i.origin):

                self.get_amount_status(i)
            else:
                # TODO: KISS (refactor this!)
                # new origin
                if i.supplier_id.data_type:
                    data_type = i.supplier_id.data_type
                else:
                    data_type = 'calls'

                self.contracts[i.contract.id]['origins'][i.origin] = {
                    'product': i.product,
                    'calls': [],
                    'status': [],
                    'total': 0,
                    'minutes': self.get_minutes_free(i.origin, i.contract_line_id.product_id.id),
                    'data_type': data_type
                }

                self.get_amount_status(i)

        # create invoices with lines
        invoices = []
        amount = 0
        for i in self.contracts.values():
            # invoice lines
            lines = []
            lines_name = []
            for j in i['origins']:
                # default_product = i['origins'][j]['calls'][0]['supplier_id'].product_id
                product = i['origins'][j]['product']
                if 'Consumo de %s' % j not in lines_name:
                    lines.append((0, 0, {
                        'product_id': product.id,
                        'name': 'Consumo de %s' % j,
                        'account_id': product.property_account_income.id,
                        'account_analytic_id': i['contract'].id,
                        'invoice_line_tax_id': [(6, 0, [k.id for k in product.taxes_id])],
                        'price_unit': i['origins'][j]['total']
                    }))
                    lines_name.append('Consumo de %s' % j)
                if not product.property_account_income:
                    if product:
                        product_err = 'Missing account for product:'+product.name + str(product.id) + 'numero:' + j
                    else:
                        product_err = 'Missing product for line'+j
                        raise ValidationError(product_err)

                # invoice
                data = {
                    'is_telephony': True,
                    'origin': i['contract'].code,
                    'date_invoice': self.date_invoice,
                    'partner_id': i['contract'].partner_id.id,
                    'journal_id': self.journal_id.id,
                    'telephony_period_id': period.id,
                    'account_id': i['contract'].partner_id.property_account_receivable.id,
                    'invoice_line': lines,
                    'company_id': self.company_id.id,
                    'data_type': i['origins'][j]['data_type']
                }
                if not i['contract'].partner_id.property_account_receivable:
                    partner_err = 'Missing account for partner:'+i['contract'].partner_id.name+str(i['contract'].partner_id.id)
                    raise ValidationError(partner_err)
                if hasattr(i['contract'], 'payment_mode'):
                    data['payment_mode'] = i['contract'].payment_mode.id,

                # recover or create invoice to add lines
                if data['partner_id']:
                    # first of all, search for draft invoices for this partner and contract
                    invoice_obj = self.env['account.invoice'].search(
                        [('state', '=', 'draft'), ('partner_id', '=', data['partner_id']),
                         ('origin', '=', data['origin']), ('company_id', '=', self.company_id.id)])
                    if len(invoice_obj) == 1 and self.existing_invoice:
                        invoice = invoice_obj[0]
                        lines_not_exist = []
                        for line in lines:
                            enc = False
                            for inv_line in invoice.invoice_line:
                                if line[2]['name'] == inv_line.name:
                                    enc = True
                            if not enc:
                                lines_not_exist.append(line)

                        invoice.write({
                            'is_telephony': True,
                            'telephony_period_id': period.id
                        })

                        if len(lines_not_exist) != 0:
                            invoice.write({
                                'invoice_line': lines_not_exist
                            })

                    elif len(invoice_obj) == 0 or not self.existing_invoice:
                        invoice = self.env['account.invoice'].create(data)
                    else:
                        # raise ValidationError('Error processing contract for %s. Many draft invoices.' % ', '.join(i['origins'].keys()))
                        raise ValidationError(
                            'Error processing contract for %s. Many draft invoices. or NO invoice' % j)
                else:
                    raise ValidationError('Error processing contract for %s' % ', '.join(i['origins'].keys()))

                amount += i['origins'][j]['total']

                # link calls with its invoice and set new status
                for k in xrange(len(i['origins'][j]['calls'])):
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

                # recalc taxes
                invoice.button_reset_taxes()

                # append invoice to period
                invoices.append(invoice)

        # update period data
        data = {
            'invoice_ids': [(6, 0, [k.id for k in invoices])],
            'call_details_ids': [(6, 0, [k.id for k in call_details])],
            'amount': amount
        }

        period.write(data)

    journal_id = fields.Many2one('account.journal', 'Journal', required=True)
    partner_id = fields.Many2one('res.partner')
    date_invoice = fields.Date('Date invoice', required=True)
    date_start = fields.Date('From', required=True)
    date_end = fields.Date('To', required=True)
    recalc = fields.Boolean(help='Override previus calcs in calls')  # override invoiced status
    existing_invoice = fields.Boolean('Add to existing invoices')
    company_id = fields.Many2one('res.company', required=True)
    supplier_id = fields.Many2one('telephony_isp.supplier')
