# -*- coding: utf-8 -*-
# from odoo import http


# class Ztask(http.Controller):
#     @http.route('/ztask/ztask/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ztask/ztask/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('ztask.listing', {
#             'root': '/ztask/ztask',
#             'objects': http.request.env['ztask.ztask'].search([]),
#         })

#     @http.route('/ztask/ztask/objects/<model("ztask.ztask"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ztask.object', {
#             'object': obj
#         })
