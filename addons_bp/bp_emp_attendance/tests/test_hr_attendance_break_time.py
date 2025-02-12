from datetime import datetime

import pytz
from odoo.tests import new_test_user
from odoo.tests.common import TransactionCase


def tz_datetime(year, month, day, hour, minute):
    tz = pytz.timezone("Europe/Brussels")
    return (
        tz.localize(datetime(year, month, day, hour, minute))
        .astimezone(pytz.utc)
        .replace(tzinfo=None)
    )


class TestHrAttendance(TransactionCase):
    """Test for break time calculation."""

    def setUp(self):
        super().setUp()
        self.employee_user = new_test_user(
            self.env,
            login="bp",
            groups="base.group_user",
        )
        self.employee_login = self.env["hr.employee"].create(
            {
                "name": "Martin Holz",
                "pin": "4477",
                "user_id": self.employee_user.id,
            }
        )

    def get_attendance_data(self, attendance_id):
        attendance = self.env["hr.attendance"].browse(int(attendance_id))
        return {
            "net_working_time": round(attendance.net_working_time, 2),
            "employee_break_time": round(attendance.employee_break_time, 2),
            "worked_hours": round(attendance.worked_hours, 2),
        }

    def test_employee_checkout(self):
        # Make sure the attendance of the employee already checked out
        assert self.employee_login.attendance_state == "checked_out"

    def test_attendance_case_1(self):
        """Test break/net work time calculation is correctly computed if employee has
        only one attendance log record."""

        # Case 1: Employee total working hours less than 6
        attendance = self.env["hr.attendance"].create(
            {
                "employee_id": self.employee_login.id,
                "check_in": tz_datetime(2022, 4, 7, 8, 0),
                "check_out": tz_datetime(2022, 4, 7, 12, 0),
            }
        )
        attendance_data = self.get_attendance_data(attendance_id=attendance.id)
        net = attendance_data.get("net_working_time")
        break_time = attendance_data.get("employee_break_time")
        worked_hours = net - break_time
        assert net == 4.0
        assert break_time == 0.0
        assert round(attendance.worked_hours, 2) == worked_hours

        # Case 2: Employee total working hours between 6:15 less than 6:30
        attendance.check_out = tz_datetime(2022, 4, 7, 14, 15)
        attendance_data = self.get_attendance_data(attendance_id=attendance.id)
        net = attendance_data.get("net_working_time")
        break_time = attendance_data.get("employee_break_time")
        worked_hours = net - break_time

        assert net == 6.25
        assert break_time == 0.25
        assert round(attendance.worked_hours, 2) == worked_hours

        # Case 4: Employee total working hours greater than 06:30
        attendance.check_out = tz_datetime(2022, 4, 7, 16, 15)
        attendance_data = self.get_attendance_data(attendance_id=attendance.id)
        net = attendance_data.get("net_working_time")
        break_time = attendance_data.get("employee_break_time")
        worked_hours = net - break_time

        assert net == 8.25
        assert break_time == 0.5
        assert round(attendance.worked_hours, 2) == worked_hours

    def test_attendance_case_2(self):
        """Test break/net work time calculation is correctly computed if employee has
        multi check in/out in same day."""
        # Case 1
        attendance_1 = self.env["hr.attendance"].create(
            {
                "employee_id": self.employee_login.id,
                "check_in": tz_datetime(2022, 4, 7, 8, 0),
                "check_out": tz_datetime(2022, 4, 7, 9, 0),
            }
        )
        attendance_data = self.get_attendance_data(
            attendance_id=attendance_1.id,
        )
        net = attendance_data.get("net_working_time")
        break_time = attendance_data.get("employee_break_time")
        worked_hours = net - break_time

        assert net == 1.00
        assert break_time == 0.0
        assert round(attendance_1.worked_hours, 2) == worked_hours

        # Case 2
        attendance_2 = self.env["hr.attendance"].create(
            {
                "employee_id": self.employee_login.id,
                "check_in": tz_datetime(2022, 4, 7, 9, 00),
                "check_out": tz_datetime(2022, 4, 7, 17, 00),
            }
        )
        attendance_data = self.get_attendance_data(
            attendance_id=attendance_2.id,
        )
        net = attendance_data.get("net_working_time")
        break_time = attendance_data.get("employee_break_time")
        worked_hours = net - break_time
        assert net == 8.00
        assert break_time == 0.5
        assert round(attendance_2.worked_hours, 2) == worked_hours

        # Case 3: Employee total working hours above 9hrs
        attendance_3 = self.env["hr.attendance"].create(
            {
                "employee_id": self.employee_login.id,
                "check_in": tz_datetime(2022, 4, 8, 8, 00),
                "check_out": tz_datetime(2022, 4, 8, 18, 00),
            }
        )
        attendance_data = self.get_attendance_data(
            attendance_id=attendance_3.id,
        )
        attendance_3.action_recompute_worked_hours()
        net = attendance_data.get("net_working_time")
        break_time = attendance_data.get("employee_break_time")
        worked_hours = net - break_time
        assert net == 10
        assert break_time == 0.75  # 45 min
        assert round(attendance_3.worked_hours, 2) == worked_hours

        # Case 4: Employee total working hours exact 9hr
        attendance_3.write(
            {
                "check_out": tz_datetime(2022, 4, 8, 17, 00),
            }
        )
        attendance_data = self.get_attendance_data(
            attendance_id=attendance_3.id,
        )
        net = attendance_data.get("net_working_time")
        break_time = attendance_data.get("employee_break_time")
        worked_hours = net - break_time
        assert net == 9.0
        assert break_time == 0.5  # 30 min
        assert round(attendance_3.worked_hours, 2) == worked_hours
