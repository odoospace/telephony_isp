# -*- coding: utf-8 -*-

from openerp import models, fields, api

class account_invoice(models.Model):
    _inherit = 'account.invoice'

    is_telephony = fields.Boolean() # internal field in invoice
    telephony_ids = fields.One2many('telephony_isp.call_detail', 'invoice_id') # use related field
    telephony_period_id = fields.Many2one('telephony_isp.period')


class product_product(models.Model):
    _inherit = 'product.product'

    telephony_ok = fields.Boolean('Can be used in telephony', help='This product can be used for telephony')
    telephony_ids = fields.One2many('product.telephony', 'product_id')


class product_telephony(models.Model):
    _name = 'product.telephony'

    product_id = fields.Many2one('product.product')
    segment = fields.Selection([
        ('domestic_number', 'Domestic Number'),
        ('domestic_mobile', 'Domestic Mobile'),
        ('international', 'Intenational'),
        ('Other', 'Other')]
    )
    minutes_free = fields.Integer('Minutes free')


class call_detail(models.Model):
    _name = 'telephony_isp.call_detail'

    @api.multi
    def set_status(self, status):
        self.write({'status': status})

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
    product_id = fields.Many2one('product.product') # operator
    ratio = fields.Float() # price = cost + cost * ratio
    date_start = fields.Date()
    date_end = fields.Date()
    rate_ids = fields.One2many('telephony_isp.rate', 'supplier_id')


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
    date_start = fields.Date()
    date_end = fields.Date()
    amount = fields.Float() # total
