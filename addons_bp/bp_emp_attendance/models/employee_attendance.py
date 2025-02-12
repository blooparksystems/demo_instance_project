# © 2023 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import date, datetime, timedelta

import pytz
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.tools import Markup



class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    net_working_time = fields.Float(copy=False)
    employee_break_time = fields.Float(copy=False, string='Deducted Time')
    employee_extra_hours = fields.Float(copy=False)
    worked_hours = fields.Float(
        compute="_compute_de_worked_hours",
        store=True,
    )

    def _update_overtime_hours(self, over_hours):
        self.write({'worked_hours': over_hours})

    @api.model_create_multi
    def create(self, vals):
        res = super().create(vals)
        for record in res:
            record.action_recompute_worked_hours()
            record.action_update_overtime()
        return res

    def write(self, vals):
        for attendance in self:
            if (attendance.check_in and vals.get("check_in")) or (
                attendance.check_out and vals.get("check_out")
            ):
                attendance.action_log_employee_message(
                    old_values=attendance.read()[0],
                    new_values=vals,
                )

        res = super().write(vals)
        my_list_set = {
            "employee_id",
            "check_in",
            "check_out",
            "employee_extra_hours",
        }
        my_dict_set = set(vals)
        if my_list_set.intersection(my_dict_set):
            self.action_recompute_worked_hours()
            self.action_update_overtime()
        return res

    @api.depends(
        "net_working_time",
        "employee_break_time",
        "employee_extra_hours",
    )
    def _compute_de_worked_hours(self):
        """This method implemented to replace odoo standard calculation.

            From (check out - check_in)
            To → employee_extra_hours + (net_working_time - employee_break_time)

        and also to prevent override/edit odoo from another modules,
        that's why we added new method name _compute_de_worked_hours
        """
        for attendance in self:
            net = attendance.net_working_time
            break_time = attendance.employee_break_time
            employee_extra_hours = attendance.employee_extra_hours
            attendance.worked_hours = employee_extra_hours + (net - break_time)

    def action_recompute_worked_hours(self):
        """Test break/net work time calculation is correctly computed If employee has
        only 1 record check in/out in same day: case 1: working hours less than 6:00 h.

                → break_time should be (00:00)
            case 2: working hours between than 6:00h ~ 6:30h
                → break_time = (check_out - check_in) - 6
            case 3: working hours more than 6:30 h
                → break_time = 00:30 hh:mm

        Else employee logged many record per day:
            case 1: total day working hours less than 6:00 h
                → break_time should be (00:00)
            case 2: total day working hours between than 6:00h ~ 6:30h
                → break_time = (sum_working_time - 6 - sum_break_time_before)
            case 3: total day working hours more than 6:30 h
                → break_time = 0.75 - sum_break_time_before
        """
        for attendance in self:
            check_in = attendance.check_in
            check_out = attendance.check_out
            employee_break_time = 0.0
            net_working_time = 0.0
            if (check_out and check_in) and (check_out > check_in):
                tz = pytz.timezone(attendance.employee_id.tz or "UTC")
                start_naive = check_in.astimezone(tz).replace(
                    hour=0,
                    minute=0,
                    second=0,
                )
                end_naive = check_in.astimezone(tz).replace(
                    hour=23,
                    minute=59,
                    second=59,
                )

                # If employee logged his time in normal day
                last_attendance = self.sudo().search(
                    [
                        ("employee_id", "=", attendance.employee_id.id),
                        ("check_in", ">=", start_naive),
                        ("check_out", "<=", end_naive),
                        ("check_out", "<=", attendance.check_in),
                        ("id", "not in", attendance.ids),
                    ],
                    order="check_out desc",
                    limit=1,
                )
                attendance_before = self.sudo().search(
                    [
                        ("employee_id", "=", attendance.employee_id.id),
                        ("check_in", ">=", start_naive),
                        ("check_out", "<=", end_naive),
                        ("check_out", "<=", attendance.check_in),
                        ("id", "not in", attendance.ids),
                    ],
                    order="check_out desc",
                )
                attendance_after = self.sudo().search(
                    [
                        ("employee_id", "=", attendance.employee_id.id),
                        ("check_in", ">=", attendance.check_in),
                        ("check_out", "<=", end_naive),
                        ("id", "not in", attendance.ids),
                    ],
                    order="check_out desc",
                    limit=1,
                )
                if attendance_after:
                    attendance_after.action_recompute_worked_hours()

                if not last_attendance:
                    net_working_time = self.get_diff_min(
                        check_in=check_in,
                        check_out=check_out,
                    )

                    if net_working_time > 9:
                        employee_break_time = 0.75

                    elif 6.5 < net_working_time <= 9:
                        employee_break_time = 0.50

                    elif 6 < net_working_time <= 6.5:
                        employee_break_time = net_working_time - 6

                elif len(attendance_before) >= 1:
                    net_working_time = self.get_diff_min(
                        check_in=check_in,
                        check_out=check_out,
                    )
                    sum_working_time = (
                        sum(attendance_before.mapped("net_working_time"))
                        + net_working_time
                    )
                    current = attendance
                    total_break_time = 0
                    for record in attendance_before:
                        total_break_time += self.get_diff_min(
                            record.check_out, current.check_in
                        )
                        current = record

                    for record in attendance_before:
                        record.employee_break_time = 0

                    if sum_working_time > 9 and total_break_time < 0.75:
                        employee_break_time = 0.75 - total_break_time
                    elif 6.5 < sum_working_time <= 9.0 and total_break_time <= 0.5:
                        employee_break_time = 0.5 - total_break_time

                    elif (6 <= sum_working_time <= 6.5) and (
                        total_break_time < (sum_working_time - 6)
                    ):
                        employee_break_time = sum_working_time - 6 - total_break_time
                    elif sum_working_time > 9 and total_break_time > 0.75:

                        net_working_time = net_working_time
                        employee_break_time = 0

            attendance.net_working_time = net_working_time
            attendance.employee_break_time = employee_break_time

    @api.model
    def get_diff_min(self, check_in, check_out):
        """This method implemented to calculate diff between and dates in minutes.

        :param check_in: check in datetime
        :param check_out: check out datetime
        :return: diff in minutes (check_out - check_in)
        :rtype: float
        """
        diff = check_out - check_in
        diff_seconds = diff.total_seconds()
        value = diff_seconds / 3600.0
        return value

    def action_update_overtime(self):
        overtime = self.env["hr.attendance.overtime"].sudo()
        for rec in self:
            date_start = rec.check_in.date()
            date_end = date_start + relativedelta(days=1)
            day_overtime = overtime.search(
                [
                    ("employee_id", "=", rec.employee_id.id),
                    ("date", ">=", date_start),
                    ("date", "<", date_end),
                    ("adjustment", "=", False),
                ]
            )
            day_overtime.action_update_day_overtime()
            if not day_overtime:
                self.env["hr.attendance.overtime"].sudo().with_context(
                    {
                        'worked_hours': rec.worked_hours,
                    }
                ).create(
                    {
                        "employee_id": rec.employee_id.id,
                        "adjustment": False,
                        "date": date_start,
                        "duration": 0,
                    }
                )

    def action_log_employee_message(self, old_values, new_values):
        employee_id = (
            new_values.get("employee_id") or old_values.get("employee_id")[0]
            if old_values.get("employee_id")
            else False
        )

        check_in = old_values.get("check_in") or new_values.get("check_in")
        new_check_in = new_values.get("check_in") or False

        check_out = old_values.get("check_out") or new_values.get("check_out")
        new_check_out = new_values.get("check_out") or False

        if employee_id and (new_check_in or new_check_out):
            check_in = self.get_datetime_context_timestamp(check_in)
            new_check_in = self.get_datetime_context_timestamp(new_check_in)
            check_out = self.get_datetime_context_timestamp(check_out)
            new_check_out = self.get_datetime_context_timestamp(new_check_out)

            employee = self.env["hr.employee"].sudo().browse(employee_id)
            body = Markup (f"{self.env.user.name} changed Attendance Data: <br/>")
            if new_check_in != check_in and new_check_in:
                body += Markup(f"<li><b>Check in : </b>{check_in} → {new_check_in} <br/></li>")
            if new_check_out != check_out and new_check_out:
                body += Markup(
                    f"<li><b>Check out : </b>{check_out} → {new_check_out} <br/></li>"
                )
            employee.message_post(body=body)

    def get_datetime_context_timestamp(self, data):
        """
        :param data: datetime or sting datetime
        :return: datetime with time stamp
        """
        if not data:
            return ""
        datetime_data = fields.Datetime.from_string(str(data))
        return fields.Datetime.to_string(
            fields.Datetime.context_timestamp(self, datetime_data)
        )

    @api.model
    def action_create_missing_attendance(self, year=False):
        if not year:
            year = int(date.today().year)
        date_from = date(year=int(year), month=1, day=1)
        date_to = date.today()
        range_date = range(int((date_to - date_from).days))
        dates_list = [date_from + timedelta(n) for n in range_date]
        attendance_list = []

        for ydate in dates_list:
            employees = (
                self.env["hr.employee"]
                .sudo()
                .search(
                    [
                        ("check_daily_attendance", "=", True),
                        ("first_contract_date", "<=", ydate),
                    ]
                )
            )
            check_in = datetime.combine(ydate, datetime.min.time())
            check_out = datetime.combine(ydate, datetime.max.time())
            for emp in employees:
                work_data = emp.resource_calendar_id.get_work_duration_data(
                    from_datetime=check_in,
                    to_datetime=check_out,
                    compute_leaves=True,
                )
                leaves = emp.check_employee_vacation(
                    date_from=check_in,
                    date_to=check_out,
                )

                if work_data.get("hours") and not leaves:
                    attendance_day = self.sudo().search(
                        [
                            ("employee_id", "=", emp.id),
                            ("check_in", ">=", check_in),
                            ("check_out", "<=", check_out),
                        ],
                        order="check_out desc",
                    )
                    if not attendance_day:
                        attendance_list.append(
                            {
                                "employee_id": emp.id,
                                "check_in": check_in.replace(hour=4),
                                "check_out": check_in.replace(hour=4),
                            }
                        )
        self.sudo().create(attendance_list)
