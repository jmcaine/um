


def started(hd, task_func):
	if hd.task != task_func:
		hd.task = task_func
		hd.state[task_func.__name__] = {}
		return False # wasn't already started (though it is now, so next call will return True
	#else:
	return True # task already started

def clear_state(hd, task_func):
	if task_func.__name__ in hd.state:
		del hd.state[task_func.__name__]
