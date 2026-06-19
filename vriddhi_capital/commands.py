import click
import frappe
from frappe.commands import pass_context


@click.command("seed-vriddhi")
@pass_context
def seed_vriddhi(context):
	"""Seed Vriddhi Capital sample company data for the hosted submission."""
	site = context.sites[0]
	frappe.init(site=site)
	frappe.connect()
	try:
		from vriddhi_capital.setup.seed import seed_vriddhi_sample_company

		seed_vriddhi_sample_company()
		frappe.db.commit()
		click.echo(f"Seeded Vriddhi sample data on {site}")
	finally:
		frappe.destroy()


commands = [seed_vriddhi]
