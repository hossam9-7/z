# -*- encoding: utf-8 -*-

from datetime import datetime, time

from addons.product.models import product
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseRequestType(models.Model):
    _name = "purchase.request.type"
    _description = "Purchase request Type"
    _order = "sequence"

    name = fields.Char(string='Agreement Type', required=True, translate=True)
    sequence = fields.Integer(default=1)
    quantity_copy = fields.Selection(string='Quantities', required=True, default=1)


class PurchaseRequest(models.Model):
    _name = "purchase.request"
    _description = "Purchase request"
    _order = "id description"

    def _get_type_id(self):
        return self.env['purchase.request.type'].search([], limit=1)

    name = fields.Char(string='Reference', required=True, copy=False, default='New', readonly=True)
    origin = fields.Char(string='Source Document')
    order_count = fields.Integer(compute='_compute_orders_number', string='Number of Orders')
    vendor_id = fields.Many2one('res.partner', string="Vendor", domain="['|', ('company_id', '=', False),"
                                                                       " ('company_id', '=', company_id)]")
    type_id = fields.Many2one('purchase.request.type', string="Agreement Type", required=True, default=_get_type_id)
    ordering_date = fields.Date(string="Ordering Date", tracking=True)
    date_end = fields.Datetime(string='Agreement Deadline', tracking=True)
    schedule_date = fields.Date(string='Delivery Date', index=True,
                                help="The expected and scheduled delivery date where all the products are received",
                                tracking=True)
    user_id = fields.Many2one('res.users', string='Purchase Representative',
                              default=lambda self: self.env.user, check_company=True)
    description = fields.Text()
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    purchase_ids = fields.One2many('purchase.order', 'request_id', string='Purchase Orders',
                                   states={'done': [('readonly', True)]})
    line_ids = fields.One2many('purchase.request.line', 'request_id', string='Products to Purchase',
                               states={'done': [('readonly', True)]}, copy=True)
    product_id = fields.Many2one('product.product', related='line_ids.product_id', string='Product', readonly=False)

    product.t_id = fields.Many2one('uom.uom', string='Product Unit of Measure', domain="[('category_id', '=',"
                                                                                       " product.t_category_id)]")
    product.t_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure')

    purchase_request_STATES = [
        ('draft', 'Draft'),
        ('ongoing', 'Ongoing'),
        ('in_progress', 'Confirmed'),
        ('open', 'Bid Selection'),
        ('done', 'Closed'),
        ('cancel', 'Cancelled')
    ]

    state = fields.Selection(purchase_request_STATES, 'Status', tracking=True, required=True, copy=False,
                             default='draft')
    state_blanket_order = fields.Selection(purchase_request_STATES, compute='_set_state')
    is_quantity_copy = fields.Selection(related='type_id.quantity_copy', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True,
                                  default=lambda self: self.env.company.currency_id.id)

    @api.depends('state')
    def _set_state(self):
        for request in self:
            request.state_blanket_order = request.state

    def _compute_orders_number(self):
        for request in self:
            request.order_count = len(request.purchase_ids)

    def action_cancel(self):
        for request in self:
            for request_line in request.line_ids:
                request_line.supplier_info_ids.unlink()
            request.purchase_ids.button_cancel()
            for po in request.purchase_ids:
                po.message_post(body=_('Cancelled'))
        self.write({'state': 'cancel'})

    def action_in_progress(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("no product line confirmation for '%s' failed.", self.name))
        if self.type_id.quantity_copy == 'none' and self.vendor_id:
            for request_line in self.line_ids:
                if request_line.price_unit <= 0.0:
                    raise UserError(_('please put a price.'))
                if request_line.product_qty <= 0.0:
                    raise UserError(_('please put a quantity.'))
                request_line.create_supplier_info()
            self.write({'state': 'ongoing'})
        else:
            self.write({'state': 'in_progress'})
        if self.name == 'New':
            if self.is_quantity_copy != 'none':
                self.name = self.env['ir.sequence'].next_by_code('purchase.request.purchase.tender')
            else:
                self.name = self.env['ir.sequence'].next_by_code('purchase.request.blanket.order')

    def action_open(self):
        self.write({'state': 'open'})

    def action_draft(self):
        self.ensure_one()
        self.name = 'New'
        self.write({'state': 'draft'})

    def action_done(self):
        if any(purchase_order.state in ['draft', 'sent', 'to approve'] for purchase_order in
               self.mapped('purchase_ids')):
            raise UserError(_('You have to cancel or validate every request before closing the purchase request.'))
        for request in self:
            for request_line in request.line_ids:
                request_line.supplier_info_ids.unlink()
        self.write({'state': 'done'})

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product.t_id = self.product_id.uom_po_id
            self.product_qty = 1.0
        if not self.schedule_date:
            self.schedule_date = self.request_id.schedule_date

    def _prepare_purchase_order_line(self, name, product_qty=0.0, price_unit=0.0):
        self.ensure_one()
        request = self.request_id
        if self.product_description_variants:
            name += '\n' + self.product_description_variants
        if request.schedule_date:
            date_planned = datetime.combine(request.schedule_date, time.min)
        else:
            date_planned = datetime.now()
        return {
            'name': name,
            'product_id': self.product_id.id,
            'product.t': self.product_id.uom_po_id.id,
            'product_qty': product_qty,
            'price_unit': price_unit,
            'date_planned': date_planned,
        }
