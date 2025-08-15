__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging
import traceback
import json

from dataclasses import dataclass, field as dataclass_field
from yarl import URL

import aiosqlite
import asyncio

from aiohttp import web, WSMsgType, WSCloseCode

from . import admin
from . import db
from . import emailer
from . import fields
from . import html
from . import messages
from . import settings
from . import task
from .task import Task
from . import text
from . import valid
from . import ws

from . import exception as ex

from .const import *



# Logging ---------------------------------------------------------------------

logging.getLogger('aiosqlite').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('aiohttp').setLevel(logging.ERROR if settings.debug else logging.ERROR) # ERROR and INFO will dump tracebacks on console upon "500 Internal Server Error" failures - essential to development; INFO will add informational lines re: GETs and such; DEBUG would be fine here, but aiohttp internal debug info not necessarily useful; probably just noisy

logging.basicConfig(format = '%(asctime)s - %(levelname)s : %(name)s:%(lineno)d -- %(message)s', level = logging.DEBUG if settings.debug else logging.CRITICAL)
l = logging.getLogger(__name__)


# Shortcuts -------------------------------------------------------------------

hr = lambda text: web.Response(text = text, content_type = 'text/html')
gurl = lambda rq, name, **kwargs: str(rq.app.router[name].url_for(**kwargs))
dbc = lambda rq: db.cursor(rq.app['db_connection'])


# Init / Shutdown -------------------------------------------------------------

rt = web.RouteTableDef()

async def _init(app):
	l.info('Initializing...')
	app['hds'] = []
	app['active_module'] = 'app.main' # default to ourselves
	await _init_db(app)
	l.info('...initialization complete')

async def _shutdown(app):
	l.info('Shutting down...')
	while True:
		try:
			hd = app['hds'].pop()
			await hd.wsr.close(code = WSCloseCode.GOING_AWAY, message = "Server shutdown")
		except IndexError:
			break # done
	l.info('...shutdown complete')

async def _init_db(app):
	l.info('...initializing database...')

	app['db_connection'] = await db.connect(settings.db_filename) # sqlite3 offers an "efficient" approach that involves just using the database (dbc) directly - a temp cursor is auto-created under the hood): https://pysqlite.readthedocs.io/en/latest/sqlite3.html#using-sqlite3-efficiently ... however, there's nothing wrong with using connection.cursor() to get and interact (in the more conventional way) with a cursor object rather than interacting with the DB connection object itself.  Note that doing so does NOT imply a separate transaction for every cursor - use db.begin(dbc), db.rollback(dbc), db.commit(dbc) for that....

	l.info('...database initialized...')


# Run server like so, from cli, from root directory (containing 'app' directory):
#		python -m aiohttp.web -H localhost -P 8080 app.main:init
#		python -m aiohttp.web -H localhost -P 8462 app.main:init
#         https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers
# Or, using adev (from parent directory!):
#		adev runserver -s static --livereload app
def init(argv):
	app = web.Application()

	# Add standard routes:
	app.add_routes(rt)

	# Add startup/shutdown hooks:
	app.on_startup.append(_init)
	app.on_shutdown.append(_shutdown)

	return app


# Alternately, use adev to run:
#		adev runserver -s static --livereload app
#def app():
#	return init(None)


# Handlers --------------------------------------------------------------------

if settings.debug:
	rt.static('/static', settings.debug_static)
#else use "real" reverse proxy set up in nginx, e.g., to map static directly

if settings.debug:
	@rt.get('/favicon.ico')
	async def favico(rq):
		return web.FileResponse('./static/favicon.ico')


@rt.get('/')
async def main(rq):
	return hr(html.document(_ws_url(rq)).render())

@rt.get('/invite/{code}')
async def redeem_invite(rq):
	code = rq.match_info['code'][:db.k_reset_code_length].replace('"', '') # simple sanitation; sufficient
	return hr(html.document(_ws_url(rq), f'code:{code}').render())

