__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import io
import logging
import random
import re
import string

from dataclasses import dataclass, field as dataclass_field

import cv2 # pip install opencv-python
from PIL import Image # pip install Pillow

from . import db
from . import html
from . import settings
from . import task
from . import text
from . import ws

from .admin import authorize as is_admin
from .messages_const import *

from .const import *


l = logging.getLogger(__name__)


async def active(hd, user_id):
	return (await db.get_user(hd.dbc, user_id, 'active'))['active']


@ws.handler
async def enter_module(hd):
	hd.rq.app['active_module'] = 'app.messages'
	hd.state['message_notify'] = NewMessageNotify.inject

@ws.handler
async def exit_module(hd):
	hd.state['message_notify'] = NewMessageNotify.tease

@ws.handler(auth_func = active)
async def messages(hd, reverting = False):
	if hd.rq.app['active_module'] != 'messages': # frequently, messages() is called from elsewhere (other than user request), e.g., as a default startup.  In this case, the normal framework caller of our enter_module() doesn't get called, so we need to call it; this is the exception, and is because this method is a little special
		await enter_module(hd)
	if reverting and hd.state['message_notify'] != NewMessageNotify.reload: # TODO: DEPRECATE NewMessageNotify.reload
		return # nothing to do here - don't reload messages if reverting, unless NewMessageNotify.reload

	just_started = task.just_started(hd, messages) # have to do this first, before referencing hd.task.state, below
	filt = hd.task.state['filt'] = hd.payload.get('filt', hd.task.state.get('filt', Filter.new)) # prefer filt sent in payload, then filt already recorded, and, finally, if nothing, default to viewing `new` messages (only)
	hd.task.state['injects'] = set()

	if just_started:
		await ws.send_sub_content(hd, 'topbar_container', html.messages_topbar(await is_admin(hd, hd.uid)))
		await ws.send_content(hd, 'content', html.messages_container())
		# sending the above can happen almost immediately; as message lookup might take a moment longer, we'll do it only subsequently (below), even for the very first load, so that the user at least has the framework of the page to see, and the "loading messages..." to see (or, hopefully not, if things are fast enough!)
	await ws.send_sub_content(hd, 'filter_container', html.messages_filter(filt))
	if news := filt == Filter.new:
		hd.task.state['skip'] = 0 # start at "top" (oldest "new" messages), and only load new messages when user scrolls to bottom
	else:
		hd.task.state['skip'] = -1 # start at "bottom" of "last page" (newest messages), and load older messages when user scrolls to top
	ms = await _get_messages(hd)
	hd.task.state['skip'] += len(ms) if hd.task.state['skip'] >= 0 else -len(ms)
	await ws.send_content(hd, 'messages', html.messages(ms, hd.uid, hd.admin, news, None, news), scroll_to_bottom = 0 if news else 1, filt = filt)
	if len(ms) > 0:
		hd.task.state['last_thread_patriarch'] = ms[-1]['reply_chain_patriarch'] if news else ms[0]['reply_chain_patriarch'] # last message, if we're scrolling down; first if up

@ws.handler(auth_func = active)
async def more_new_messages_forward_only(hd): # this is only called if a screen is taller than the default # of messages can fill, so more messages are immediately needed; note that a skip of -1 canNOT result in a more_new_messages call or we'll have an infinite loop because the number of "newest" messages fits on screen, with room for more, but calling for more incessantly won't result in any change; this method is ONLY for forward (skipping-forward, from older "new" messages) orientations
	if hd.task.state['skip'] > 0:
		return await more_new_messages(hd)
	#else no-op

@ws.handler(auth_func = active)
async def more_new_messages(hd): # inspired by "down-scroll" below "bottom", or a screen that isn't full of messages and can take more new ones on bottom
	if hd.task.state.get('filt') != Filter.new:
		return # nothing to do - all filters except `new` show the "most current (most currently stashed)" at the bottom, in the first load, so there are never any "newer" messages to load beyond those
	#else:
	assert(hd.task.state['skip'] >= 0) # true by virtue of filtering new messages - we're only skipping 'forward'
	ms = await _get_messages(hd)
	if len(ms) > 0:
		await ws.send_content(hd, 'more_new_messages', html.messages(ms, hd.uid, hd.admin, True, hd.task.state['last_thread_patriarch']))
		hd.task.state['skip'] += len(ms)
		hd.task.state['last_thread_patriarch'] = ms[-1]['reply_chain_patriarch']
	else:
		await ws.send(hd, 'no_more_new_messages')

