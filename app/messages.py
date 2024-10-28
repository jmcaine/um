__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging
import re

from dataclasses import dataclass, field as dataclass_field

from . import db
from . import html
from . import task
from . import text
from . import ws

from .admin import authorize as is_admin

l = logging.getLogger(__name__)


async def active(hd, user_id):
	return (await db.get_user(hd.dbc, user_id, 'active'))['active']


@ws.handler(auth_func = active)
async def messages(hd, reverting = False):
	if task.just_started(hd, messages):
		hd.state['message_delivery'] = 'whole' # TODO - make real; this is just a placeholder!!
		hd.task.state['filt'] = 'new' # default to viewing new messages (only)
		await ws.send_content(hd, 'content', html.messages_page(await is_admin(hd, hd.uid)))
		# sending the above can happen almost immediately; as message lookup might take a moment longer, we'll do it only subsequently (below), even for the very first load, so that the user at least has the framework of the page to see, and the "loading messages..." to see (or, hopefully not, if things are fast enough!)
	if filt := hd.payload.get('filt'):
		hd.task.state['filt'] = filt
	ms = await db.get_messages(hd.dbc, hd.uid,
													deep = not hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													filt = hd.task.state['filt'])
	await ws.send_content(hd, 'sub_content', html.messages(ms), container = 'messages_container')

@ws.handler(auth_func = active)
async def new_message(hd, reverting = False):
	if reverting:
		await task.finish(hd) # just bump back another step (no value in reverting to this transient task)
		return # finished here
	#else:
	first = task.just_started(hd, new_message)
	drafts = await _get_message_drafts(hd)
	if not drafts:
		await brand_new_message(hd)
		return # nothing else to do here
	#else, we have drafts to present...
	if first:
		await ws.send_content(hd, 'dialog', html.choose_message_draft(drafts))
	elif not await task.finished(hd): # dialog-box could have been "canceled"
		# user did something like filtersearch update, and we're back here with a new set of drafts to present:
		await _send_message_draft_table(hd, drafts)

@ws.handler(auth_func = active)
async def brand_new_message(hd):
	await edit_message(hd, False, await db.new_message(hd.dbc, hd.uid))

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def edit_message(hd, reverting = False, message_id = None):
	if reverting and hd.task.state['resume_sending_on_revert']:
		await send_message(hd) # just go straight (back) to sending the message
		return # finished here
	#else:
	if first := task.just_started(hd, edit_message):
		hd.task.state['message_id'] = message_id or hd.payload.get('message_id') or hd.task.state.get('message_id')
	elif not reverting and await task.finished(hd): # user pushed ▼, to save draft for later
		await ws.send_content(hd, 'banner', html.info(text.message_draft_saved)) # send banner to prior-task
		return # finished
	#else:
	if first or reverting:
		# load message: (note that send_message() handles the "send" ► action)
		message = await db.get_message(hd.dbc, hd.task.state['message_id'])
		await ws.send_content(hd, 'edit_message', html.edit_message(message["message"]))

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def trash_message(hd):
	# NOTE: not an independent task; processing expected from within 'new_message' task, during choose_message_draft processing
	await db.trash_message(hd.dbc, hd.payload['message_id'])
	banner = text.trash_succeeded
	drafts = await _get_message_drafts(hd)
	if not drafts:
		banner += '  ' + text.no_more_drafts
	await ws.send_content(hd, 'detail_banner', html.info(banner))
	await _send_message_draft_table(hd, drafts)

@ws.handler(auth_func = active)
async def save_wip(hd):
	await db.save_message(hd.dbc, hd.task.state['message_id'], hd.payload['content'])


@ws.handler(auth_func = active)
async def send_message(hd):
	mid = hd.task.state['message_id']
	match hd.payload.get('to_sender_only', -1): # versus "to all original recipients"; only really applies to replies...
		case 1: # yup, replier wishes to send only to the original (parent_mid) sender, and leave others out of it...
			await db.add_tag_to_message(hd.dbc, mid, (await db.get_author_tag(hd.dbc, hd.task.state['parent_mid']))['id'])
		case 0: # nope, rather, replier wishes to send "to all original recipients", instead...
			await db.set_reply_message_tags(hd.dbc, mid)
		#else, this isn't a "reply", and the message tags are already set by user (or they aren't and the next call will fail gracefully
	message = await db.send_message(hd.dbc, mid)
	match message:
		case db.Send_Message_Result.NoTags:
			await message_tags(hd, resume_sending_on_revert = True) # note: revert is to edit_message task; send_message isn't actually a task, it's just a helper-handler!
			return # finished here
		case db.Send_Message_Result.EmptyMessage:
			await ws.send_content(hd, 'detail_banner', html.error(text.cant_send_empty_message))
			return # finished here
	await task.finish(hd) # actually finishing the edit_message task, here!
	teaser = None # poor-man's cache
	for other_hd in hd.rq.app['hds']:
		teaser = await deliver_message(other_hd, message, teaser)
	await ws.send_content(hd, 'detail_banner', html.info(text.message_sent))

@ws.handler(auth_func = active)
async def preprocess(hd):
	hd.state['message_delivery'] = 'alert'

