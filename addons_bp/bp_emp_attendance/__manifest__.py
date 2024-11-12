# © 2023 bloopark systems (<http://bloopark.de>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Employee Attendance & Extra Hours",
    "sequence": 20,
    "version": "1.0.0",
    "category": "Human Resources/Attendances",
    "author": "bloopark systems GmbH & Co. KG",
    "website": "http://www.bloopark.de",
    "license": "LGPL-3",
    "depends": [
        "hr_attendance",
        "hr_holidays_attendance",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "data": [
        # security files
        "security/ir.model.access.csv",
        "security/attendance_security.xml",
        # Wizard files
        "wizard/hr_attendance_extra_hours_wizard.xml",
        # Views files
        "views/hr_attendance_view.xml",
        "views/hr_employee.xml",
        "views/hr_leave_views.xml",
        "views/hr_attendance_overtime_views.xml",
        # Data files
        "data/attendance_data.xml",
        # Report files
        "report/hr_custom_report_attendance_views.xml",
    ],
    "demo": [],
}