@rt.get('/_sms/{to}/{from}/{message}/{id}/{timestamp}')
async def sms(rq):
	"""
	From https://wiki.voip.ms/article/SMS-MMS#Send_and_Receive_Messages_.28via_SIP_MESSAGE_Protocol.29
	{ID} = The ID of the SMS message.
	{TIMESTAMP} = The date and time the message was received.
	{FROM} = The phone number that sent you the message.
	{TO} = The DID Number that received the message.
	{MESSAGE} = The content of the message.
	{MEDIA} = Comma-separated list of media files.
	"""
	mi = rq.match_info
	await messages.sms(rq, mi['from'], mi['message'], mi['timestamp'])
	return hr('OK')

@rt.get('/_ws')
async def _ws(rq):
	wsr = web.WebSocketResponse(max_msg_size = 0)
	try:
		await wsr.prepare(rq)
		hd = Hd(rq, wsr, await dbc(rq))
		rq.app['hds'].append(hd)
		async for msg in wsr:
			match msg.type:
				case WSMsgType.ERROR:
					raise wsr.exception()
				case WSMsgType.TEXT:
					await _handle_ws_text(rq, hd, msg.data)
				case WSMsgType.BINARY:
					await _handle_ws_binary(hd, msg.data)
				case _:
					l.error('Unexpected/invalid WebSocketResponse message type; ignoring... anxiously')
	except Exception as e:
		l.error(traceback.format_exc())
		l.error('Exception processing WS messages; shutting down WS...')
	finally:
		try: rq.app['hds'].remove(hd)
		except ValueError: pass # not in list; already removed!
		l.info('Websocket connection closed')
	return wsr

async def _handle_ws_text(rq, hd, data):
	hd.payload = json.loads(data)
	module = hd.payload.get('module', 'app.main')
	active_module = rq.app['active_module']
	if module != active_module and hd.payload['task'] != 'ping': # (don't switch module for mere (periodic and automatic) pings!)
		# Call the exit/enter handlers, if switching modules:
		if 'exit_module' in ws._handlers[active_module]:
			await ws._handlers[active_module]['exit_module'](hd)
		if 'enter_module' in ws._handlers[module]:
			await ws._handlers[module]['enter_module'](hd)
		rq.app['active_module'] = module # may be redundant, if enter_module() did this already
	# Now call the handler for the given task - functions decorated with @ws.handler are handlers; their (function) names are the task names
	await ws._handlers[module][hd.payload['task']](hd)


async def _handle_ws_binary(hd, data):
	assert data[0] == ord('!'), '"magic byte" ! needed to indicate this is a file upload (by convention)'
	delimiter = b'\r\n\r\n'
	idx = data.find(delimiter)
	meta = json.loads(data[1:idx]) # '1' to get past the "magic byte" ('!')
	meta['files'] = json.loads(meta['files'])
	payload = data[idx+len(delimiter):]
	await ws._handlers[hd.payload.get('module', 'app.messages')][meta['task']](hd, meta, payload)


# -----------------------------------------------------------------------------
# define handlers for "tasks" sent over the websocket - functions decorated with @ws.handler are handlers; their (function) names are the task names


@dataclass(slots = True)
class Hd: # handler data class; for grouping stuff more convenient to pass around in one object in websocket-handler functions
	rq: web.Request
	wsr: web.WebSocketResponse
	dbc: aiosqlite.Connection
	idid: str | None = None
	uid: int | None = None
	admin: bool = False
	state: dict = dataclass_field(default_factory = dict)
	payload: dict | None = None
	task: Task | None = None
	prior_tasks: list = dataclass_field(default_factory = list)

@ws.handler
async def enter_module(hd):
	pass

@ws.handler
async def exit_module(hd):
	pass


@ws.handler
async def ping(hd):
	#l.info('PING received from client!') # uncomment to confirm heartbeat
	pass # nothing to do


async def handle_invalid(hd, message, banner):
	await ws.send_content(hd, banner, html.error(message))


@ws.handler
async def submit_fields(hd):
	'''
	This task-handler is called a lot - whenever "fields" are submitted; it's a second-class
	citizen task - the main task is stored in hd.task, and used to call the proper handler
	for the given (expected) fieldset.
	'''
	await hd.task.handler(hd)


@ws.handler
async def finish(hd): # usually called (via ws client) to "cancel";
	await task.finish(hd)

