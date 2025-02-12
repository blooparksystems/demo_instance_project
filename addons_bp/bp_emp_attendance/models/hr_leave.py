# © 2023 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


from odoo import api, fields, models


class HrLeave(models.Model):
    _inherit = "hr.leave"

    employee_overtime = fields.Float(related="employee_id.total_overtime")

    def action_refuse(self):
        if self.env.user.has_group('bp_emp_attendance.group_cancel_extra_hours'):
            self.mapped("overtime_id").unlink()
        super().action_refuse()

    @api.depends('holiday_status_id')
    def _compute_overtime_deductible(self):
        has_group = self.env.user.has_group(
            'bp_emp_attendance.group_cancel_extra_hours'
        )
        return (
            self.write(
                {
                    "overtime_deductible": False,
                }
            )
            if has_group
            else super()._compute_overtime_deductible()
        )
