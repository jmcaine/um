__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging
import traceback

from functools import wraps
from string import ascii_uppercase

from random import choices as random_choices

from . import db
from . import html
from . import shared
from . import text


l = logging.getLogger(__name__)

send = lambda hd, task, **kwargs: hd.wsr.send_json(dict({'task': task}, **kwargs))
send_content = lambda hd, task, content, **kwargs: send(hd, task, content = content.render(), **kwargs)
send_sub_content = lambda hd, container, content, **kwargs: send_content(hd, 'sub_content', content, container = container, **kwargs)

_handlers = {}

@shared.doublewrap
def handler(func, auth_func = None):
	@wraps(func)
	async def inner(hd, *args, **kwargs):
		try:
			if auth_func and not await auth_func(hd, hd.uid):
				await send_content(hd, 'banner', html.error(text.auth_required))
				return # done
			#else:
			await func(hd, *args, **kwargs)
		except Exception as e:
			try: await db.rollback(hd.dbc)
			except: pass # move on, even if rollback failed (e.g., there might not even be an outstanding transaction)
			reference = ''.join(random_choices(ascii_uppercase, k=6))
			l.error(f'ERROR reference ID: {reference} ... details/traceback:')
			l.error(traceback.format_exc())
			await send_content(hd, 'banner', html.error(text.internal_error.format(reference = reference)))
	module = func.__module__
	global _handlers
	if module not in _handlers:
		_handlers[module] = {}
	_handlers[module][func.__name__] = inner
	return inner


