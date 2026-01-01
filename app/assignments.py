__author__ = 'J. Michael Caine'
__copyright__ = '2025'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from . import db
from . import fields
from . import html
from . import shared
from . import task
from . import text
from . import valid
from . import ws

from .assignments_const import *


l = logging.getLogger(__name__)


async def authorize_admin(hd):
	return hd.admin

async def authorize_sub_manager(hd):
	return hd.sub_manager

async def authorize_logged_in(hd):
	return hd.uid


k_assignments_container_id = 'assignments_container'

@ws.handler(auth_func = authorize_logged_in)
async def main(hd, reverting = False):
	if task.just_started(hd, main):
		await ws.send_sub_content(hd, 'topbar_container', html.assignments_topbar(hd.admin))
		await ws.send_content(hd, 'content', html.container(text.loading_assignments, k_assignments_container_id))

	filt = _get_set_state(hd, 'filt', Filter.current)
	subj_id = _get_set_state(hd, 'subj_id')

	person_id = hd.payload.get('person_id', 0) if hd.admin else None
	uid = (await db.get_person_user(hd.dbc, person_id))['id'] if hd.admin and person_id else hd.uid

	fs = hd.task.state.get('filtersearch', {})
	assignments = await db.get_assignments(hd.dbc, uid,
							like = fs.get('searchtext', ''),
							filt = filt,
							subj_id = subj_id,
							limit = None if fs.get('dont_limit', False) else db.k_assignment_resultset_limit)
	subjects = set([html.DropselOption(a['subject_name'], a['subject_id']) for a in assignments])
	await ws.send_sub_content(hd, 'filter_container', html.assignments_filter(filt, subjects, subj_id))

	tsk = 'show_assignments_print' if filt == Filter.all and hd.admin else 'show_assignments'
	#WISH (see comment on next line): await ws.send_sub_content(hd, k_assignments_container_id, html.assignments(assignments))
	await ws.send_content(hd, tsk, html.assignments(assignments)) # TODO would prefer the above ("WISH"), to centralize k_assignments_container_id, but have to refactor the send_content semantics to handle sub_content hide_dialog() behavior....


@ws.handler(auth_func = authorize_logged_in)
async def mark_complete(hd):
	await db.mark_assignment_complete(hd.dbc, hd.uid, int(hd.payload['assignment_id']), int(hd.payload['enrollment_id']), bool(hd.payload['checked'])) # TODO: handle return value (error)!


@ws.handler(auth_func = authorize_admin)
async def classes(hd, reverting = False):
	if task.just_started(hd, classes):
		await ws.send_sub_content(hd, 'topbar_container', html.common_topbar())
		await ws.send_sub_content(hd, 'filter_container', html.classes_mainbar())

	ays = await db.get_academic_years(hd.dbc)

	ay = _get_set_state(hd, 'academic_year', ays[0]['id'])
	fs = hd.task.state.get('filtersearch', {})
	r = await db.get_classes(hd.dbc,
							academic_year = ay,
							active = not fs.get('show_inactives', False),
							like = fs.get('searchtext', ''),
							get_enrollment_count = True,
							limit = None if fs.get('dont_limit', False) else db.k_default_resultset_limit)
	#await ws.send_sub_content(hd, 'filter_container', html.assignments_filter(filt, subjects, subj_id))

	await ws.send_content(hd, 'content', html.classes_page(r))


@ws.handler(auth_func = authorize_admin)
async def class_students(hd, reverting = False):
	container = 'enrollments_table_container'
	if task.just_started(hd, class_students, ('academic_year',)) or reverting:
		hd.task.state['class_instance_id'] = int(hd.payload.get('id'))
		await ws.send_content(hd, 'dialog', html.table_dialog(await class_students_table(hd), container, 'assignments', 'class_students'))
	elif not await task.finished(hd): # dialog-box could have been "closed"
		await ws.send_content(hd, 'sub_content', await class_students_table(hd), container = container)


