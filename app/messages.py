__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from . import db
from . import html
from . import task
from . import ws

from .admin import authorize as is_admin

l = logging.getLogger(__name__)


async def active(hd, user_id):
	return (await db.get_user(hd.dbc, user_id, 'active'))['active']


@ws.handler(auth_func = active)
async def messages(hd, reverting = False):
	if reverting:
		await ws.send(hd, 'hide_dialog')
	if not task.started(hd, messages):
		await ws.send_content(hd, 'content', html.messages_page(await is_admin(hd, hd.uid)))
	else:
		await ws.send_content(hd, 'sub_content', html.messages(), container = 'messages_container')

@ws.handler(auth_func = active)
async def edit_message(hd):
	if not task.started(hd, edit_message):
		hd.task.state['mid'] = hd.payload.get('mid', await db.new_message(hd.dbc, hd.uid)) # TODO: confirm that this only creates new_message IF mid not available!
		await ws.send_content(hd, 'edit_message', html.edit_message(), message_content = '')
	elif await task.finished(hd): # user pushed ▼, to save draft for later
		await ws.send_content(hd, 'banner', html.info(text.message_draft_saved))

@ws.handler(auth_func = active)
async def save_draft(hd):
	await db.save_message(hd.dbc, hd.task.state['mid'], hd.payload['content'])

@ws.handler(auth_func = active)
async def send_message(hd):
	await db.send_message(hd.dbc, hd.task.state['mid'])
	message = await db.get_message(hd.dbc, hd.task.state['mid'])
	await task.finish(hd) # actually finishing the edit_message task, here!
	for other_hd in hd.rq.app['hds']:
		await deliver_message(other_hd, message)
		
@ws.handler(auth_func = active)
async def deliver_message(hd, message):
	await ws.send_content(hd, 'deliver_message', html.message(message['message']))

