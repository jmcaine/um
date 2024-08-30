__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from . import db
from . import fields
from . import html
from . import task
from . import text
from . import valid
from . import ws


l = logging.getLogger(__name__)


async def authorize(hd, user_id):
	return await db.authorized(hd.dbc, user_id, 'admin')


async def handle_invalid(hd, message):
	await ws.send_content(hd, 'banner', html.error(message))



@ws.handler(auth_func = authorize)
async def admin_screen(hd):
	#TODO! Implement!  For now, just go to admin_users page...
	await users(hd) # TODO!! ^^



@ws.handler(auth_func = authorize)
async def users(hd, reverting = False):
	if reverting:
		await ws.send(hd, 'hide_dialog')
	if not task.started(hd, users):
		await ws.send_content(hd, 'content', html.users_page(await db.get_users(hd.dbc)))
	else:
		u = await db.get_users(hd.dbc, like = hd.task.state.get('filtersearch_text', ''), active = not hd.task.state.get('filtersearch_include_extra', False))
		await ws.send_content(hd, 'sub_content', html.user_table(u), container = 'user_table')


#TODO!
@ws.handler(auth_func = authorize)
async def admin_messages(hd):
	if not supertask_started(hd, admin_messages):
		hd.state['filtersearch_text'] = '' # clear old searchtext if we're starting anew here
	#TODO!




@ws.handler(auth_func = authorize)
async def user_detail(hd):
	if not task.started(hd, user_detail):
		hd.task.state['user'] = await db.get_user(hd.dbc, int(hd.payload.get('id')))
		await ws.send_content(hd, 'dialog', html.dialog2(text.user, fields.USER, hd.task.state['user']))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.USER, handle_invalid):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		un = data['username']
		if un != hd.task.state['user']['username'] and await db.username_exists(hd.dbc, un):
			await ws.send_content(hd, 'detail_banner', html.error(text.Valid.username_exists))
			return # finished
		#else all good, move on!
		data['active'] = html.checkbox_value(data, 'active')
		await db.update_user(hd.dbc, hd.task.state['user']['id'], fields.USER.keys(), data)
		await task.finish(hd)
		await ws.send_content(hd, 'banner', html.info(text.change_detail_success.format(change = f'"{un}"')))


@ws.handler(auth_func = authorize)
async def person_detail(hd):
	if not task.started(hd, user_detail):
		hd.task.state['person'] = await db.get_person(hd.dbc, int(hd.payload.get('id')))
		await ws.send_content(hd, 'dialog', html.dialog2(text.person, fields.PERSON, hd.task.state['user'], more_func = 'more_person_detail'))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.PERSON, handle_invalid):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		first, last = data['first_name'], data['last_name']
		await db.set_person(hd.dbc, hd.task.state['person']['id'], first, last)
		await task.finish(hd)
		await ws.send_content(hd, 'banner', html.info(text.change_detail_success.format(change = f'{first} {last}')))

#TODO!
@ws.handler(auth_func = authorize)
async def more_person_detail(hd, banner = None):
	supertask_started(hd, more_person_detail) # not essential, as this task currently involves NO subtasks, but setting super is probably better than leaving it wherever it was
	id = hd.ststate['detail_got_data']['id']
	emails = await db.get_person_emails(hd.dbc, id)
	phones = await db.get_person_phones(hd.dbc, id)
	await send_task(hd, 'dialog', html.more_person_detail(emails, phones))
	if banner:
		await send_detail_banner(hd, html.info(banner))

#TODO!
@ws.handler(auth_func = authorize)
async def mpd_detail(hd):
	if not supertask_started(hd, mpd_detail):
		table = hd.ststate['mpd_detail_table'] = hd.payload['table']
		id = hd.payload.get('id', 0)
		cancel_button = html.cancel_to_mpd_button()
		match table:
			case 'email':
				data = await db.get_email(hd.dbc, id) if id else {'email': ''}
				await send_task(hd, 'dialog', html.dialog2(text.email, fields.EMAIL, data, alt_button = cancel_button))
			case 'phone':
				data = await db.get_phone(hd.dbc, id) if id else {'phone': ''}
				await send_task(hd, 'dialog', html.dialog2(text.phone, fields.PHONE, data, alt_button = cancel_button))
		data['id'] = id
		hd.ststate['mpd_got_data'] = data
	else:
		data = hd.payload
		table = hd.ststate['mpd_detail_table']
		person_id = hd.ststate['detail_got_data']['id']
		detail_id = hd.ststate['mpd_got_data']['id']
		match table:
			case 'email':
				if await _invalids(hd, data, fields.EMAIL):
					return # if there WERE invalids, bannar was already sent within
				#else all good, move on!
				if detail_id == 0:
					await db.add_email(hd.dbc, person_id, data['email'])
				else:
					await db.set_email(hd.dbc, detail_id, data['email'])
			case 'phone':
				if await _invalids(hd, data, fields.PHONE):
					return # if there WERE invalids, bannar was already sent within
				#else all good, move on!
				if detail_id == 0:
					await db.add_phone(hd.dbc, person_id, data['phone'])
				else:
					await db.set_phone(hd.dbc, detail_id, data['phone'])
		# Return to the original more-person-detail page, showing all phones and emails for the person:
		fn, ln = hd.ststate['detail_got_data']['first_name'], hd.ststate['detail_got_data']['last_name']
		await more_person_detail(hd, text.change_detail_success.format(change = f'{text.detail_for} "{fn} {ln}"'))