async def class_students_table(hd):
	fs = hd.task.state.get('filtersearch', {})
	limit = None if fs.get('dont_limit', False) else db.k_default_resultset_limit
	cid = hd.task.state['class_instance_id']
	enrollments, nons = await db.get_enrollments(hd.dbc, cid,
													limit = limit,
													like = fs.get('searchtext', ''),
													include_others = True)
	sections = await db.get_class_sections(hd.dbc, cid)
	return html.class_enrollments_table(enrollments, nons, 'add_enrollment', 'remove_enrollment', limit, sections)


async def _class_setter(hd, data):
	name = data['name']
	await db.set_class(hd.dbc, hd.task.state['db_data']['id'], name, html.checkbox_value(data, 'active'))
	await ws.send_content(hd, 'banner', html.info(text.change_detail_success.format(change = f'"{name}"')))


@ws.handler(auth_func = authorize_admin)
async def class_detail(hd, reverting = False):
	return await shared.edit_detail(hd, class_detail, reverting, db.get_class, text.clss, fields.CLASS, _class_setter)


async def _announce_enrollment_change(hd, message, pid):
	person = await db.get_person(hd.dbc, pid, 'first_name, last_name')
	await ws.send_content(hd, 'detail_banner', html.info(message.format(name = f"{person['first_name']} {person['last_name']}")))

@ws.handler(auth_func = authorize_admin)
async def remove_enrollment(hd):
	eid = int(hd.payload['enrollment_id'])
	pid = await db.get_enrollment_person_id(hd.dbc, eid)
	await db.remove_enrollment(hd.dbc, eid)
	await _announce_enrollment_change(hd, text.removed_person_from_class, pid)
	await hd.task.handler(hd) # make current handler re-draw (the table)

@ws.handler(auth_func = authorize_admin)
async def add_enrollment(hd):
	pid = int(hd.payload['person_id'])
	s = hd.task.state
	await db.add_enrollment(hd.dbc, pid, s['class_instance_id'], s['academic_year'])
	await _announce_enrollment_change(hd, text.added_person_to_class, pid)
	hd.task.state['filtersearch']['searchtext'] = '' # reset for next filter query
	await hd.task.handler(hd) # make current handler re-draw (the table)

@ws.handler(auth_func = authorize_admin)
async def change_enrollment_section(hd):
	await _set_enrollment_x(hd, db.change_enrollment_section, text.changed_persons_class_section)

@ws.handler(auth_func = authorize_admin)
async def set_enrollment_audit(hd):
	await _set_enrollment_x(hd, db.change_enrollment_audit, text.changed_persons_class_audit_status)

@ws.handler(auth_func = authorize_admin)
async def set_enrollment_teacher(hd):
	await _set_enrollment_x(hd, db.change_enrollment_teacher, text.changed_persons_class_teacher_status)

async def _set_enrollment_x(hd, fn, message):
	eid = int(hd.payload['id'])
	await fn(hd.dbc, eid, int(hd.payload['value']))
	pid = await db.get_enrollment_person_id(hd.dbc, eid)
	await _announce_enrollment_change(hd, message, pid)
	# no need to redraw - change is already visible

def _get_set_state(hd, key, default = None):
	# prefer filt sent in payload, then filt already recorded, and, finally, if nothing, default to viewing `current` assignments (only)
	hd.task.state[key] = hd.payload.get(key, hd.task.state.get(key, default))
	return hd.task.state[key]



