# -*- coding: utf-8 -*-

import tempfile
import os
from ..wizard import wizard
from odoo import models, fields, api
# check pysftp capability
try:
    import pysftp
except:
    pysftp = None

try:
    import ftplib
except:
    ftplib = None

try:
    import zipfile
except:
    zipfile = None


class account_invoice(models.Model):
    _inherit = 'account.invoice'

    is_telephony = fields.Boolean() # internal field in invoice
    telephony_ids = fields.One2many('telephony_isp.call_detail', 'invoice_id') # use related field
    telephony_period_id = fields.Many2one('telephony_isp.period')


class account_analytic_account_number(models.Model):
    _name = 'account.analytic.account.number'

    @api.model
    def _get_lines(self):
        #ids = []
        res = [('analytic_account_id', '=', self.contract_id)]
        print ('>>>', res)
        return res

    number_id = fields.Many2one('telephony_isp.pool.number', required=True, domain="[('status', '=', 'not_assigned')]")
    # name = fields.Char(related='number_id.name', store=True)
    contract_id = fields.Many2one('account.analytic.account')
    contract_line_id = fields.Many2one('account.analytic.invoice.line',
#        domain=_get_lines)
        # domain="[('analytic_account_id', '=', contract_id)]"
    )
    pool = fields.Many2one(related='number_id.pool_ida')
    login = fields.Char()
    password = fields.Char()
    product_id = fields.Many2one('product.product')
    mac = fields.Char()

    @api.model
    def create(self, vals):
        """change status of number in the pool to assigned"""
        data = {
            'status': 'assigned',
            'last_contract_id': vals['contract_id']
        }

        res = super(account_analytic_account_number, self).create(vals)
        number =  self.env['telephony_isp.pool.number'].browse([vals['number_id']])[0]
        number.write(data)
        return res

    @api.multi
    def unlink(self):
        """check if this contract is the last link for this number"""
        for i in self:
            if i.contract_id == i.number_id.last_contract_id:
                data = {
                    'status': 'not_assigned',
                    'last_contract_id': None
                }
                i.number_id.write(data)

        res = super(account_analytic_account_number, self).unlink()
        return res


class account_analytic_account(models.Model):
    _inherit = 'account.analytic.account'

    use_telephony = fields.Boolean() # internal field in invoice
    telephony_number_ids = fields.One2many('account.analytic.account.number', 'contract_id')

"""
class account_analytic_invoice_line(models.Model):
    _inherit = 'account.analytic.invoice.line'

    number_id = fields.Many2one('account.analytic.account.number')
"""

class product_product(models.Model):
    _inherit = 'product.product'

    telephony_ok = fields.Boolean('Can be used in telephony', help='This product can be used for telephony')
    telephony_ids = fields.One2many('product.telephony', 'product_id')

class product_template(models.Model):
    _inherit = 'product.template'

    telephony_ok = fields.Boolean('Can be used in telephony', help='This product can be used for telephony')
    telephony_ids = fields.One2many('product.telephony', 'product_id')


class product_telephony(models.Model):
    _name = 'product.telephony'

    product_id = fields.Many2one('product.template')
    segment = fields.Selection([
        ('domestic_number', 'Domestic Number'),
        ('domestic_mobile', 'Domestic Mobile'),
        ('domestic', 'Domestic'),
        ('international', 'Intenational'),
        ('international_mobile', 'Intenational Mobile'),
        ('sms', 'SMS'),
        ('megabytes', 'Megabytes'),
        ('other', 'Other')]
    )
    minutes_free = fields.Integer('Units free')


class pool(models.Model):
    _name = 'telephony_isp.pool'

    number_ids = fields.One2many('telephony_isp.pool.number', 'pool_id')
    supplier_id = fields.Many2one('telephony_isp.supplier', required=True)
    name = fields.Char(required=True)
    pool_type = fields.Selection([
        ('fixed', 'Fixed'),
        ('mobile', 'Mobile'),
        ('mixed', 'Mixed'),
        ('other', 'Other')
    ])


