# © 2023 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from collections import namedtuple
from datetime import datetime, timedelta

from odoo import _, api, fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    is_employee_officer = fields.Boolean(
        compute="_compute_is_employee_officer",
    )
    check_daily_attendance = fields.Boolean(
        related='employee_id.check_daily_attendance'
    )
    send_missing_attendance_mail = fields.Boolean(
        related='employee_id.send_missing_attendance_mail'
    )

    def hr_attendance_report_action(self):
        return self.employee_id.hr_attendance_report_action()

    def _compute_is_employee_officer(self):
        login_user = self.env.user
        for rec in self.sudo():
            is_employee_officer = self.env.user.has_group(
                "hr_attendance.group_hr_attendance_user"
            )
            employee_user = rec.employee_id.user_id

            if not is_employee_officer and (login_user.id == employee_user.id):
                is_employee_officer = True

            rec.is_employee_officer = is_employee_officer


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    check_daily_attendance = fields.Boolean()
    send_missing_attendance_mail = fields.Boolean(
        string="Send Daily Mail For Missing Attendance",
        default=False,
    )

    def hr_attendance_report_action(self):
        self.ensure_one()
        return self.env["ir.actions.actions"]._for_xml_id(
            "bp_emp_attendance.hr_custom_own_report_attendance_action"
        )

    def action_open_extra_hours_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Add/Deduct Employee Working Hours"),
            "res_model": "hr.attendance.extra.hours",
            "views": [(False, "form")],
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_employee_id": self.id,
            },
        }

    @api.model
    def cron_missing_attendance(self):
        date_now = datetime.now()
        dt_from = datetime.combine(date_now, datetime.min.time())
        dt_to = datetime.combine(date_now, datetime.max.time())
        attendance = self.env["hr.attendance"].sudo()
        employees = self.sudo().search(
            [
                ("parent_id", "!=", False),
                ("check_daily_attendance", "=", True),
            ]
        )
        employee_attendance = attendance.search(
            [
                ("check_in", ">=", dt_from),
                ("check_out", "<=", dt_to),
            ],
            order="check_out desc",
        ).mapped("employee_id")
        employees_to_log = list(set(employees) ^ set(employee_attendance))
        attendance_list = []
        check_dt = date_now.replace(
            hour=6,
            minute=0,
            second=0,
            microsecond=0,
        )
        manager_template = self.env.ref(
            "bp_emp_attendance.email_template_manager_daily_attendance",
            raise_if_not_found=False,
        )
        employee_template = self.env.ref(
            "bp_emp_attendance.email_template_employee_daily_attendance",
            raise_if_not_found=False,
        )

        for employee in employees_to_log:
            work_data = employee.resource_calendar_id.get_work_duration_data(
                from_datetime=dt_from,
                to_datetime=dt_to,
                compute_leaves=True,
            )
            leaves = employee.check_employee_vacation(
                date_from=dt_from,
                date_to=dt_to,
            )

            if work_data.get("hours") and not leaves:
                attendance_list.append(
                    {
                        "employee_id": employee.id,
                        "check_in": check_dt,
                        "check_out": check_dt,
                    }
                )
                if employee.send_missing_attendance_mail:
                    manager_template.sudo().send_mail(
                        employee.id,
                        force_send=True,
                    )
                    employee_template.sudo().send_mail(
                        employee.id,
                        force_send=True,
                    )
        attendance.create(attendance_list)

    def check_employee_vacation(self, date_from, date_to):
        self.ensure_one()
        hr_leaves = self.env["hr.leave"].sudo()
        holidays = hr_leaves.search(
            [
                ("employee_id", "=", self.id),
                ("state", "=", "validate"),
            ]
        )

        overlap_list = []
        Range = namedtuple("Range", ["start", "end"])
        r2 = Range(start=date_from, end=date_to)
        for line in holidays:
            r1 = Range(start=line.date_from, end=line.date_to)
            latest_start = max(r1.start, r2.start)
            earliest_end = min(r1.end, r2.end)
            delta = (earliest_end - latest_start).days + 1
            overlap = max(0, delta)
            if overlap and (line not in overlap_list):
                overlap_list.append(line.id)
        return overlap_list

    def _update_previous_attendance_action(self):
        """Function for server action to update previous attendances for the
        employee."""
        dates = []
        date_now = datetime.now()
        # Starting date to update attendance record
        date_start = datetime(2023, 8, 15)
        attendance = self.env["hr.attendance"].sudo()

        while date_start:
            if date_start != datetime.combine(date_now, datetime.min.time()):
                dates.append(date_start)
                date_start = date_start + timedelta(days=1)
            else:
                date_start = False

        for each_date in dates:
            dt_from = datetime.combine(each_date, datetime.min.time())
            dt_to = datetime.combine(each_date, datetime.max.time())

            for employee in self:
                employee_attendance = attendance.search(
                    [
                        ("check_in", ">=", dt_from),
                        ("check_out", "<=", dt_to),
                        ("employee_id", "=", employee.id),
                    ],
                    order="check_out desc",
                    limit=1,
                )
                employee_attendance.action_recompute_worked_hours()