@ws.handler(auth_func = active)
async def more_old_messages(hd): # inspired by "up-scroll" above "top"
	if hd.task.state['filt'] == Filter.new:
		return # nothing to do - 'new' load always starts with the "oldest new" messages; scrolling "down" loads "newer new" messages but scrolling to the top never needs to invoke any lookups, as there's nothing more to load above the "oldest new" on top
	#else:
	assert(hd.task.state['skip'] < 0) # true by virtue of filtering 'new' messages - we're only skipping 'backward'
	ms = await _get_messages(hd)
	if len(ms) > 0:
		await ws.send_content(hd, 'more_old_messages', html.messages(ms, hd.uid, hd.admin, False, hd.task.state['last_thread_patriarch']))
		hd.task.state['skip'] -= len(ms)
		hd.task.state['last_thread_patriarch'] = ms[0]['reply_chain_patriarch']
	#else: nothing more to do - don't ws.send() anything or update anything!  User has scrolled to the very top of the available messages for the given filter

async def _get_messages(hd):
	return await db.get_messages(hd.dbc, hd.uid,
													deep = hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													filt = hd.task.state['filt'],
													skip = hd.task.state['skip'],
													ignore = hd.task.state['injects'],
													limit = settings.messages_per_load)


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
	elif not await task.finished(hd): # dialog-box could have been "canceled" (if so, don't do the following! Rather, just let the finish finish!)
		# user did something like filtersearch update, and we're back here with a new set of drafts to present:
		await _send_message_draft_table(hd, drafts)

@ws.handler(auth_func = active)
async def brand_new_message(hd):
	await edit_message(hd, False, await db.new_message(hd.dbc, hd.uid))

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def edit_message(hd, reverting = False, message_id = None):
	first = task.just_started(hd, edit_message)
	message_id = hd.task.state['message_id'] = message_id or (hd.payload.get('message_id') or hd.task.state.get('message_id')) # using hd.task.state['message_id'] as a preserver - we may detour on a subtask, then revert here, and have lost arg message_id or payload message_id
	if not reverting and await task.finished(hd): # user pushed ▼, to save draft for later
		await ws.send_content(hd, 'banner', html.info(text.draft_saved)) # send banner to prior-task
		return # finished
	#else:
	if first or reverting:
		# load message: (note that send_message() handles the "send" ► action)
		message = await db.get_message(hd.dbc, hd.uid, message_id)
		await ws.send_content(hd, 'edit_message', html.edit_message(message_id, message['message']), message_id = message_id)


@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def delete_draft(hd):
	# NOTE: not an independent task; processing expected from within 'new_message' task, during choose_message_draft processing
	await db.delete_message(hd.dbc, hd.payload['message_id'])
	banner = text.draft_trashed
	drafts = await _get_message_drafts(hd)
	if not drafts:
		banner += '  ' + text.no_more_drafts
	await ws.send_content(hd, 'detail_banner', html.info(banner))
	await _send_message_draft_table(hd, drafts)


_strip_trailing_br = lambda content: content.rstrip('<br>')

@ws.handler(auth_func = active)
async def save_wip(hd):
	await db.save_message(hd.dbc, hd.payload['message_id'], hd.payload['content'])

@ws.handler(auth_func = active)
async def send_message(hd, message_id = None, banner = True):
	mid = message_id or hd.payload.get('message_id')
	message = await db.send_message(hd.dbc, hd.uid, mid)
	match message:
		case db.Send_Message_Result.NoTags:
			await message_tags(hd, send_after = True) # 'send_after' causes this send_message() to be tried again immediately after tags are set (at end of message_tags processing)
			return # finished here
		case db.Send_Message_Result.EmptyMessage:
			await ws.send_content(hd, 'detail_banner', html.error(text.cant_send_empty_message))
			return # finished here
	# otherwise it's a real message...
	await task.finish(hd) # actually finishing the edit_message task, here! (as send_message is not an actual task, it's just a helper called from within the context of editing)
	for each_hd in hd.rq.app['hds']: # including delivery to self
		await deliver_message(each_hd, message)
	if banner:
		await ws.send_content(hd, 'banner', html.info(text.message_sent))

