# © 2023 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import datetime

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class HrAttendanceOvertime(models.Model):
    _inherit = "hr.attendance.overtime"

    request_date = fields.Date(
        compute="_compute_overtime_data",
        store=True,
        string='Day (Request)',
    )
    leave_ids = fields.One2many(
        "hr.leave",
        "overtime_id",
        readonly=True,
        string="Leaves",
    )
    worked_hours = fields.Float(
        compute="_compute_overtime_data",
        store=True,
    )
    date = fields.Date(string='Day (Approved)')

    @api.depends("leave_ids", "adjustment", "date", "employee_id", "duration")
    def _compute_overtime_data(self):
        hr_att = self.env["hr.attendance"].sudo()
        for record in self:
            worked_hours = 0.0
            request_date = record.date or False
            if record.adjustment and record.leave_ids:
                request_date = record.leave_ids[0].request_date_from
            date_end = request_date + relativedelta(days=1)

            # Day attendance hours
            if not record.adjustment:
                att_group = hr_att.read_group(
                    [
                        ("employee_id", "=", record.employee_id.id),
                        ("check_in", ">=", request_date),
                        ("check_out", "<", date_end),
                    ],
                    groupby=["employee_id"],
                    fields=["employee_id", "worked_hours"],
                    lazy=False,
                )
                day_attendance = sum(x.get("worked_hours") for x in att_group)
                worked_hours = day_attendance

            record.request_date = request_date
            record.worked_hours = worked_hours

    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        for record in res:
            record.action_update_day_overtime()
        return res

    def write(self, vals):
        res = super().write(vals)
        my_list_set = {
            "employee_id",
            "date",
        }
        my_dict_set = set(vals)
        if my_list_set.intersection(my_dict_set):
            self.action_update_day_overtime()
        return res

    def action_update_day_overtime(self):
        hr_leaves = self.env["hr.leave"].sudo()
        for record in self.sudo().filtered(lambda o: not o.adjustment):
            date_from = record.date
            employee = record.employee_id
            resource_calendar = record.employee_id.resource_calendar_id
            dt_from = datetime.combine(date_from, datetime.min.time())
            dt_to = datetime.combine(date_from, datetime.max.time())
            work_data = resource_calendar.get_work_duration_data(
                from_datetime=dt_from,
                to_datetime=dt_to,
                compute_leaves=True,
            )
            required_hours = work_data.get("hours") or 0.00
            day_attendance = (
                self.env["hr.attendance"]
                .sudo()
                .search(
                    [
                        ("employee_id", "=", employee.id),
                        ("check_in", ">=", dt_from),
                        ("check_in", "<", dt_to),
                    ],
                    order="check_in asc",
                )
            )
            logged_hours = sum(day_attendance.mapped("worked_hours"))

            # Check employee leaves ['Extra hours' or 'On Vacations']
            emp_leaves_ids = employee.check_employee_vacation(
                date_from=dt_from,
                date_to=dt_to,
            )
            emp_leaves = hr_leaves.browse(emp_leaves_ids)
            overtime_leaves = emp_leaves.filtered(
                lambda l: l.holiday_status_id.overtime_deductible
            ).mapped("overtime_id")
            leave_hours_dur = sum(overtime_leaves.mapped("duration")) or 0.0
            if emp_leaves and not overtime_leaves:
                leave_hours_dur = -1 * required_hours

            record.duration = logged_hours - required_hours - leave_hours_dur
