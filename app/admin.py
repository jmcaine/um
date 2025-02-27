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


async def handle_invalid(hd, message, banner):
	await ws.send_content(hd, banner, html.error(message))


@ws.handler(auth_func = authorize)
async def admin_screen(hd):
	#TODO! Implement!  For now, just go to admin_users page...
	await users(hd) # TODO!! ^^



@ws.handler(auth_func = authorize)
async def users(hd, reverting = False):
	if task.just_started(hd, users):
		await ws.send_content(hd, 'content', html.users_page(await db.get_users(hd.dbc)))
	else:
		u = await db.get_users(hd.dbc,
								 like = hd.task.state.get('filtersearch_text', ''),
								 active = not hd.task.state.get('filtersearch_include_extra', False))
		await ws.send_content(hd, 'sub_content', html.user_table(u), container = 'user_table_container')


@ws.handler(auth_func = authorize)
async def user_detail(hd, reverting = False):
	if reverting:
		await task.finish(hd) # just bump back another step - see person_detail 'reverting' note...
		return # nothing more to do here
	if task.just_started(hd, user_detail):
		user_id = int(hd.payload.get('id'))
		hd.task.state['user'] = await db.get_user(hd.dbc, user_id)
		await ws.send_content(hd, 'dialog', html.dialog2(text.user, fields.USER, hd.task.state['user'], more_func = f'admin.send_ws("user_tags", {{ user_id: {user_id} }})'))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.USER, handle_invalid, 'detail_banner'):
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
async def person_detail(hd, reverting = False):
	if reverting:
		await task.finish(hd) # just bump back another step - no value in returning to this name-edit dialog when name-editing was not the objective in the first place (email or phone number or something were); note that this is the RIGHT way to do it - we never want to "call back" (e.g., from more_person_detail() to users(), skipping this) for TWO reasons - 1) it would create a false and ever-growing task stack!, and 2) we don't necessarily know that, e.g., more_person_detail came from users() - it could have come from an individual user clicking somewhere to edit his/her own phones/emails, and then the need would be to wherever THEY came from.
		return # nothing more to do here
	if task.just_started(hd, person_detail):
		person_id = int(hd.payload.get('id'))
		hd.task.state['person'] = await db.get_person(hd.dbc, person_id)
		await ws.send_content(hd, 'dialog', html.dialog2(text.person, fields.PERSON, hd.task.state['person'], more_func = f'admin.send_ws("more_person_detail", {{ id: {person_id} }})'))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.PERSON, handle_invalid, 'detail_banner'):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		first, last = data['first_name'], data['last_name']
		await db.set_person(hd.dbc, hd.task.state['person']['id'], first, last)
		await task.finish(hd)
		await ws.send_content(hd, 'banner', html.info(text.change_detail_success.format(change = f'{first} {last}')))

@ws.handler(auth_func = authorize)
async def more_person_detail(hd, reverting = False):
	if task.just_started(hd, more_person_detail):
		hd.task.state['person_id'] = int(hd.payload.get('id'))
	if not await task.finished(hd):
		person_id = hd.task.state['person_id']
		emails = await db.get_person_emails(hd.dbc, person_id)
		phones = await db.get_person_phones(hd.dbc, person_id)
		await ws.send_content(hd, 'dialog', html.more_person_detail(person_id, emails, phones))
	# Refactor NOTE: COULD put all of the code that's under 'not await task.finished' into top block, as long as 'if' check there also checks for 'reverting' - in both cases, send_content(...'dialog'...) is needed to repaint the whole dialog.  The only REAL purpose for the 'not await task.finished' block of code would be, for instance, to manage deletions and, possibly, re-ordering of emails/phones -- in such cases, COULD re-draw ONLY the emails and phones blocks, NOT the entire dialog.  This, in turn, might only be a useful advance if a filtersearch was offered at the top of the dialog, allowing live-updated email/phone lists based on filtersearch text; then, we wouldn't want to redraw the whole dialog and re-draw (and re-populate) the filtersearch box

@ws.handler(auth_func = authorize)
async def email_detail(hd, reverting = False):
	await x_detail(hd, email_detail, 'email', fields.EMAIL, db.get_email, db.set_email, db.add_email, text.email, reverting)

@ws.handler(auth_func = authorize)
async def phone_detail(hd, reverting = False):
	await x_detail(hd, phone_detail, 'phone', fields.PHONE, db.get_phone, db.set_phone, db.add_phone, text.phone, reverting)

async def x_detail(hd, func, field, flds, db_get, db_set, db_add, txt, reverting):
	if task.just_started(hd, func) or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		id = hd.task.state['id'] = int(hd.payload.get('id'))
		hd.task.state['person_id'] = int(hd.payload['person_id'])
		hd.task.state[field] = await db_get(hd.dbc, id) if id else {field: ''}
		await ws.send_content(hd, 'dialog', html.dialog2(txt, flds, hd.task.state[field]))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, flds, handle_invalid, 'detail_banner'):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		x_id = hd.task.state['id']
		person_id = hd.task.state['person_id']
		if x_id:
			await db_set(hd.dbc, x_id, data[field])
		else:
			await db_add(hd.dbc, person_id, data[field])
		await task.finish(hd)
		person = await db.get_person(hd.dbc, person_id, 'first_name, last_name')
		await ws.send_content(hd, 'detail_banner', html.info(text.change_detail_success.format(change = f'{person["first_name"]} {person["last_name"]}')))
	# Refactor NOTE: we happen to know that the 'prior task', in this case, is also dialog-based, so we know that 'detail_banner' is the right banner (rather than the main, full-page 'banner'), but it would be better if we could be ignorant of that detail.  This would allow this very dialog, in fact, to be called from other places, and after our finish(), here, we could send the html.info() ignorantly, and let the (js-side?) handler place the info in the correct banner.  TODO!