class pool_number(models.Model):
    _name = 'telephony_isp.pool.number'

    pool_id = fields.Many2one('telephony_isp.pool', required=True)
    name = fields.Char(required=True)
    number_type = fields.Selection([
        ('fixed', 'Fixed'),
        ('mobile', 'Mobile'),
        ('other', 'Other')], default='fixed'
    ) # TODO: remove this field
    status = fields.Selection([
        ('not_assigned', 'Not asigned'),
        ('assigned', 'Asigned'),
        ('no_active', 'No active')], default='not_assigned'
    )
    #contract_ids = fields.One2many('account.analytic.account')
    last_contract_id = fields.Many2one('account.analytic.account')# current active contract for this number
    migrated = fields.Boolean()


    @api.multi
    @api.depends('name', 'pool_id')
    def name_get(self):
        result = []
        for i in self:
            result.append((i.id, "%s - %s" % (i.name, i.pool_id.name)))
        return result

class call_detail(models.Model):
    _name = 'telephony_isp.call_detail'

    @api.multi
    def set_status(self, status):
        self.write({'status': status})

    @api.multi
    def fix_errors(self):
        data_with_errors = self.search([('contract_line_id', '=', False)]) #([('status', '=', 'error')])
        print ('errors:', len(data_with_errors))
        for i in data_with_errors:
            number = self.env['telephony_isp.pool.number'].search([('name', '=', i.origin)])
            if len(number) == 1:
                contract_line = self.env['account.analytic.account.number'].search([('number_id', '=', number[0].id)])
                if len(contract_line) == 1:
                    data = {
                        'contract_line_id': contract_line[0].contract_line_id.id,
                    }
                    if i.status == 'error':
                        data['status'] = 'draft'
                    i.write(data)
                    print ('Fixed!', i.origin, i)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
            }



    # TODO: add related field to contract_id with customer
    name = fields.Char() # carrier destination network
    cdr_id = fields.Char()
    supplier_id = fields.Many2one('telephony_isp.supplier') # supplier
    period_id = fields.Many2one('telephony_isp.period') # period
    contract_line_id = fields.Many2one('account.analytic.invoice.line') # contract line
    contract = fields.Many2one(related='contract_line_id.analytic_account_id') # contract
    #invoice_line_id = fields.Many2one('account.invoice.line') # invoice line
    invoice_id = fields.Many2one('account.invoice')
    partner = fields.Many2one(related='contract_line_id.analytic_account_id.partner_id', store=True)
    contract_code = fields.Char(related='contract_line_id.analytic_account_id.code', store=True)
    product = fields.Many2one(related='contract_line_id.product_id', store=True)
    time = fields.Datetime()
    origin = fields.Char()
    destiny = fields.Char()
    rate_id = fields.Many2one('telephony_isp.rate', 'Rate') # rate
    duration = fields.Integer() # in seconds
    cost = fields.Float(digits=(2, 6))
    amount = fields.Float(digits=(2, 6))
    note = fields.Text()
    status = fields.Selection([
        ('raw', 'Raw'),
        ('default', 'Default'),
        ('draft', 'Draft'),
        ('invoiced', 'Invoiced'),
        ('free', 'Free (invoiced)'),
        ('special', 'Special (invoiced)'),
        ('error', 'Error')],
        default='raw')
    to_invoice = fields.Boolean(default=True) # False -> free
    hidden = fields.Boolean(default=False) # hide this entry to some users - experimental


# TODO: use price lists instead ?
class supplier(models.Model):
    """Supplier data"""
    _name = 'telephony_isp.supplier'

    name = fields.Char() # copy from partner ?
    partner_id = fields.Many2one('res.partner') # operator
    #product_id = fields.Many2one('product.product') # operator
    ratio = fields.Float() # price = cost + cost * ratio
    date_start = fields.Date()
    date_end = fields.Date()
    rate_ids = fields.One2many('telephony_isp.rate', 'supplier_id')
    # ftp info to catch data
    ftp_hostname = fields.Char()
    ftp_path = fields.Char(default='/')
    ftp_user = fields.Char()
    ftp_password = fields.Char()
    cdr_type = fields.Selection([
        ('aire', 'Aire Networks'),
        ('telcia', 'Telcia'),
        ('misc', 'Misc')
    ], string='CDR type', default='aire', required=True)


