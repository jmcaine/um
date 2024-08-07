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
from string import ascii_uppercase
from random import choices as random_choices

import aiosqlite
import asyncio

from aiohttp import web, WSMsgType, WSCloseCode

from . import html
from . import db
from . import settings
from . import text
from . import fields
from . import valid

from . import exception as ex

# Logging ---------------------------------------------------------------------

logging.getLogger('aiosqlite').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('aiohttp').setLevel(logging.INFO if settings.debug else logging.ERROR) # ERROR and INFO will dump tracebacks on console upon "500 Internal Server Error" failures - essential to development; INFO will add informational lines re: GETs and such; DEBUG would be fine here, but aiohttp internal debug info not necessarily useful; probably just noisy

logging.basicConfig(format = '%(asctime)s - %(levelname)s : %(name)s:%(lineno)d -- %(message)s', level = logging.DEBUG if settings.debug else logging.CRITICAL)
l = logging.getLogger(__name__)


# Shortcuts -------------------------------------------------------------------

rt = web.RouteTableDef()
hr = lambda text: web.Response(text = text, content_type = 'text/html')
gurl = lambda rq, name, **kwargs: str(rq.app.router[name].url_for(**kwargs))
dbc = lambda rq: db.cursor(rq.app['db_connection'])
ws_url = lambda rq: URL.build(scheme = 'ws', host = rq.host, path = '/_ws')
wsr_send_task = lambda hd, task, html: hd.wsr.send_json({'task': task, task: html.render()})


# Init / Shutdown -------------------------------------------------------------

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


# Pages -----------------------------------------------------------------------

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

@rt.get('/test_person/{name}')
async def test(rq):
	person = await db.test_fetch(await dbc(rq), rq.match_info['name'])
	return hr(html.test(person))

@rt.get('/test_protected')
async def test_protected(rq):
	pass # TODO!!!
	

@rt.get('/join')
async def join(rq):
	return hr(html.join(ws_url(rq), _html_fields(fields.PERSON, None, text.your), fields.PERSON.keys()))

@rt.get('/invite')
async def invite(rq):
	return hr(html.invite(ws_url(rq), _html_fields(fields.PERSON, None, text.friends), fields.PERSON.keys()))


@rt.get('/users')
async def users(rq):
	return hr(html.users(ws_url(rq), await db.get_users(await dbc(rq))))


@rt.get('/list_people', name = 'list_people')
async def list_people(rq):
	return hr(html.list_people(await db.get_persons(await dbc(rq))))


# Websocket -------------------------------------------------------------------