#TODO!
@ws.handler(auth_func = authorize)
async def delete_mpd(hd):
	data = hd.payload
	await db.delete_person_detail(hd.dbc, data['table'], data['id'])
	await more_person_detail(hd, text.deletion_succeeded)



@ws.handler(auth_func = authorize)
async def tags(hd, reverting = False):
	if reverting:
		await ws.send(hd, 'hide_dialog')
	if not task.started(hd, tags):
		t = await db.get_tags(hd.dbc, get_subscribers = True)
		await ws.send_content(hd, 'content', html.tags_page(t))
	else:
		t = await db.get_tags(hd.dbc,
								active = not hd.task.state.get('filtersearch_include_extra', False),
								like = hd.task.state.get('filtersearch_text', ''),
								get_subscribers = True)
		await ws.send_content(hd, 'sub_content', html.tag_table(t), container = 'tag_table')


@ws.handler(auth_func = authorize)
async def new_tag(hd):
	if not task.started(hd, new_tag):
		await ws.send_content(hd, 'dialog', html.dialog2(text.tag, fields.TAG))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.TAG, handle_invalid):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		name = data['name']
		await db.new_tag(hd.dbc, name, html.checkbox_value(data, 'active'))
		await task.finish(hd)
		await ws.send_content(hd, 'banner', html.info(text.added_tag_success.format(name = f'"{name}"')))

@ws.handler(auth_func = authorize) # TODO: change to user-level auth; users that create tags can edit those tags (perhaps only some users are even allowed to create tags; need concept of publicly-discoverable tags vs. admin-directed subscription management....)
async def tag_detail(hd):
	if not task.started(hd, tag_detail):
		hd.task.state['tag'] = await db.get_tag(hd.dbc, int(hd.payload.get('id')))
		await ws.send_content(hd, 'dialog', html.dialog2(text.tag, fields.TAG, hd.task.state['tag']))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.TAG, handle_invalid):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		name = data['name']
		await db.set_tag(hd.dbc, hd.task.state['tag']['id'], name, html.checkbox_value(data, 'active'))
		await task.finish(hd)
		await ws.send_content(hd, 'banner', html.info(text.change_detail_success.format(change = f'"{name}"')))


async def _get_users_and_nonusers(hd, tag_id):
	return await db.get_tag_users_and_nonusers(hd.dbc, tag_id, hd.task.state.get('filtersearch_text'))

@ws.handler(auth_func = authorize)
async def tag_users(hd):
	if not task.started(hd, tag_users):
		tag_id = int(hd.payload.get('tag_id'))
		hd.task.state['tag'] = await db.get_tag(hd.dbc, tag_id)
		users, nonusers = await _get_users_and_nonusers(hd, tag_id)
		await ws.send_content(hd, 'dialog', html.tag_users_and_nonusers(hd.payload.get('tag_name'), users, nonusers))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		await tag_users_table(hd)

async def tag_users_table(hd, banner = None):
	users, nonusers = await _get_users_and_nonusers(hd, int(hd.task.state['tag']['id']))
	await ws.send_content(hd, 'sub_content', html.tag_users_and_nonusers_table(hd.task.state['tag']['name'], users, nonusers), container = 'users_and_nonusers_table_container')
	if banner:
		await ws.send_content(hd, 'detail_banner', html.info(banner))

async def _remove_or_add_user_to_tag(hd, func, message):
	uid = int(hd.payload['user_id'])
	await func(hd.dbc, uid, hd.task.state['tag']['id'])
	username = await db.get_user(hd.dbc, uid, 'username')
	await tag_users_table(hd, html.info(message.format(username = username['username'], tag_name = hd.task.state['tag']['name'])))

@ws.handler(auth_func = authorize)
async def remove_user_from_tag(hd):
	await _remove_or_add_user_to_tag(hd, db.remove_user_from_tag, text.removed_user_from_tag)

@ws.handler(auth_func = authorize)
async def add_user_to_tag(hd):
	await _remove_or_add_user_to_tag(hd, db.add_user_to_tag, text.added_user_to_tag)