@ws.handler(auth_func = active)
async def send_reply(hd):
	mid = hd.payload['message_id']
	if hd.payload.get('to_sender_only') == '1': # replier wishes to send only to the original (parent_mid) sender, and leave others out of it...
		await db.add_tag_to_message(hd.dbc, mid, (await db.get_author_tag(hd.dbc, hd.payload['parent_mid']))['id'])
	else: # replier wishes to send "to all original recipients", instead...
		await db.set_reply_message_tags(hd.dbc, mid)
	message = await db.send_message(hd.dbc, hd.uid, mid)
	assert message != db.Send_Message_Result.NoTags, 'Should be impossible - a reply always inherits the tags of the parent message.'
	if message == db.Send_Message_Result.EmptyMessage:
		await ws.send(hd, 'remove_reply_container', message_id = mid)
	else:
		stashable = hd.task.state.get('filt') == Filter.new
		_, html_message = html.message(message, hd.uid, hd.admin, stashable, message['reply_chain_patriarch'], injection = True)
		await ws.send_content(hd, 'post_completed_reply', html_message, message_id = mid)
		hd.state['active_reply'] = None # reset; no longer in active reply (until user starts or resumes another reply)
		for each_hd in hd.rq.app['hds']:
			if each_hd != hd:
				await deliver_message(each_hd, message)


@dataclass(slots = True)
class Active_Reply:
	mid: int
	parent_mid: int
	patriarch_mid: int | None

@ws.handler(auth_func = active)
async def compose_reply(hd):
	parent_mid = hd.payload['message_id']
	patriarch_id = await db.get_patriarch_message_id(hd.dbc, parent_mid)
	selection = hd.payload.get('selection') # TODO: (int, int) range? or actual text, or...?
	new_mid = await db.new_message(hd.dbc, hd.uid, parent_mid, patriarch_id)
	hd.task.state['injects'].add(new_mid) # this new_mid will already be in view, for author of the reply, and should not be loaded upon a scroll-down (incurring a new-message-load)
	hd.state['active_reply'] = Active_Reply(new_mid, parent_mid, patriarch_id) # while replying, tell other replies-to-the-same-parent-or-grandparent-message to be injected ABOVE:
	# load (empty) reply-box: (note that send_reply() handles the "send" ► action)
	await ws.send_content(hd, 'inline_reply_box', html.inline_reply_box(new_mid, parent_mid), message_id = new_mid, parent_mid = parent_mid)


async def deliver_message(hd, message):
	'''
	Consider scenarios - 
	1) user is staring at (or staring away from) new-messages screen - new messages can pop up (on top, according to scheme)
		likewise, replies can pop up in-place
		both of these can be achieved by a reload, which will have the added effect (benefit) of limiting the showing messages to the normal #
		SO, for this scenario, we just want a message-list reload!
		UPDATE: we've discovered that DOM-inserts that are out of scroll-view (above or below visible scrolled area) do NOT cause content to move up or down
		- that's great, and re-motivates the possibility of always(?) doing DOM inserts instead of list reloads.  This COULD be nicer ergonomically when, e.g.,
		somebody has scrolled WAY down (or up), causing a pretty large list to be loaded; in such a case, a re-load would potentially shorten that list up
		to the viewed region of messages (which should be fine for the moment), but if the user really wants that huge bunch of messages loaded... well, he'll be disappointed
	2) user is typing a reply - replies to the same thread want to pop "insert" above the active text/typing box; no reload here - just a DOM insert, so that the text/typing doesn't have to re-load (alternately, we COULD reload, as the active reply should be periodically auto-saving, and we could do one more (last) auto-save before the reload, and, of course, re-load with the editing reply still in edit mode and the carat where it belongs, but this could get tricky(?) if the user is precisely in the middle of fast typing; e.g., perhaps a keystroke will be lost?!
		Note that we KNOW this detail (whether a user is typing a reply) here, server-side - we don't have to send to recipients and make decisions client-side.
		SO, for this scenario, we care about the message the user is replying to; if it shares inheritance, we have to DOM-insert; if it does not, we can treat this as if it's scenario 3 (below)
		NOTE also with the "UPDATE" above, #1, the leaning is toward always inserting, here too, and always inserting in the expected location, *almost* always where a user would expect to see the message on a fresh load (an inject above a WIP reply, of another user's reply, might be a bit of a reasonable exception).
	3) user is doing something else in the application, not looking at messages at all (e.g., in "settings", or typing a completely new message...) but, in any event, NOT looking at (or ignoring) the normal "messages" screen
		SO, for this scenario, we want to send the teaser only!) - next time user goes to messages screen, it'll reload properly
	'''
	mid = message['id']
	if await db.delivery_recipient(hd.dbc, hd.uid, mid):
		placement = None
		match hd.state.get('message_notify'):
			case NewMessageNotify.tease:
				if not message['deleted']:
					await ws.send(hd, 'deliver_message_teaser', teaser = message['teaser'])
			case NewMessageNotify.reload: # TODO: DEPRECATE!
				l.warning(f'!!! RELOADING! (DEPRECATE ME!)')
				await messages(hd)
			case NewMessageNotify.inject:
				# Default: place this new message at the end ('beforeend') of the parent, after all other replies (that have already come in)
				reference_mid = message['reply_to'] # Note: could be None if message has no parent (is not a reply) (in this case, `placement` will be disregarded by inject_deliver_new_message)
				placement = 'beforeend' # parent is a super-container, with all replies "within", so stick this within that container, before the end of it (after the previous last reply)
				# BUT, if active reply is underway...
				if active_reply := hd.state.get('active_reply'):
					if active_reply.parent_mid == message['reply_to']: # message (to be delivered) shares the same parent...
						reference_mid = active_reply.mid # place injection just above active reply (so that user can see it even while authoring active reply)
						placement = 'beforebegin'
					elif active_reply.patriarch_mid == message['reply_chain_patriarch']: # message (to be delivered) shares the same patriarch...
						reference_mid = active_reply.parent_mid # place injection just above parent (so that user can see it even while authoring active reply)
						placement = 'beforebegin'
					#else: just take the defaults set above - the injection can go wherever it belongs, even if it's off screen
				#NOTE: we DON'T add(mid) to state['injects'] here, prematurely - within inject_deliver_new_message, client-side, decision may be made to NOT add the message to the DOM! (see injected_message() signal)
				stashable = hd.task.state.get('filt') == Filter.new
				patriarch = None if reference_mid == None else message['reply_chain_patriarch'] # `None` means the message has no parent (is not a reply, so it will be "injected" at the bottom)
				_, html_message = html.message(message, hd.uid, hd.admin, stashable, patriarch, injection = True) # when `patriarch` is not None, `message`'s own reply_chain_patriarch has to be the patriarch
				await ws.send_content(hd, 'inject_deliver_new_message', html_message, new_mid = mid, reference_mid = reference_mid or 0, placement = placement)

