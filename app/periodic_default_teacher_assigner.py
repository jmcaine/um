
from datetime import datetime

import sqlite3

dbc = sqlite3.connect('um_13.db', isolation_level = None)
dbc.row_factory = sqlite3.Row

users = '''
	select user.id, person.first_name, person.last_name, email.email
	from user
	join person on user.person = person.id
	join email on email.person = person.id
	where user.active = 1
'''

k_datetime_format = '%Y-%m-%d %H:%M:%SZ'
k_date_format = '%Y-%m-%d'

k_campus = '2' # TODO: kludge!
k_ay = '6' # TODO: kludge!

def run():
	w = dbc.execute(f'select week from academic_calendar where date >= ? and campus = {k_campus} and academic_year = {k_ay} limit 1', (datetime.utcnow().strftime(k_date_format),)).fetchone()
	dbc.execute('''
			update class_teacher_sub set teacher = 
			(select enrollment.person from class_teacher_sub as cts
			join class_instance on class_instance.id = cts.class_instance
			join enrollment on enrollment.class_instance = class_instance.id and enrollment.section = cts.section
			where cts.id = class_teacher_sub.id and enrollment.teacher is not null and enrollment.teacher != 0)
			where teacher is null and week = ?
		''', (w['week'],))
	print(f"Updated teacher/subs for week {w['week']}")


if __name__ == '__main__':
	run()
