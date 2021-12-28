# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from datetime import datetime,timedelta
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from openerp.exceptions import Warning
import itertools

class posPaymentReport(models.AbstractModel):

	_name='report.bi_pos_reports.report_pos_payment'	
	_description = "POS Payment Report Wizard"

	
	@api.multi
	def _get_report_values(self, docids, data=None,sessions=False):
		""" Serialise the orders of the day information

		params: pos_payment_rec.start_dt, pos_payment_rec.end_dt string representing the datetime of order
		"""
		Report = self.env['ir.actions.report']
		top_selling_report = Report._get_report_from_name('pos_membership_odoo.report_profit_loss')		
		top_selling_rec = self.env['pos.payment.wizard'].browse(docids)	
		orders = self.env['pos.order'].search([
				('date_order', '>=', top_selling_rec.start_dt),
				('date_order', '<=', top_selling_rec.end_dt),
				('state', 'in', ['paid','invoiced','done']),
			])
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
		prod_data ={}
		top_list={}
		my_prod = {}			
		for odr in orders:		
			for line in odr.lines:					
				product = line.product_id.id
				disc = 0
				if line.discount > 0 :
					disc =(line.price_unit * line.qty * line.discount)/100

				if product in prod_data:
					old_qty = prod_data[product]['qty']
					old_price = prod_data[product]['price_subtotal']
					old_discount = prod_data[product]['discount']
				
					prod_data[product].update({
						'qty' :  float(old_qty+line.qty),
						'price_subtotal' :  float(old_price+line.price_subtotal_incl),
						'discount': float(old_discount + disc),
					})
				else:	
					prod_data.update({ product : {
						'product_id':line.product_id.id,
						'product_name':line.product_id.name,
						'uom_name':line.product_id.uom_id.name,
						'price_unit':line.price_unit,						
						'price_subtotal':line.price_subtotal_incl,						
						'qty' : float(line.qty),
						'discount':float(disc),					
					}})
				if product in my_prod:
					my_prod[product] += line.qty

				else:
					my_prod.update({
						product : line.qty
						})
		top_list=(sorted(prod_data.values(), key=lambda kv: kv['qty'], reverse=True))
				
		return {
			'currency_precision': 2,
			'doc_ids': docids,
			'doc_model': 'pos.top.selling.wizard',
			'start_dt' : top_selling_rec.start_dt,
			'end_dt' : top_selling_rec.end_dt,
			'prod_data':top_list,
			'payments': payments,			
		}
	

	

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
