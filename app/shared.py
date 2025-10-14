__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

from . import html
from . import task
from . import valid
from . import ws


async def handle_invalid(hd, message, banner):
	await ws.send_content(hd, banner, html.error(message))


async def edit_detail(hd, task_fn, reverting, fetcher, title, fieldset, db_setter):
	if task.just_started(hd, task_fn) or reverting: # 'reverting' check is currently useless, but if sub-dialogs are added here, this is necessary to repaint the whole dialog
		hd.task.state['db_data'] = await fetcher(hd.dbc, int(hd.payload.get('id')))
		await ws.send_content(hd, 'dialog', html.dialog2(title, fieldset, hd.task.state['db_data']))
	elif not await task.finished(hd): # e.g., dialog-box could have been "canceled"
		data = hd.payload
		if await valid.invalids(hd, data, fieldset, handle_invalid, 'detail_banner'):
			return # if there WERE invalids, bannar was already sent within
		#else all good, move on!
		await db_setter(hd, data)
		await task.finish(hd)