@ws.handler
async def filtersearch(hd):
	'''
	Similar to submit_fields - see note there.
	'''
	hd.task.state['filtersearch'] = hd.payload # store for handling by actual task
	await hd.task.handler(hd)


@ws.handler
async def identify(hd):
	idid = hd.idid = hd.payload.get('idid')
	if key := hd.payload.get('key'):
		# new identity:
		await db.add_idid_key(hd.dbc, idid, key)
		# new persistence for this client (previous one expired or this is a brand new login or...)
		initial = hd.payload.get('initial')
		if initial.startswith('code:'):
			# invite code provided in url; process now:
			await redeem_invite(hd, initial.split(':')[1])
		else:
			# normal login:
			await login(hd) #await login_or_join(hd)
	else: # it's one or the other (idid and key were sent, or else idid and pub and hsh were sent)
		# existing identity; resume:
		user_id = await db.get_user_by_id_key(hd.dbc, idid, hd.payload['pub'], hd.payload['hsh'])
		if user_id: # "persistent session" all in order, "auto log-in"... go straight to it:
			hd.uid = user_id
			hd.admin = await admin.authorize(hd, user_id)
			await messages.messages(hd) # show main messages page
		else:
			await ws.send(hd, 'new_key')


@ws.handler
async def login_or_join(hd):
	task.start(hd, login_or_join) # necessary for "cancel" fallback, from the middle of a new "join"
	await ws.send_content(hd, 'content', html.login_or_join())


@ws.handler
async def login(hd, reverting = False):
	if task.just_started(hd, login):
		await ws.send(hd, 'fieldset', fieldset = html.login(fields.LOGIN).render())
	else:
		data = hd.payload
		if await valid.invalids(hd, data, fields.LOGIN, handle_invalid, 'banner'):
			return # if there WERE invalids, banner was already sent within
		#else all good, move on!
		uid = await db.login(hd.dbc, hd.idid, data['username'], data['password'])
		if uid:
			hd.uid = uid
			hd.admin = await admin.authorize(hd, uid)
			await messages.messages(hd)
		else:
			await ws.send_content(hd, 'banner', html.error(text.invalid_login))

@ws.handler
async def redeem_invite(hd, code = None):
	if task.just_started(hd, redeem_invite):
		if uid := await db.get_user_id_by_reset_code(hd.dbc, code):
			hd.uid = hd.task.state['user_id'] = uid
			hd.task.state['code'] = code
			await ws.send(hd, 'fieldset', fieldset = html.new_password(fields.NEW_PASSWORD).render())
		else:
			await ws.send_content(hd, 'banner', html.error(text.no_such_invitation_code))
	else:
		data = hd.payload
		password = data.get('password')
		if password != data.get('password_confirmation'):
			await ws.send_content(hd, 'banner', html.error(text.Valid.password_match))
		else:
			await db.reset_user_password(hd.dbc, hd.task.state['user_id'], password)
			hd.admin = await admin.authorize(hd, hd.uid)
			await db.force_login(hd.dbc, hd.idid, hd.uid)
			await messages.messages(hd)


@ws.handler
async def logout(hd):
	await db.logout(hd.dbc, hd.uid)
	await ws.send(hd, 'reload')