@dataclass(slots = True)
class MD_Inject:
	parent_id: int
	patriarch_id: int | None

@ws.handler(auth_func = active)
async def compose_reply(hd):
	started = task.just_started(hd, compose_reply)
	mid = hd.task.state['parent_mid'] = hd.payload['message_id']
	patriarch_id = await db.get_patriarch_message_id(hd.dbc, mid)
	selection = hd.payload.get('selection') # TODO: (int, int) range? or actual text, or...?
	# While replying, allow other replies to the same parent or grandparent message to be injected in real-time:
	hd.state['message_delivery'] = MD_Inject(mid, patriarch_id)
	new_mid = hd.task.state['message_id'] = await db.new_message(hd.dbc, hd.uid, mid, patriarch_id)
	# load (empty) reply-box: (note that send_message() handles the "send" ► action)
	await ws.send_content(hd, 'inline_reply_box', html.inline_reply_box(hd.payload.get('to_sender_only', 1)), message_id = mid)


async def deliver_message(hd, message, teaser):
	delivery = hd.state.get('message_delivery')
	if delivery:
		if await db.delivery_recipient(hd.dbc, hd.uid, message['id']):
			if delivery in ('teaser', 'whole'): # don't bother if just 'alert'
				if not teaser:
					teaser = make_teaser(message)
			match delivery:
				case 'alert':
					await ws.send(hd, 'deliver_message_alert')
				case 'teaser':
					#TODO: fix - shouldn't be doing a deliver_message; rather, deliver_teaser or something....
					await ws.send(hd, 'deliver_message', '', teaser = teaser)
				case 'whole':
					await ws.send(hd, 'deliver_message', message = html.message(message['message']).render(), teaser = teaser)
	return teaser # cache

def make_teaser(message):
	return strip_tags(message['message'][:50])[:20] # [:50] to just operate on opening portion of content, but then, once stripped of tags, whittle down to [:20]; if only one of these was used, "taggy" content would be rather over-shrunk or under-taggy content would be rather under-shrunk

def strip_tags(content):
	return re.sub('<.*', '', re.sub('<[^<]+?>', '..', content)) # TODO: improve this to regex-replace "<tag>" with empty string and </tag> with "..." and any (final) "<..." (incomplete open- or close-tag) with empty string (that part already done)

@ws.handler(auth_func = active)
async def message_tags(hd, reverting = False, resume_sending_on_revert = False):
	mid = hd.task.state['message_id'] # possibly (intentionally) stealing from prior task (BEFORE calling task.started())!
	hd.task.state['resume_sending_on_revert'] = resume_sending_on_revert # also setting this to PRIOR task, actually (on first entry, before just_started() call) - on purpose, to tell message-sending (e.g.) to send directly after this message-tag-selection operation is complete; no need to pause on (reverting to) that prior task for anything more
	if started := task.just_started(hd, message_tags):
		hd.task.state['message_id'] = mid # stolen from prior task; now a part of our task TODO: make this technique a PART of task.started(args)?!
	if started or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		await ws.send_content(hd, 'dialog', html.message_tags(await message_tags_table(hd)))
	elif not await task.finished(hd): # dialog-box could have been "closed"
		await ws.send_content(hd, 'sub_content', await message_tags_table(hd), container = 'message_tags_table_container')

async def message_tags_table(hd):
	utags, otags = await db.get_message_tags(hd.dbc, hd.task.state['message_id'],
													active = not hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													include_others = True)
	return html.message_tags_table(utags, otags)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def remove_tag_from_message(hd):
	await _remove_or_add_tag_to_message(hd, db.remove_tag_from_message, text.removed_tag_from_message)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def add_tag_to_message(hd):
	await _remove_or_add_tag_to_message(hd, db.add_tag_to_message, text.added_tag_to_message)


@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def archive(hd):
	await db.archive_message(hd.dbc, hd.payload['message_id'], hd.uid)
	await messages(hd)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def unarchive(hd):
	await db.unarchive_message(hd.dbc, hd.payload['message_id'], hd.uid)
	await messages(hd)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def pin(hd):
	await db.pin_message(hd.dbc, hd.payload['message_id'], hd.uid)
	await messages(hd)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def unpin(hd):
	await db.unpin_message(hd.dbc, hd.payload['message_id'], hd.uid)
	await messages(hd)


# -----------------------------------------------------------------------------

async def _get_message_drafts(hd):
	return await db.get_message_drafts(hd.dbc, hd.uid,
										include_trashed = hd.task.state.get('filtersearch_include_extra'),
										like = hd.task.state.get('filtersearch_text'))

async def _send_message_draft_table(hd, drafts):
	await ws.send_content(hd, 'sub_content', html.choose_message_draft_table(drafts), container = 'choose_message_draft_table_container')

async def _remove_or_add_tag_to_message(hd, func, banner_text):
	tid = int(hd.payload['tag_id'])
	await func(hd.dbc, hd.task.state['message_id'], tid)
	await ws.send_content(hd, 'sub_content', await message_tags_table(hd), container = 'message_tags_table_container')
	tag = await db.get_tag(hd.dbc, tid, 'name')
	await ws.send_content(hd, 'detail_banner', html.info(banner_text.format(name = tag['name'])))

