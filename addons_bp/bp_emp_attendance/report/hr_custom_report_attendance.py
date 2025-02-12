# © 2023 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools


class HRAttendanceReport(models.Model):
    _name = "custom.hr.attendance.report"
    _description = "Attendance Report Custom"
    _auto = False

    employee_id = fields.Many2one("hr.employee", readonly=True)
    check_in = fields.Date("Check In", readonly=True)
    worked_hours = fields.Float("Hours Worked", readonly=True)
    overtime_hours = fields.Float("Extra Hours", readonly=True)
    department_id = fields.Many2one("hr.department", readonly=True)

    @api.model
    def _select(self):
        return """
            SELECT
                ovr.id,
                ovr.employee_id,
                ovr.check_in,
                worked_hours,
                department_id,
                ovr.overtime_hours
        """

    @api.model
    def _from(self):
        return """
            FROM(
                SELECT
                    id,
                    row_number() over (partition by employee_id, CAST(date AS DATE)) as ot_check,
                    employee_id,
                    worked_hours,
                    CAST(request_date as DATE) as check_in,
                    duration as overtime_hours
                FROM
                    hr_attendance_overtime

            ) as ovr
        """

    def _join(self):
        return """
            LEFT JOIN hr_employee ON hr_employee.id = ovr.employee_id
        """

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                %s
                %s
                %s
            )
        """
            % (
                self._table,
                self._select(),
                self._from(),
                self._join(),
            )
        )