class Ws: # Namespace for websocket handler methods
	
	async def ignore_message(hd):
		l.info('ignore_message() - probably a spurious (post-handshake) "init"')

	async def ping_pong(hd):
		#l.info('ping_pong()') # uncomment to confirm heartbeat
		pass # nothing to do

	async def test(hd):
		l.debug('test()');
		action = hd.payload['action']
		match action:
			case 'test1':
				await wsr_send_task(hd, 'test1', html.test1('test content...'))
			case _:
				l.error(f'Action "{action}" not recognized!')


	async def handle(handler, hd):
		# This wrapper calls `handler(hd)`, but places the call in a try/except to handle unhandled exceptions meaningfully
		try:
			await handler(hd)
		except Exception as e:
			await db.rollback(hd.dbc)
			reference = ''.join(random_choices(ascii_uppercase, k=6))
			l.error(f'ERROR reference ID: {reference} ... details/traceback:')
			l.error(traceback.format_exc())
			await wsr_send_task(hd, 'internal_error', html.error(f'Internal error; please refer to with this error ID: {reference}'))

	async def join(hd):
		await Ws._join_or_invite(hd, True, text.your)

	async def invite(hd):
		await Ws._join_or_invite(hd, False, text.friends)
		
	async def filtersearch(hd):
		text = hd.payload['text']
		if text == '**repeat':
			text = hd.state.get('latest_filtersearch_text', '')
		else:
			hd.state['latest_filtersearch_text'] = text
		query = hd.payload['query']
		match query:
			case 'users':
				users = await db.get_users(await dbc(hd.rq), like = text, active = not hd.payload['include_inactives'])
				await wsr_send_task(hd, 'content', html.user_table(users))
			case _:
				raise ex.UmException('filtersearch query "{query}" not recognized!')

	async def get_detail(hd):
		table = hd.state['detail_table'] = hd.payload['table']
		id = int(hd.payload.get('id'))
		if not id:
			id = hd.state['detail_got_data']['id'] # if this fails (unknown-key exception), then it's a true exception - this should exist if id was not in payload!
		match table:
			case 'user':
				data = await db.get_user(hd.dbc, id, ', '.join(fields.USERNAME.keys()))
				await wsr_send_task(hd, 'dialog', html.detail(fields.USERNAME, data, None))
			case 'person':
				data = await db.get_person(hd.dbc, id, ', '.join(fields.PERSON.keys()))
				await wsr_send_task(hd, 'dialog', html.detail(fields.PERSON, data, 'get_more_person_detail'))
			case _:
				raise ex.UmException('detail query for table "{table}" not recognized!')
		data['id'] = id
		hd.state['detail_got_data'] = data

	async def set_detail(hd):
		data = hd.payload
		got_data = hd.state['detail_got_data']
		send_success = lambda arg: hd.wsr.send_json({
			'task': 'change_detail_success',
			'message': html.info(text.change_detail_success.format(change = f'"{arg}"')).render(),
		})
		table = hd.state['detail_table']
		match table:
			case 'user':
				if await _invalids(hd, data, fields.USERNAME): 
					return # if there WERE invalids, wsr.send_json() was already done within
				un = data['username']
				if un != got_data['username'] and await db.username_exists(hd.dbc, un):
					await wsr_send_task(hd, 'detail_message', html.error(text.Valid.username_exists))
					return # finished
				#else all good, move on!
				await db.update_user(hd.dbc, got_data['id'], fields.USERNAME.keys(), data)
				await send_success(un)
			case 'person':
				if await _invalids(hd, data, fields.PERSON): 
					return # if there WERE invalids, wsr.send_json() was already done within
				#else all good, move on!
				first, last = data['first_name'], data['last_name']
				await db.set_person(hd.dbc, got_data['id'], first, last)
				await send_success(f'{first} {last}')
			case _:
				raise ex.UmException('set_detail() for table "{table}" not recognized!')
		#TODO: clear out hd.state!

	async def get_more_person_detail(hd, message = None):
		id = hd.state['detail_got_data']['id']
		emails = await db.get_person_emails(hd.dbc, id)
		phones = await db.get_person_phones(hd.dbc, id)
		await wsr_send_task(hd, 'dialog', html.more_person_detail(emails, phones))
		if message:
			await wsr_send_task(hd, 'detail_message', html.info(message))

	async def get_mpd_detail(hd):
		table = hd.state['mpd_detail_table'] = hd.payload['table']
		id = hd.payload.get('id', 0)
		match table:
			case 'email':
				data = await db.get_email(hd.dbc, id) if id else {'email': ''}
				await wsr_send_task(hd, 'dialog', html.mpd_detail(fields.EMAIL, data))
			case 'phone':
				data = await db.get_phone(hd.dbc, id) if id else {'phone': ''}
				await wsr_send_task(hd, 'dialog', html.mpd_detail(fields.PHONE, data))
		data['id'] = id
		hd.state['mpd_got_data'] = data

	async def set_mpd_detail(hd):
		data = hd.payload
		table = hd.state['mpd_detail_table']
		person_id = hd.state['detail_got_data']['id']
		detail_id = hd.state['mpd_got_data']['id']
		match table:
			case 'email':
				if await _invalids(hd, data, fields.EMAIL):
					return # if there WERE invalids, wsr.send_json() was already done within
				#else all good, move on!
				if detail_id == 0:
					await db.add_email(hd.dbc, person_id, data['email'])
				else:
					await db.set_email(hd.dbc, detail_id, data['email'])
			case 'phone':
				if await _invalids(hd, data, fields.PHONE): 
					return # if there WERE invalids, wsr.send_json() was already done within
				#else all good, move on!
				if detail_id == 0:
					await db.add_phone(hd.dbc, person_id, data['phone'])
				else:
					await db.set_phone(hd.dbc, detail_id, data['phone'])
		# Return to the original more-person-detail page, showing all phones and emails for the person:
		fn, ln = hd.state['detail_got_data']['first_name'], hd.state['detail_got_data']['last_name']
		await Ws.get_more_person_detail(hd, text.change_detail_success.format(change = f'{text.detail_for} "{fn} {ln}"'))


		



	async def _join_or_invite(hd, send_username_fieldset, label_prefix):
		send_person_fs = lambda: _send_fieldset(hd, text.name,
									_html_fields(fields.PERSON, None, label_prefix), fields.PERSON.keys(), text.next)
		send_email_fs = lambda: _send_fieldset(hd, text.email,
									_html_fields(fields.EMAIL, None, label_prefix), fields.EMAIL.keys(), text.next)
		send_phone_fs = lambda: _send_fieldset(hd, text.phone,
									_html_fields(fields.PHONE, None, label_prefix), fields.PHONE.keys(), text.next)
		send_username_fs = lambda username_hint: _send_fieldset(hd, text.username,
									_html_fields(fields.NEW_USERNAME, {'username': username_hint}, label_prefix), fields.NEW_USERNAME.keys(), text.next)
		send_password_fs = lambda: _send_fieldset(hd, text.password,
									_html_fields(fields.NEW_PASSWORD, None, label_prefix), fields.NEW_PASSWORD.keys(), text.finish)

		data = hd.payload
		match hd.state.get('action', 'add_person'): # assume 'add_person' (first action) if no action yet set
			case 'add_person':
				if await _invalids(hd, data, fields.PERSON):
					return # _invalids() handles invalid case, and there's nothing more to do here
				#else:
				await db.begin(hd.dbc) # work through ALL actions before committing (transaction) to DB
				hd.state['pid'] = await db.add_person(hd.dbc, data['first_name'], data['last_name'])
				hd.state['name'] = data # store name for later
				hd.state['action'] = 'add_email' # next action
				_bump_action(hd, 'add_email', 'add_person')
				await send_email_fs()

			case 'add_email':
				if await _invalids(hd, data, fields.EMAIL): 
					return # if there WERE invalids, wsr.send_json() was already done within
				if await _not_yet(hd, 'add_person'):
					await send_person_fs()
					return # finished
				#else all good, move on!
				await db.add_email(hd.dbc, hd.state['pid'], data['email'])
				_bump_action(hd, 'add_phone', 'add_email')
				await send_phone_fs()

			case 'add_phone':
				if await _invalids(hd, data, fields.PHONE):
					return # if there WERE invalids, wsr.send_json() was already done within
				if await _not_yet(hd, 'add_email'):
					await send_email_fs()
					return # finished
				#else all good, move on!
				await db.add_phone(hd.dbc, hd.state['pid'], data['phone'])
				username_suggestion = await db.suggest_username(hd.dbc, hd.state['name'])
				hd.state['username_suggestion'] = username_suggestion
				if send_username_fieldset:
					_bump_action(hd, 'add_username', 'add_phone')
					await send_username_fs(username_suggestion)
				else: # we're dealing with /invite - finish the invite:
					# (note that this is more of a "mandatory invite", as an admin might use to build a team;
					# a more casual invite might simply involve somebody giving you the website name and
					# letting you sign up yourself; there's nothing "in between" - in-between-land is usually
					# just "annoy people" land)
					# create the user record:
					user_id = await db.add_user(hd.dbc, hd.state['pid'], username_suggestion)
					await db.commit(hd.dbc) # finally, commit it all
					# send a password-reset code via email, to the user's email:
					code = await db.generate_password_reset_code(hd.dbc, user_id)
					emails = await db.get_user_emails(hd.dbc, user_id)
					l.debug(f'inviting new user ({hd.state["name"]}) via email: {emails[0]["email"]}')
					# TODO!
					# notify inviter of success:
					_bump_action(hd, 'finished') # is add_phone really "right" here; hardly matters when 'finished' is our new state
					await wsr_send_task(hd, 'success', html.invite_succeeded(hd.state['name']))

			case 'add_username':
				if await _invalids(hd, data, fields.NEW_USERNAME): 
					return # if there WERE invalids, wsr.send_json() was already done within
				if await _not_yet(hd, 'add_phone'):
					await send_phone_fs()
					return # finished
				# else, add one more validation step: confirm that the username isn't already taken:
				if await db.username_exists(hd.dbc, data['username']):
					await wsr_send_task(hd, 'message', html.error(text.Valid.username_exists))
					return # finished
				#else all good, move on!
				hd.state['user_id'] = await db.add_user(hd.dbc, hd.state['pid'], data['username'])
				_bump_action(hd, 'add_password', 'add_username')
				await send_password_fs()

			case 'add_password':
				if await _invalids(hd, data, fields.NEW_PASSWORD): 
					return # if there WERE invalids, wsr.send_json() was already done within
				if await _not_yet(hd, 'add_username'):
					await send_username_fs(hd.state['username_suggestion'])
					return # finished
				#else, add one more validation step: confirm passwords are identical:
				if data['password'] != data['password_confirmation']:
					await wsr_send_task(hd, 'message', html.error(text.Valid.password_match))
					return # finished
				#else all good, move on!
				await db.reset_user_password(hd.dbc, hd.state['user_id'], data['password'])
				await db.commit(hd.dbc) # finally, commit it all
				_bump_action(hd, 'finished')
				await wsr_send_task(hd, 'success', html.join_succeeded())



