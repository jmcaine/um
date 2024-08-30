__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging
import traceback
import json
import weakref
import copy

from dataclasses import dataclass, field as dataclass_field
from yarl import URL

import aiosqlite
import asyncio

from aiohttp import web, WSMsgType, WSCloseCode

from . import db
from . import fields
from . import html
from . import messages
from . import settings
from .task import Task
from . import text
from . import valid
from . import ws

from . import admin

from . import exception as ex


# Logging ---------------------------------------------------------------------

logging.getLogger('aiosqlite').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('aiohttp').setLevel(logging.INFO if settings.debug else logging.ERROR) # ERROR and INFO will dump tracebacks on console upon "500 Internal Server Error" failures - essential to development; INFO will add informational lines re: GETs and such; DEBUG would be fine here, but aiohttp internal debug info not necessarily useful; probably just noisy

logging.basicConfig(format = '%(asctime)s - %(levelname)s : %(name)s:%(lineno)d -- %(message)s', level = logging.DEBUG if settings.debug else logging.CRITICAL)
l = logging.getLogger(__name__)


# Shortcuts -------------------------------------------------------------------

hr = lambda text: web.Response(text = text, content_type = 'text/html')
gurl = lambda rq, name, **kwargs: str(rq.app.router[name].url_for(**kwargs))
dbc = lambda rq: db.cursor(rq.app['db_connection'])
ws_url = lambda rq: URL.build(scheme = 'ws', host = rq.host, path = '/_ws')


# Init / Shutdown -------------------------------------------------------------

rt = web.RouteTableDef()

_websockets = web.AppKey("websockets", weakref.WeakSet)

async def _init(app):
	l.info('Initializing...')
	app[_websockets] = weakref.WeakSet()
	await _init_db(app)
	l.info('...initialization complete')

async def _shutdown(app):
	l.info('Shutting down...')
	for ws in set(app[_websockets]):
		await ws.close(code = WSCloseCode.GOING_AWAY, message = "Server shutdown")
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

@rt.get('/test')
async def test(rq):
	return hr(html.test())


@rt.get('/')
async def main(rq):
	return hr(html.main(ws_url(rq)))


@rt.get('/_ws')
async def _ws(rq):
	wsr = web.WebSocketResponse()
	await wsr.prepare(rq)
	rq.app[_websockets].add(wsr)

	try:
		hd = Hd(rq, wsr, await dbc(rq))
		async for msg in wsr:
			match msg.type:
				case WSMsgType.ERROR:
					raise wsr.exception()
				case WSMsgType.TEXT:
					hd.payload = json.loads(msg.data)
					module = hd.payload.get('module', 'app.main')
					await ws._handlers[module][hd.payload['task']](hd) # call the handler for the given task - functions decorated with @ws.handler are handlers; their (function) names are the task names
				case WSMsgType.BINARY:
					pass #TODO: await _ws_binary(hd, msg.data)
				case _:
					l.error('Unexpected/invalid WebSocketResponse message type; ignoring... anxiously')
	except Exception as e:
		l.error(traceback.format_exc())
		l.error('Exception processing WS messages; shutting down WS...')

	rq.app[_websockets].discard(wsr)
	l.info('Websocket connection closed')
	return wsr


# -----------------------------------------------------------------------------
# define handlers for "tasks" sent over the websocket - functions decorated with @ws.handler are handlers; their (function) names are the task names


@dataclass(slots = True)
class Hd: # handler data class; for grouping stuff more convenient to pass around in one object in websocket-handler functions
	rq: web.Request
	wsr: web.WebSocketResponse
	dbc: aiosqlite.Connection
	idid: str | None = None
	uid: int | None = None
	state: dict = dataclass_field(default_factory = dict)
	payload: dict | None = None
	task: Task | None = None
	prior_tasks: list = dataclass_field(default_factory = list)


@ws.handler
async def ping(hd):
	#l.info('PING received from client!') # uncomment to confirm heartbeat
	pass # nothing to do


@ws.handler
async def submit_fields(hd):
	'''
	This task-handler is called a lot - whenever "fields" are submitted; it's a second-class
	citizen task - the main task is stored in hd.task, and used to call the proper handler
	for the given (expected) fieldset.
	'''
	await hd.task.handler(hd)


@ws.handler
async def finish(hd):
	hd.payload['finished'] = True
	await hd.task.handler(hd)