@ws.handler(auth_func = active)
async def injected_message(hd):
	hd.task.state['injects'].add(hd.payload['message_id'])

@ws.handler(auth_func = active)
async def delete_message(hd):
	mid = hd.payload['message_id']
	await db.delete_message(hd.dbc, mid)
	# "deliver" the deleted message - its "deleted" state will result in inline removal of the message in real-time
	for each_hd in hd.rq.app['hds']: # including delivery to self
		await ws.send(each_hd, 'remove_message', message_id = mid)
	await ws.send_content(hd, 'banner', html.info(text.message_deleted))
	if hd.task and hd.task.handler == edit_message:
		await task.finish(hd) # actually finishing the edit_message task, here!

@ws.handler(auth_func = active)
async def message_tags(hd, reverting = False, send_after = False):
	just_started = task.just_started(hd, message_tags)
	send_after = hd.task.state['send_after'] = hd.payload.get('send_after', hd.task.state.get('send_after', send_after)) # prefer payload arg, then state already recorded, and, finally, if nothing, default to direct function arg; this preference order IS quite significant
	mid = hd.task.state['message_id'] = hd.payload.get('message_id', hd.task.state.get('message_id')) # ...similarly
	finished = hd.payload.get('finished') # just test first -- may need to post error to detail_banner, and not finish() yet, even if requested...
	if finished and send_after: # tricky: before task.finish(), we want to make sure that there are tags if send_after; in that case, or in the case of !send_after, we can finish(), but otherwise, need to post error - can't move on to sending the message if it has no tags!
		if not await db.has_tags(hd.dbc, mid):
			await ws.send_content(hd, 'detail_banner', html.error(text.cant_send_message_without_recipients))
		else:
			await task.finish(hd)
			await send_message(hd, mid) # just go straight to sending the message
	elif finished: # but not send_after
		await task.finish(hd)
	elif just_started or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		await ws.send_content(hd, 'dialog', html.message_tags(await message_tags_table(hd, mid))) # send whole dialog
	elif not finished: # just in the middle of processing - need repaint...
		await ws.send_content(hd, 'sub_content', await message_tags_table(hd, mid), container = 'message_tags_table_container') # just reload the tags_table

async def message_tags_table(hd, mid):
	limit = 10
	utags, otags = await db.get_message_tags(hd.dbc, mid, hd.uid,
													limit = limit,
													active = not hd.task.state.get('filtersearch_include_extra'),
													like = hd.task.state.get('filtersearch_text'),
													include_others = True)
	return html.message_tags_table(utags, otags, mid, limit)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def remove_tag_from_message(hd):
	await _remove_or_add_tag_to_message(hd, db.remove_tag_from_message, text.removed_tag_from_message)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def add_tag_to_message(hd):
	await _remove_or_add_tag_to_message(hd, db.add_tag_to_message, text.added_tag_to_message)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def stash(hd):
	await db.stash_message(hd.dbc, hd.payload['message_id'], hd.uid)
	if hd.task.state['skip'] > 0:
		hd.task.state['skip'] -= 1

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def pin(hd):
	await db.pin_message(hd.dbc, hd.payload['message_id'], hd.uid)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def unpin(hd):
	await db.unpin_message(hd.dbc, hd.payload['message_id'], hd.uid)