WS_HANDLERS = {
	#task: handler_function
	'init': Ws.ignore_message, # real init/handshake already handled above; expect no more, ignore any
	'ping': Ws.ping_pong,
	'test': Ws.test,
	'join': Ws.join,
	'invite': Ws.invite,
	'filtersearch': Ws.filtersearch,
	'get_detail': Ws.get_detail,
	'set_detail': Ws.set_detail,
	'get_more_person_detail': Ws.get_more_person_detail,
	'get_mpd_detail': Ws.get_mpd_detail,
	'set_mpd_detail': Ws.set_mpd_detail,
}


@dataclass(slots = True)
class Hd: # handler data class; for grouping stuff more convenient to pass around in one object, when handling websocket commands
	rq: web.Request
	wsr: web.WebSocketResponse
	dbc: aiosqlite.Connection
	payload: dict | None = None
	state: dict = dataclass_field(default_factory = dict)

@rt.get('/_ws')
async def _ws(rq):
	wsr = web.WebSocketResponse()
	await wsr.prepare(rq)
	rq.app[_websockets].add(wsr)

	try:
		# Handshake carefully (necessary... see code/comments below for some detail, as well as ws.onopen() in *.js):
		l.info('New websocket connection established; hand-shaking...')
		await wsr.send_json({'task': 'init'})
		while True:
			try:
				payload = await wsr.receive_json(timeout = 0.2)
				assert payload['task'] == 'init', "initial message must be an 'init' response"
				break # out of while loop
			except asyncio.TimeoutError as e: # timed out; try again:
				await wsr.send_json({'task': 'init'}) # it seems that initial sends will often fail; even though the web socket was set up by the client side, initially, and we're handling the opening of this socket here in this function, and have called wsr.prepare() and everything... still, sometimes the initial 'init' sent goes unheaded; likewise, if we initialize the send from the client, it often isn't read here.  One solution seems to be to always wait a second before sending the initial, but this tight while-loop is more robust
		l.info('... "init" handshake complete; websocket ready for normal messages.')

		# Now we can begin indefinitely processing normal messages:
		hd = Hd(rq, wsr, await dbc(rq))
		async for msg in wsr:
			match msg.type:
				case WSMsgType.ERROR:
					raise wsr.exception()
				case WSMsgType.TEXT:
					hd.payload = json.loads(msg.data)
					await Ws.handle(WS_HANDLERS[hd.payload['task']], hd)
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


# Utils -----------------------------------------------------------------------


async def _invalids(hd, data, fields):
	if invalids:= valid.validate(data, fields):
		# prompt user with message - first invalid in invalids (one at a time works for such a small fieldset):
		await wsr_send_task(hd, 'message', html.error(list(invalids.values())[0]))
	return invalids

def _bump_action(hd, next_action, current_action = None):
	if 'completed' not in hd.state:
		hd.state['completed'] = []
	hd.state['completed'].append(current_action)
	hd.state['action'] = next_action

async def _not_yet(hd, required_action):
	if completed := hd.state.get('completed'):
		if required_action in completed:
			return False # good to continue normall processing
	#else:
	hd.state['action'] = required_action
	return True # "true, NOT YET ready to move on!"

def _html_fields(fieldset, data = None, label_prefix = None, invalids = None):
	return [field.html_field.build(name, data, label_prefix, invalids) \
		for name, field in fieldset.items()]

async def _send_fieldset(hd, fieldset_title, html_fields, field_names, button_title):
	await hd.wsr.send_json({
		'task': 'show_fieldset', 
		'fieldset': html.ws_fieldset(fieldset_title, html_fields, field_names, button_title).render(),
	})
