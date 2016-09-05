# -*- coding: utf-8 -*-
from openerp import http

# class TelephonyIsp(http.Controller):
#     @http.route('/telephony_isp/telephony_isp/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/telephony_isp/telephony_isp/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('telephony_isp.listing', {
#             'root': '/telephony_isp/telephony_isp',
#             'objects': http.request.env['telephony_isp.telephony_isp'].search([]),
#         })

#     @http.route('/telephony_isp/telephony_isp/objects/<model("telephony_isp.telephony_isp"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('telephony_isp.object', {
#             'object': obj
#         })