@ws.handler(auth_func = authorize)
async def delete_mpd(hd):
	data = hd.payload
	await db.delete_person_detail(hd.dbc, data['table'], data['id'])
	await more_person_detail(hd)
	await ws.send_content(hd, 'detail_banner', html.info(text.deletion_succeeded))


@ws.handler(auth_func = authorize)
async def user_tags(hd, reverting = False):
	if task.just_started(hd, user_tags) or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		hd.task.state['uid'] = int(hd.payload.get('user_id')) # TODO: make variant for hd.uid, for non-admins to manage their own (personal) tag-subscriptions
		await ws.send_content(hd, 'dialog', html.user_tags(await user_tags_table(hd)))
	elif not await task.finished(hd): # dialog-box could have been "closed"
		await ws.send_content(hd, 'sub_content', await user_tags_table(hd), container = 'user_tags_table_container')

async def user_tags_table(hd):
	utags, otags = await db.get_user_tags(hd.dbc, hd.task.state['uid'],
													active = not hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													include_unsubscribed = True)
	return html.user_tags_table(utags, otags)

async def _remove_or_add_tag_to_user(hd, func, message):
	tid = int(hd.payload['tag_id'])
	await func(hd.dbc, hd.task.state['uid'], tid)
	await ws.send_content(hd, 'sub_content', await user_tags_table(hd), container = 'user_tags_table_container')
	tag = await db.get_tag(hd.dbc, tid, 'name')
	await ws.send_content(hd, 'detail_banner', html.info(message.format(name = tag['name'])))

@ws.handler(auth_func = authorize)
async def remove_tag_from_user(hd):
	await _remove_or_add_tag_to_user(hd, db.remove_user_from_tag, text.removed_tag_from_user)

@ws.handler(auth_func = authorize)
async def add_tag_to_user(hd):
	await _remove_or_add_tag_to_user(hd, db.add_user_to_tag, text.added_tag_to_user)



@ws.handler(auth_func = authorize)
async def tags(hd, reverting = False):
	if task.just_started(hd, tags):
		t = await db.get_tags(hd.dbc, get_subscribers = True)
		await ws.send_content(hd, 'content', html.tags_page(t))
	else:
		t = await db.get_tags(hd.dbc,
								active = not hd.task.state.get('filtersearch_include_extra', False),
								like = hd.task.state.get('filtersearch_text', ''),
								get_subscribers = True)
		await ws.send_content(hd, 'sub_content', html.tag_table(t), container = 'tag_table_container')


@ws.handler(auth_func = authorize)
async def new_tag(hd, reverting = False):
	if task.just_started(hd, new_tag) or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		await ws.send_content(hd, 'dialog', html.dialog2(text.tag, fields.TAG))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.TAG, handle_invalid, 'detail_banner'):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		name = data['name']
		await db.new_tag(hd.dbc, name, html.checkbox_value(data, 'active'))
		await task.finish(hd)
		await ws.send_content(hd, 'banner', html.info(text.added_tag_success.format(name = f'"{name}"')))

@ws.handler(auth_func = authorize) # TODO: change to user-level auth; users that create tags can edit those tags (perhaps only some users are even allowed to create tags; need concept of publicly-discoverable tags vs. admin-directed subscription management....)
async def tag_detail(hd, reverting = False):
	if task.just_started(hd, tag_detail) or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		hd.task.state['tag'] = await db.get_tag(hd.dbc, int(hd.payload.get('id')))
		await ws.send_content(hd, 'dialog', html.dialog2(text.tag, fields.TAG, hd.task.state['tag']))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fields.TAG, handle_invalid, 'detail_banner'):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		name = data['name']
		await db.set_tag(hd.dbc, hd.task.state['tag']['id'], name, html.checkbox_value(data, 'active'))
		await task.finish(hd)
		await ws.send_content(hd, 'banner', html.info(text.change_detail_success.format(change = f'"{name}"')))


@ws.handler(auth_func = authorize)
async def tag_users(hd, reverting = False):
	if task.just_started(hd, tag_users) or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		hd.task.state['tag'] = await db.get_tag(hd.dbc, int(hd.payload.get('tag_id')))
		await ws.send_content(hd, 'dialog', html.tag_users_and_nonusers(await tag_users_table(hd)))
	elif not await task.finished(hd): # dialog-box could have been "closed"
		await ws.send_content(hd, 'sub_content', await tag_users_table(hd), container = 'users_and_nonusers_table_container')

async def tag_users_table(hd):
	users, nonusers = await db.get_tag_users(hd.dbc, hd.task.state['tag']['id'],
															active = not hd.task.state.get('filtersearch_include_extra'),
															like = hd.task.state.get('filtersearch_text'),
															include_unsubscribed = True)
	return html.tag_users_and_nonusers_table(hd.task.state['tag']['name'], users, nonusers)

async def _remove_or_add_user_to_tag(hd, func, message):
	uid = int(hd.payload['user_id'])
	await func(hd.dbc, uid, hd.task.state['tag']['id'])
	await ws.send_content(hd, 'sub_content', await tag_users_table(hd), container = 'users_and_nonusers_table_container')
	username = await db.get_user(hd.dbc, uid, 'username')
	await ws.send_content(hd, 'detail_banner', html.info(message.format(username = username['username'], tag_name = hd.task.state['tag']['name'])))


@ws.handler(auth_func = authorize)
async def remove_user_from_tag(hd):
	await _remove_or_add_user_to_tag(hd, db.remove_user_from_tag, text.removed_user_from_tag)

@ws.handler(auth_func = authorize)
async def add_user_to_tag(hd):
	await _remove_or_add_user_to_tag(hd, db.add_user_to_tag, text.added_user_to_tag)


