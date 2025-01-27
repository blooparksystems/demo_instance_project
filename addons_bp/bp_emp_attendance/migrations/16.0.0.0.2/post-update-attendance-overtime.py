# © 2023 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    overtimes = env["hr.attendance.overtime"].search([])
    overtimes._compute_overtime_data()
    overtimes.action_update_day_overtime()