@ws.handler
async def forgot_password(hd):
	if task.just_started(hd, forgot_password):
		await ws.send(hd, 'fieldset', fieldset = html.forgot_password(fields.EMAIL).render())
		await ws.send_content(hd, 'banner', html.info(text.forgot_password_prelude))
	else:
		data = hd.payload
		hd.task.state['email'] = email = data.get('email', hd.task.state.get('email')).strip() # stage 1
		hd.task.state['code'] = code = data.get('code', hd.task.state.get('code', '')).strip() # stage 2
		hd.task.state['password'] = password = data.get('password', hd.task.state.get('password')) # stage 3
		if not code:
			# Still at stage 1 - get address and send email:
			if await valid.invalids(hd, data, fields.EMAIL, handle_invalid, 'banner'):
				return # if there WERE invalids, banner was already sent within
			#else all good, move on!
			hd.task.state['user_id'] = user_id = await db.get_user_id_by_email(hd.dbc, email)
			if not user_id:
				await ws.send_content(hd, 'banner', html.info(text.unknown_email))
				return # finished
			# else:
			new_code = await db.generate_password_reset_code(hd.dbc, user_id)
			emailer.send_email(email, text.reset_email_subject, text.password_reset_code_email_body.format(code = new_code))
			await ws.send(hd, 'fieldset', fieldset = html.password_reset_code(fields.RESET_CODE).render())
			await ws.send_content(hd, 'banner', html.info(text.enter_reset_code))
		elif not password:
			# Still at stage 2 - get/validate code:
			if await db.validate_reset_password_code(hd.dbc, code, hd.task.state['user_id']):
				await ws.send(hd, 'fieldset', fieldset = html.new_password(fields.NEW_PASSWORD).render())
			else:
				await ws.send_content(hd, 'banner', html.error(text.enter_reset_code_retry))
		else:
			# Stage 3 - get/process new password:
			if password != data.get('password_confirmation'):
				await ws.send_content(hd, 'banner', html.error(text.Valid.password_match))
			else:
				await db.reset_user_password(hd.dbc, hd.task.state['user_id'], password)
				hd.uid = hd.task.state['user_id']
				hd.admin = await admin.authorize(hd, hd.uid)
				await db.force_login(hd.dbc, hd.idid, hd.uid)
				await messages.messages(hd)

@ws.handler
async def join(hd):
	if task.just_started(hd, join):
		await start_join_or_invite(hd, text.your)
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		await continue_join_or_invite(hd, True)

@ws.handler
async def invite(hd):
	if task.just_started(hd, invite):
		await start_join_or_invite(hd, text.friends)
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		await continue_join_or_invite(hd, False)

async def start_join_or_invite(hd, label_prefix):
	hd.task.state['label_prefix'] = label_prefix
	await ws.send_content(hd, 'dialog', html.dialog(text.name, html.build_fields(fields.PERSON, None, label_prefix), fields.PERSON.keys(), text.next))

