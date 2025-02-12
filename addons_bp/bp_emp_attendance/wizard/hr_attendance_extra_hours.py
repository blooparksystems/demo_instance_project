# © 2023 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from dateutil.relativedelta import relativedelta
from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import Markup



class HRAttendanceExtraHours(models.TransientModel):
    _name = "hr.attendance.extra.hours"
    _description = "Attendance Extra Hours"

    date = fields.Date(required=True, default=fields.Date.today)
    extra_hours = fields.Float(required=True)
    employee_id = fields.Many2one("hr.employee", required=True)

    def action_confirm(self):
        """Create an attendance record on not logging day with at same login/logout
        datetime and add/deduct hours at employee_extra_hours field.

        raise an error if user tried to add extra or deduct hours on logging day

        :return: created attendance record
        """
        self.ensure_one()
        date_end = self.date + relativedelta(days=1)
        attendance = self.env["hr.attendance"].sudo()

        day_attendance = attendance.search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("check_in", ">=", self.date),
                ("check_in", "<", date_end),
            ],
            order="check_in asc",
        )

        if day_attendance:
            raise UserError(
                _(
                    "You're not able to add/deduct hours from this employee.\n"
                    "Employee already logged at this day!"
                )
            )

        attendance_date = fields.Datetime.from_string(str(self.date))
        attendance_date = attendance_date.replace(hour=6)
        msg = _(Markup(f"<strong>{self.env.user.name}<strong/> logged {self.extra_hours} extra hours on {self.date}."))
        self.employee_id.message_post(body=msg)
        return attendance.create(
            {
                "employee_id": self.employee_id.id,
                "check_in": attendance_date,
                "check_out": attendance_date,
                "employee_extra_hours": self.extra_hours,
            }
        )