@ws.handler
async def filtersearch(hd):
	'''
	Similar to submit_fields - see note there.
	'''
	hd.task.state['filtersearch_text'] = hd.payload.get('searchtext', '')
	hd.task.state['filtersearch_include_extra'] = hd.payload.get('include_extra', False)
	await hd.task.handler(hd)


@ws.handler
async def identify(hd):
	idid = hd.idid = hd.payload.get('idid')
	if key := hd.payload.get('key'):
		# new identity:
		await db.add_idid_key(hd.dbc, idid, key)
		# New persistence, with this client (previous one expired or this is a brand new login or...); send the login-or-join choice:
		await login_or_join(hd)
	else: # it's one or the other (idid and key were sent, or else idid and pub and hsh were sent)
		# existing identity
		user_id = await db.get_user_by_id_key(hd.dbc, idid, hd.payload['pub'], hd.payload['hsh'])
		if user_id: # "persistent session" all in order, "auto log-in"... go straight to it:
			hd.uid = user_id
			await messages.messages(hd) # show main messages page
		else:
			await ws.send(hd, 'new_key')


@ws.handler
async def login_or_join(hd):
	task.started(hd, login_or_join) # necessary for "cancel" fallback, from the middle of a new "join"
	await ws.send_content(hd, 'content', html.login_or_join())


@ws.handler
async def login(hd):
	if not task.started(hd, login):
		await send_task(hd, 'fieldset', html.login(fields.LOGIN))
	else:
		data = hd.payload
		if await _invalids(hd, data, fields.LOGIN):
			return # if there WERE invalids, bannar was already sent within
		uid = await db.login(hd.dbc, hd.idid, data['username'], data['password'])
		if uid:
			hd.uid = uid
			await messages.messages(hd)
		else:
			await ws.send_content(hd, 'banner', html.error(text.invalid_login))


@ws.handler
async def logout(hd):
	await db.logout(hd.dbc, hd.uid)
	task.clear_all(hd)
	hd.state = {}
	await login_or_join(hd)


@ws.handler
async def forgot_password(hd):
	#!!!	await send_banner_task(hd, 'fieldset', html.info(text.forgot_password_prelude), html.forgot_password(fields.EMAIL))
	await ws.send_content(hd, 'banner', html.info(text.forgot_password_prelude))

@ws.handler
async def join(hd):
	if supertask_started(hd, join):
		await continue_join_or_invite(hd, True, text.your)
	else:
		await start_join_or_invite(hd, text.your)

@ws.handler
async def invite(hd):
	if supertask_started(hd, invite):
		await continue_join_or_invite(hd, False, text.friends)
	else:
		await start_join_or_invite(hd, text.friends)

start_join_or_invite = lambda hd, label_prefix: send_task(hd, 'dialog', html.dialog(text.name, html.build_fields(fields.PERSON, None, label_prefix), fields.PERSON.keys(), text.next))