@ws.handler(auth_func = authorize_sub_manager)
async def teachers_subs(hd, reverting = False):
	js = task.just_started(hd, teachers_subs)
	programs = await db.get_programs(hd.dbc)
	if js:
		await ws.send_sub_content(hd, 'topbar_container', html.common_topbar())
		await ws.send_sub_content(hd, 'filter_container', html.teachers_subs_mainbar(programs)) # TODO: add academic_year, program, and week selectors! (underway! above!)


	program = _get_set_state(hd, 'program', programs[0]['id'])
	ay = _get_set_state(hd, 'academic_year', (await db.get_academic_years(hd.dbc))[0]['id']) #TODO: use user's school config....
	week = _get_set_state(hd, 'week')
	fs = hd.task.state.get('filtersearch', {})
	week_dates, tss = await db.get_teachers_subs(hd.dbc, program, ay, week,
							limit = None, #if fs.get('dont_limit', False) else db.k_default_resultset_limit,
							like = fs.get('searchtext', ''))
	await ws.send_content(hd, 'content', html.teachers_subs_page(week_dates, tss))

@ws.handler(auth_func = authorize_sub_manager)
async def choose_teacher_sub(hd, reverting = False):
	container = 'teachers_container'
	ctsid = int(_get_set_state(hd, 'class_teacher_sub_id'))
	if task.just_started(hd, choose_teacher_sub, ('class_teacher_sub_id',)):
		await ws.send_content(hd, 'dialog', html.table_dialog(await teachers_table(hd), container))
	elif not await task.finished(hd, False): # execute_finish=False because we don't want teachers_subs() to execute before we db.set_teacher_sub(), below!
		await ws.send_content(hd, 'sub_content', await teachers_table(hd), container = container)
	else: # finished; get new value (from client and set to db)...
		if pid := int(hd.payload['person_id']):
			await db.set_teacher_sub(hd.dbc, ctsid, pid)
			person = await db.get_person(hd.dbc, pid)
			await ws.send_content(hd, 'banner', html.info(text.teacher_sub_assignment_success.format(name = f"{person['first_name']} {person['last_name']}")))
		await task.finish(hd) # we told finished() not to execute_finish, so we have to do it now; now it's safe, since we've now called db.set_teacher_sub()

async def teachers_table(hd):
	fs = hd.task.state.get('filtersearch', {})
	limit = None if fs.get('dont_limit', False) else db.k_default_resultset_limit
	teachers = await db.get_teachers(hd.dbc, limit, fs.get('searchtext', ''))
	return html.teachers_table(teachers, 'assignments', 'choose_teacher_sub', limit)



@ws.handler(auth_func = authorize_logged_in)
async def finances(hd, reverting = False):
	if task.just_started(hd, finances):
		await ws.send_sub_content(hd, 'topbar_container', html.common_topbar())
		parents = await db.get_teachers(hd.dbc) if hd.admin or (await db.authorized(hd.dbc, hd.uid, 'accountant')) else None
		await ws.send_sub_content(hd, 'filter_container', html.financials_mainbar(parents))

	ay = _get_set_state(hd, 'academic_year', (await db.get_academic_years(hd.dbc))[0]['id']) #TODO: use user's school config....
	guardian_id = int(_get_set_state(hd, 'guardian', (await db.get_user_person(hd.dbc, hd.uid))['id']))
	guardian = await db.get_person(hd.dbc, guardian_id)
	enrollments = await db.get_family_enrollments(hd.dbc, guardian_id)
	costs = await db.get_family_costs(hd.dbc, guardian_id)
	guardian['pay_projected'] = await db.get_teacher_pay_projected(hd.dbc, ay, guardian_id)
	guardian['pay_so_far'] = await db.get_teacher_pay_so_far(hd.dbc, ay, guardian_id)
	if spouse := await db.get_person_spouse(hd.dbc, guardian_id):
		spouse['pay_projected'] = await db.get_teacher_pay_projected(hd.dbc, ay, spouse['id'])
		spouse['pay_so_far'] = await db.get_teacher_pay_so_far(hd.dbc, ay, spouse['id'])
	week = await db.get_week(hd.dbc)
	await ws.send_content(hd, 'content', html.financials_page(week, enrollments, costs, guardian, spouse))
