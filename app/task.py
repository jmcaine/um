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

def start(hd, handler):
	if not hd.task:
		hd.task = Task(handler)
		return True # just started
	elif hd.task.handler != handler:
		hd.prior_tasks.append(hd.task)
		hd.task = Task(handler)
		return True # just started
	#else:
	return False # task not just (now) started; may have been started already, in the past, though
	
def just_started(hd, handler):
	# Same as start(); that is, has the (side) effect of STARTING the task, but 'just_started' semantically helps caller understand the implications, and know that the task now "just started", or, indeed, did not (because it was already started some time in the past; in which case, this function is a no-op, other than returning that state info)
	return start(hd, handler)

async def finished(hd):
	if hd.payload.get('finished'):
		await finish(hd)
		return True # yes, finished
	return False # no, not finished

async def finish(hd):
	try: await db.rollback(hd.dbc) # if a transaction was started, normal processing should have performed the COMMIT when all finished well; if we're here, and that's not done, we assume responsibility for rolling back unfinished DB business
	except: pass # move on, even if rollback failed (e.g., there might not even be an outstanding transaction)
	if len(hd.prior_tasks) > 0: # no-op if there ARE no prior tasks (just stick with current task)
		await ws.send(hd, 'hide_dialog') # always hide_dialog here; if we're reverting to another dialog-based task, it's going to need to re-paint the whole dialog-box again (as if re-starting) anyway, because this (finishing) task's dialog is surely not what the reverted-to-task needs/wants; alternately, if we're reverting to a full page, then the dialog needs to be hidden no matter what.  Alas, hid_dialog happens here.
		hd.task = hd.prior_tasks.pop() # actually ASSIGN hd.task to the prior task here; thus, when the prior task is actually invoked (one line below), it'll enter with its old state all in-tact... INCLUDING the 'started' state - that is, the (usually) top call to just_started() will return False, since, indeed, this prior-task started long ago, in fact.  A reversion is not equivalent to a new start, from scratch.  Tasks should, thus, check the 'reverting' flag (in addition to the return of just_started()) in order to decide how to proceed properly
		await hd.task.handler(hd, True)
	#else: no-op, really (other than the possible rollback()

def clear_all(hd):
	hd.task = None
	hd.prior_tasks = []
