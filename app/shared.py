
from functools import wraps

def doublewrap(f):
	'''
	a decorator decorator, allowing the decorator to be used as:
	@decorator(with, arguments, and=kwargs)
	or
	@decorator
	THANKS https://stackoverflow.com/users/618895/bj0
	'''
	@wraps(f)
	def new_dec(*args, **kwargs):
		if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
			# actual decorated function
			return f(args[0])
		else:
			# decorator arguments
			return lambda realf: f(realf, *args, **kwargs)

	return new_dec
