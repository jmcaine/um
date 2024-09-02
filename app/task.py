__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from collections.abc import Callable
from dataclasses import dataclass, field as dataclass_field

from . import db
from . import ws

l = logging.getLogger(__name__)


@dataclass(slots = True)
class Task:
	handler: Callable[[], None]
	state: dict = dataclass_field(default_factory = dict)

def started(hd, handler):
	if not hd.task:
		hd.task = Task(handler)
		return False # wasn't already started (though it is now, so next call will return True)
	elif hd.task.handler != handler:
		hd.prior_tasks.append(hd.task)
		hd.task = Task(handler)
		return False # wasn't already started (though it is now, so next call will return True)
	#else:
	return True # task already started

async def finished(hd, revert = True):
	if hd.payload.get('finished'):
		await finish(hd, revert)
		return True # yes, finished
	return False # no, not finished

async def finish(hd, revert = True):
	if revert:
		try: await db.rollback(hd.dbc) # if a transaction was started, normal processing should have performed the COMMIT when all finished well; if we're here, and that's not done, we assume responsibility for rolling back unfinished DB business
		except: pass # move on, even if rollback failed (e.g., there might not even be an outstanding transaction)
		if len(hd.prior_tasks) > 0: # no-op if there ARE no prior tasks (just stick with current task)
			hd.task = hd.prior_tasks.pop()
	await hd.task.handler(hd, revert)

def clear_all(hd):
	hd.task = None
	hd.prior_tasks = []
