# -*- coding: utf-8 -*-

from openerp import models, fields, api

class call_detail(models.Model):
    _name = 'telephony_isp.call_detail'

    # TODO: add related field to contract_id with customer
    name = fields.Char() # carrier destination network
    cdr_id = fields.Char()
    supplier_id = fields.Many2one('telephony_isp.supplier') # supplier
    contract_id = fields.Many2one('account.analytic.account') # contract
    invoice_id = fields.Many2one('account.invoice') # invoice
    partner = fields.Many2one(related='contract_id.partner_id')
    contract_code = fields.Char(related='contract_id.code')
    time = fields.Datetime()
    origin = fields.Char()
    destiny = fields.Char()
    rate_id = fields.Many2one('telephony_isp.rate', 'Rate') # rate
    duration = fields.Integer() # in seconds
    cost = fields.Float(digits=(2, 6))
    final_price = fields.Float(digits=(2, 6))
    note = fields.Text()
    status = fields.Selection([
        ('raw', 'Raw'),
        ('draft', 'Draft'),
        ('invoiced', 'Invoiced'),
        ('free', 'Free'),
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
    ratio = fields.Float() # price = cost + cost * ratio
    date_start = fields.Date()
    date_end = fields.Date()
    rate_ids = fields.One2many('telephony_isp.rate', 'supplier_id')


class rate(models.Model):
    """Price to apply to call cost"""
    _name = 'telephony_isp.rate'

    supplier_id = fields.Many2one('telephony_isp.supplier')
    name = fields.Char() # network
    prefix = fields.Char()
    cost = fields.Float(digits=(2, 6))
    price = fields.Float(digits=(2, 6))