@ws.handler(auth_func = active) # TODO: also confirm user is owner of this message (or admin)!
async def upload_files(hd, meta, payload):
	message_id = meta['partition_id'] # partition scheme, for message file-attachments, is the message_id
	pos = 0
	filenames = []
	for fil in meta['files']:
		name = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(5)) + '_' + fil['name'] # TODO: sanitize fil['name'] first!!  NOTE that we canNOT have commas in filenames (see _mega_message_select in db.py and the conversation around DISTINCT - we can't choose delimiter in the GROUP_CONCAT - we get a comma whether we want it or not, and this is the best way to get that list, all in one query (like tag names))
		filenames.append(name)
		size = fil['size']
		fp = k_upload_path + name

		if name.lower().endswith(k_video_formats):
			with open(fp, "wb") as file:
				file.write(payload[pos:pos+size])
			vid = cv2.VideoCapture(fp)
			vid.set(cv2.CAP_PROP_POS_FRAMES, int(vid.get(cv2.CAP_PROP_FRAME_COUNT)) / 2) # get thumbnail from half-way frame (because the first umpteen are often black, in a fade-from-black)
			result, image = vid.read()
			assert result == True, "FAILED to capture frame!"
			height, width = image.shape[:2]
			th_width, th_height, overlay_file = \
				(k_thumbnail_size, k_thumbnail_size * 9 // 16, k_landscape_video_overlay) if width > height else \
				(k_thumbnail_size * 9 // 16, k_thumbnail_size, k_portrait_video_overlay)
			thumb = cv2.resize(image, (th_width, th_height))
			overlay = cv2.imread(overlay_file, cv2.IMREAD_UNCHANGED) # Load with alpha channel
			bg, alpha = overlay[:, :, :3], overlay[:, :, 3] / 255.0  # Normalize alpha to 0-1 range
			roi = thumb[0:th_height, 0:th_width]
			for c in range(3):
				roi[:, :, c] = roi[:, :, c] * (1 - alpha) + bg[:, :, c] * alpha
			cv2.imwrite(fp + k_thumb_appendix, thumb)

		elif name.lower().endswith(k_image_formats):
			img = Image.open(io.BytesIO(payload[pos:pos+size])).convert("RGB")
			img.save(fp)
			img.thumbnail((k_thumbnail_size, k_thumbnail_size)) # modifies img in-place
			img.save(fp + k_thumb_appendix)

		elif name.lower().endswith(k_audio_formats): # TODO!!!
			with open(fp, "wb") as file:
				file.write(payload[pos:pos+size])
		else:
			l.error(f'upload of file {name} FAILED - is not in set of video formats ({k_video_formats}) or image formats ({k_image_formats}) or audio formats ({k_audio_formats})!')
		pos += size
	if filenames: # indicating files were actually uploaded and processed
		await db.add_message_attachments(hd.dbc, message_id, filenames)
		# NOTE - this is not atomic, and we're not revisiting and deleting files just written to file, above; so, rather, run a periodic script that deletes media that is not referenced in DB!  This will also allow for quick "deletion" (by removal of file reference in DB), that can be followed later by actual file removal (possibly also handy for "undo"ability, if don't wait too long.)

	content = html.thumbnail_strip(filenames)
	await ws.send_content(hd, 'files_uploaded', content, message_id = message_id)

# -----------------------------------------------------------------------------

async def _get_message_drafts(hd):
	return await db.get_message_drafts(hd.dbc, hd.uid,
										include_trashed = hd.task.state.get('filtersearch_include_extra'),
										like = hd.task.state.get('filtersearch_text'))

async def _send_message_draft_table(hd, drafts):
	await ws.send_content(hd, 'sub_content', html.choose_message_draft_table(drafts), container = 'choose_message_draft_table_container')

async def _remove_or_add_tag_to_message(hd, db_func, banner_text):
	tid = int(hd.payload['tag_id'])
	mid = int(hd.payload['message_id'])
	await db_func(hd.dbc, mid, tid)
	await ws.send_content(hd, 'sub_content', await message_tags_table(hd, mid), container = 'message_tags_table_container')
	tag = await db.get_tag(hd.dbc, tid, 'name')
	await ws.send_content(hd, 'detail_banner', html.info(banner_text.format(name = tag['name'])))