async def continue_join_or_invite(hd, send_username_fieldset, label_prefix = None):
	if label_prefix:
		hd.ststate['label_prefix'] = label_prefix
	else:
		label_prefix = hd.ststate['label_prefix']

	send_X_fs = lambda fs_title, fieldset: send_fieldset(hd, fs_title, 
								html.build_fields(fieldset, None, label_prefix), fieldset.keys(), text.next)
	send_Y_fs = lambda fs_title, fieldset: send_task(hd, 'dialog', html.dialog(fs_title,
								html.build_fields(fieldset, None, label_prefix), fieldset.keys(), text.next))
	send_person_fs = lambda: send_Y_fs(text.name, fields.PERSON)
	send_email_fs = lambda: send_Y_fs(text.email, fields.EMAIL)
	send_phone_fs = lambda: send_Y_fs(text.phone, fields.PHONE)
	send_username_fs_DEPRECATE = lambda username_hint: send_fieldset(hd, text.username,
								html.build_fields(fields.NEW_USERNAME, {'username': username_hint}, label_prefix), fields.NEW_USERNAME.keys(), text.next)
	send_username_fs = lambda username_hint: send_task(hd, 'dialog', html.dialog(text.username,
								html.build_fields(fields.NEW_USERNAME, {'username': username_hint}, label_prefix), fields.NEW_USERNAME.keys(), text.next))
	send_password_fs = lambda: send_Y_fs(text.password, fields.NEW_PASSWORD)

	data = hd.payload
	match hd.ststate.get('action', 'add_person'): # assume 'add_person' (first action) if no action yet set
		case 'add_person':
			if await _invalids(hd, data, fields.PERSON, 'detail_banner'):
				return # _invalids() handles invalid case, and there's nothing more to do here
			#else:
			await db.begin(hd.dbc) # work through ALL actions before committing (transaction) to DB
			hd.ststate['pid'] = await db.add_person(hd.dbc, data['first_name'], data['last_name'])
			hd.ststate['name'] = data # store name for later
			hd.ststate['action'] = 'add_email' # next action
			_bump_action(hd, 'add_email', 'add_person')
			await send_email_fs()

		case 'add_email':
			if await _invalids(hd, data, fields.EMAIL, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			if _not_yet(hd, 'add_person'):
				await send_person_fs()
				return # finished
			#else all good, move on!
			await db.add_email(hd.dbc, hd.ststate['pid'], data['email'])
			_bump_action(hd, 'add_phone', 'add_email')
			await send_phone_fs()

		case 'add_phone':
			if await _invalids(hd, data, fields.PHONE, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			if _not_yet(hd, 'add_email'):
				await send_email_fs()
				return # finished
			#else all good, move on!
			await db.add_phone(hd.dbc, hd.ststate['pid'], data['phone'])
			username_suggestion = await db.suggest_username(hd.dbc, hd.ststate['name'])
			hd.ststate['username_suggestion'] = username_suggestion
			if send_username_fieldset:
				_bump_action(hd, 'add_username', 'add_phone')
				await send_username_fs(username_suggestion)
			else: # we're dealing with /invite - finish the invite:
				# (note that this is more of a "mandatory invite", as an admin might use to build a team;
				# a more casual invite might simply involve somebody giving you the website name and
				# letting you sign up yourself; there's nothing "in between" - in-between-land is usually
				# just "annoy people" land)
				# create the user record:
				user_id = await db.add_user(hd.dbc, hd.ststate['pid'], username_suggestion)
				await db.commit(hd.dbc) # finally, commit it all
				# send a password-reset code via email, to the user's email:
				code = await db.generate_password_reset_code(hd.dbc, user_id)
				emails = await db.get_user_emails(hd.dbc, user_id)
				l.debug(f'inviting new user ({hd.ststate["name"]}) via email: {emails[0]["email"]}')
				# TODO!
				# notify inviter of success:
				person = hd.ststate['name']
				await revert_to_priortask(hd)
				await send_banner(hd, html.info(text.invite_succeeded.format(name = f"{person['first_name']} {person['last_name']}")))

		case 'add_username':
			if await _invalids(hd, data, fields.NEW_USERNAME, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			if _not_yet(hd, 'add_phone'):
				await send_phone_fs()
				return # finished
			# else, add one more validation step: confirm that the username isn't already taken:
			if await db.username_exists(hd.dbc, data['username']):
				await send_banner(hd, html.error(text.Valid.username_exists))
				return # finished
			#else all good, move on!
			hd.ststate['user_id'] = await db.add_user(hd.dbc, hd.ststate['pid'], data['username'])
			_bump_action(hd, 'add_password', 'add_username')
			await send_password_fs()

		case 'add_password':
			if await _invalids(hd, data, fields.NEW_PASSWORD, 'detail_banner'):
				return # if there WERE invalids, bannar was already sent within
			if _not_yet(hd, 'add_username'):
				await send_username_fs(hd.ststate['username_suggestion'])
				return # finished
			#else, add one more validation step: confirm passwords are identical:
			if data['password'] != data['password_confirmation']:
				await send_banner(hd, html.error(text.Valid.password_match))
				return # finished
			#else all good, move on!
			await db.reset_user_password(hd.dbc, hd.ststate['user_id'], data['password'])
			await db.commit(hd.dbc) # finally, commit it all
			hd.uid = hd.ststate['user_id']
			await db.force_login(hd.dbc, hd.idid, hd.uid)
			hd.ststate = {} # reset
			await send_content(hd, html.messages(False)) # just joined, so couldn't possibly be an admin!


# Utils -----------------------------------------------------------------------


def _bump_action(hd, next_action, current_action = None):
	if 'completed' not in hd.ststate:
		hd.ststate['completed'] = []
	hd.ststate['completed'].append(current_action)
	hd.ststate['action'] = next_action

def _not_yet(hd, required_action):
	if completed := hd.ststate.get('completed'):
		if required_action in completed:
			return False # good to continue normall processing
	#else:
	hd.ststate['action'] = required_action
	return True # "true, NOT YET ready to move on!"