class rate(models.Model):
    """Price to apply to call cost"""
    _name = 'telephony_isp.rate'

    supplier_id = fields.Many2one('telephony_isp.supplier')
    name = fields.Char() # TODO: remove this one?
    segment = fields.Selection([
        ('domestic_number', 'Domestic Number'),
        ('domestic_mobile', 'Domestic Mobile'),
        ('international', 'Intenational'),
        ('Other', 'Other')]
    )
    prefix = fields.Char()
    special = fields.Boolean('Special', help='This number is special and it\'ll use rate')
    connection = fields.Float(digits=(2, 6), help='Connection cost')
    cost = fields.Float(digits=(2, 6), help='Reference cost')
    price = fields.Float(digits=(2, 6), help='Price by minute') # price is fix
    ratio = fields.Float(digits=(2, 6), help='Percentaje for special numbers') # rate percentage


class period(models.Model):
    """Price to apply to call cost"""
    _name = 'telephony_isp.period'

    #supplier_id = fields.Many2one('telephony_isp.supplier', 'Supplier')
    invoice_ids = fields.One2many('account.invoice', 'telephony_period_id', 'Invoices')
    call_details_ids = fields.One2many('telephony_isp.call_detail', 'period_id', 'Call detail')
    name = fields.Char() # TODO: remove this one?
    date_start = fields.Date('Start')
    date_end = fields.Date('End')
    amount = fields.Float() # total


class task(models.Model):
    """CRON"""
    _name = 'telephony_isp.task'

    @api.model
    def download_ftp(self):
        print('FTP!!!')

        suppliers = self.env['telephony_isp.supplier'].search([])
        print ('>>>', suppliers)
        for s in suppliers:
            # check if there is ftp info
            if not s.ftp_hostname or not s.ftp_user or not s.ftp_password:
                continue
            # check protocol
            if s.ftp_hostname.startswith('ftp://'):
                protocol = 'ftp'
                hostname, port = s.ftp_hostname[6:].split(':')
            elif s.ftp_hostname.startswith('sftp://'):
                protocol = 'sftp'
                hostname, port = s.ftp_hostname[7:].split(':')
            else:
                protocol = 'ftp'
                hostname, port = s.ftp_hostname.split(':')
            path = s.ftp_path
            user = s.ftp_user
            password = s.ftp_password

            if protocol == 'sftp' and pysftp:
                with pysftp.Connection(hostname, port=int(port), username=user, password=password) as sftp:
                    files = sftp.listdir(path)
                    print('FILES:', files)
            elif protocol == 'ftp' and ftplib:
                ftp = ftplib.FTP()
                ftp.connect(hostname, int(port), 5)
                ftp.login(user, password)
                ftp.cwd(path)
                files = ftp.nlst()
                # copy files

                # for f in (i for i in files if i.endswith('.done')):
                #     ftp.rename(f, f.split('.')[0] + '.zip')
                # continue
                # read and process data in zip files
                for f in (i for i in files if i.endswith('.zip')):
                    temp = tempfile.NamedTemporaryFile(suffix=".zip")
                    ftp.retrbinary('RETR %s' % f, temp.write)
                    print ('FTP:', f, temp)
                    with zipfile.ZipFile(temp, "r") as zip_ref:
                        with tempfile.TemporaryDirectory() as tmpdirname:
                            print('Created temporary directory:', tmpdirname)
                            zip_ref.extractall(tmpdirname)
                            datafiles = os.listdir(tmpdirname)
                            for datafile in datafiles:
                                data = open(os.path.join(tmpdirname, datafile), 'r').read()
                                print('>>>', datafile)
                                w_obj = self.env['telephony_isp.import.cdr.ws']
                                d = {
                                    'cdr_type': 'misc',
                                    'cdr_data': wizard.base64.b64encode(data.encode('utf-8'))
                                }
                                w = w_obj.create(d)
                                w.import_cdr_ws()
                    # rename file to avoid process it again
                    ftp.rename(f, f + '.done')
                    temp.close()


                
                #print('>>>', w)