async def continue_join_or_invite(hd, send_username_fieldset):
	label_prefix = hd.task.state['label_prefix']
	send_fs = lambda fs_title, fieldset: ws.send_content(hd, 'dialog', html.dialog(fs_title,
								html.build_fields(fieldset, None, label_prefix), fieldset.keys(), text.next))
	send_person_fs = lambda: send_fs(text.name, fields.PERSON)
	send_email_fs = lambda: send_fs(text.email, fields.EMAIL)
	send_phone_fs = lambda: send_fs(text.phone, fields.PHONE)
	send_username_fs = lambda username_hint: ws.send_content(hd, 'dialog', html.dialog(text.username,
								html.build_fields(fields.NEW_USERNAME, {'username': username_hint}, label_prefix), fields.NEW_USERNAME.keys(), text.next))
	send_password_fs = lambda: send_fs(text.password, fields.NEW_PASSWORD)

	data = hd.payload
	match hd.task.state.get('action', 'add_person'): # assume 'add_person' (first action) if no action yet set
		case 'add_person':
			if await valid.invalids(hd, data, fields.PERSON, handle_invalid, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			#else all good, move on!
			await db.begin(hd.dbc) # work through ALL actions before committing (transaction) to DB
			hd.task.state['pid'] = await db.add_person(hd.dbc, data['first_name'], data['last_name'])
			hd.task.state['name'] = data # store name for later
			hd.task.state['action'] = 'add_email' # next action
			_bump_action(hd, 'add_email', 'add_person')
			await send_email_fs()

		case 'add_email':
			if await valid.invalids(hd, data, fields.EMAIL, handle_invalid, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			if _not_yet(hd, 'add_person'):
				await send_person_fs()
				return # finished
			#else all good, move on!
			await db.add_email(hd.dbc, hd.task.state['pid'], data['email'])
			_bump_action(hd, 'add_phone', 'add_email')
			await send_phone_fs()

		case 'add_phone':
			if await valid.invalids(hd, data, fields.PHONE, handle_invalid, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			if _not_yet(hd, 'add_email'):
				await send_email_fs()
				return # finished
			#else all good, move on!
			await db.add_phone(hd.dbc, hd.task.state['pid'], data['phone'])
			username_suggestion = await db.suggest_username(hd.dbc, hd.task.state['name'])
			hd.task.state['username_suggestion'] = username_suggestion
			if send_username_fieldset:
				_bump_action(hd, 'add_username', 'add_phone')
				await send_username_fs(username_suggestion)
			else: # we're dealing with /invite - finish the invite:
				# (note that this is more of a "mandatory invite", as an admin might use to build a team;
				# a more casual invite might simply involve somebody giving you the website name and
				# letting you sign up yourself; there's nothing "in between" - in-between-land is usually
				# just "annoy people" land)
				# create the user record:
				user_id = await db.add_user(hd.dbc, hd.task.state['pid'], username_suggestion)
				await db.commit(hd.dbc) # finally, commit it all
				# send a password-reset code via email, to the user's email:
				code = await db.generate_password_reset_code(hd.dbc, user_id)
				emails = await db.get_user_emails(hd.dbc, user_id)
				emailer.send_email(emails[0]["email"], text.email_invite_subject,
							  text.email_invite_body.format(code = code),
							  text.email_invite_body_html.format(code = code))
				l.info(f'inviting new user ({hd.task.state["name"]}) via email: {emails[0]["email"]} ... code = {code}')
				# notify inviter of success:
				person = hd.task.state['name']
				await task.finish(hd)
				await ws.send_content(hd, 'banner', html.info(text.invite_succeeded.format(name = f"{person['first_name']} {person['last_name']}")))

		case 'add_username':
			if await valid.invalids(hd, data, fields.NEW_USERNAME, handle_invalid, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			if _not_yet(hd, 'add_phone'):
				await send_phone_fs()
				return # finished
			# else, add one more validation step: confirm that the username isn't already taken:
			if await db.username_exists(hd.dbc, data['username']):
				await ws.send_content(hd, 'banner', html.error(text.Valid.username_exists))

				return # finished
			#else all good, move on!
			hd.task.state['user_id'] = await db.add_user(hd.dbc, hd.task.state['pid'], data['username'])
			_bump_action(hd, 'add_password', 'add_username')
			await send_password_fs()

		case 'add_password':
			if await valid.invalids(hd, data, fields.NEW_PASSWORD, handle_invalid, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			if _not_yet(hd, 'add_username'):
				await send_username_fs(hd.task.state['username_suggestion'])
				return # finished
			#else, add one more validation step: confirm passwords are identical:
			if data['password'] != data['password_confirmation']:
				await ws.send_content(hd, 'banner', html.error(text.Valid.password_match))
				return # finished
			#else all good, move on!
			await db.reset_user_password(hd.dbc, hd.task.state['user_id'], data['password'])
			await db.commit(hd.dbc) # finally, commit it all
			hd.uid = hd.task.state['user_id']
			hd.admin = await admin.authorize(hd, hd.uid)
			await db.force_login(hd.dbc, hd.idid, hd.uid)
			task.clear_all(hd) # a "join" results in a clean slate - no prior tasks (note that, above, the end of invite, after the db-commit, we DO finish() to revert to prior task, which may be administrative user-list management.....
			await ws.send(hd, 'hide_dialog') # safe; no need to finish() task - we just logged in (force_login) and have a clean slate
			await messages.messages(hd) # show main messages page



# Utils -----------------------------------------------------------------------


def _bump_action(hd, next_action, current_action = None):
	if 'completed' not in hd.task.state:
		hd.task.state['completed'] = []
	hd.task.state['completed'].append(current_action)
	hd.task.state['action'] = next_action

def _not_yet(hd, required_action):
	if completed := hd.task.state.get('completed'):
		if required_action in completed:
			return False # good to continue normall processing
	#else:
	hd.task.state['action'] = required_action
	return True # "true, NOT YET ready to move on!"

def _ws_url(rq):
	host = rq.host.split(':')
	port = int(host[1]) if len(host) > 1 else None
	#return URL.build(scheme = 'wss' if rq.secure else 'ws', host = host[0], port = port, path = '/_ws')
	#TODO: the above line, elegantly building 'wss' or 'ws', does not work because https requests are translated in nginx to http requests over unix socket, so rq.secure is False and rq.scheme is http (not https)!
	return URL.build(scheme = 'ws', host = host[0], port = port, path = '/_ws')
