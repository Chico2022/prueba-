# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta,date,datetime
from functools import partial

import psycopg2
import pytz

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons import decimal_precision as dp

_logger = logging.getLogger(__name__)

class PosXReport(models.TransientModel):

	_name='x.report.wizard'
	_description = "POS x Report Wizard"


	pos_session_ids = fields.Many2many('pos.session', 'pos_sessions',string="POS Session(s)",domain="[('state', 'in', ['opened'])]",required=True)
	report_type = fields.Char('Report Type', readonly = True, default='PDF')

	@api.multi
	def generate_x_report(self):
		data = {'session_ids':self.pos_session_ids.ids}
		return self.env.ref('bi_pos_reports.action_x_report_print').report_action([], data=data)

class OpenSessionReport(models.AbstractModel):

	_name = 'report.bi_pos_reports.report_open_session'
	_description = 'Point of Sale Details'

	@api.model
	def get_sale_details(self,sessions=False):
		if sessions:
			orders = self.env['pos.order'].search([
				('session_id.state','in', ['opened']),
				('session_id', 'in', sessions.ids)])

		user_currency = self.env.user.company_id.currency_id

		total = 0.0
		total_tax = 0.0
		products = []
		categories_data = {}
		categories_tot = []
		total_discount = 0.0
		return_total =0.0
		for order in orders:
			if user_currency != order.pricelist_id.currency_id:
				total += order.pricelist_id.currency_id._convert(
					order.amount_total, user_currency, order.company_id, order.date_order or fields.Date.today())
			else:
				total += order.amount_total

			total_tax = total_tax + order.amount_tax
			return_total+= order.amount_return

			for line in order.lines:
				disc = 0
				if line.discount > 0 :
					disc =(line.price_unit * line.qty * line.discount)/100

				total_discount += disc

				category = line.product_id.pos_categ_id.name
				if category in categories_data:
					old_subtotal = categories_data[category]['total']
					categories_data[category].update({
					'total' : old_subtotal+line.price_subtotal_incl,
					})
				else:
					categories_data.update({ category : {
						'name' :category,
						'total' : line.price_subtotal_incl,
					}})
			categories_tot = list(categories_data.values())		
		st_line_ids = self.env["account.bank.statement.line"].search([('pos_statement_id', 'in', orders.ids)]).ids
		if st_line_ids:
			self.env.cr.execute("""
				SELECT aj.name, sum(amount) total
				FROM account_bank_statement_line AS absl,
					 account_bank_statement AS abs,
					 account_journal AS aj 
				WHERE absl.statement_id = abs.id
					AND abs.journal_id = aj.id 
					AND absl.id IN %s 
				GROUP BY aj.name
			""", (tuple(st_line_ids),))
			payments = self.env.cr.dictfetchall()
		else:
			payments = []

		sessions_name =[]
		opening_balance = 0.0
		for i in sessions:
			if i.cash_register_balance_start:
				opening_balance += i.cash_register_balance_start
			sessions_name.append(i.name)

		num_sessions = ', '.join(map(str,sessions_name) )

		return {
			'currency_precision': 2,
			'total_paid': user_currency.round(total),
			'payments': payments,
			'company_name': self.env.user.company_id.name,
			'taxes': float(total_tax),
			'num_sessions': num_sessions,
			# 'products_data': products,
			'categories_data':categories_tot,
			'total_discount' : total_discount,
			'print_date' : datetime.now(),
			'return_total':return_total,
			'opening_balance':opening_balance,
		}

	@api.multi
	def _get_report_values(self, docids, data=None):
		data = dict(data or {})
		sessions = self.env['pos.session'].browse(data['session_ids'])
		data.update(self.get_sale_details(sessions))
		return data
