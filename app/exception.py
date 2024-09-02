__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'


class UmException(Exception):
	pass

class InvalidInput(UmException):
	pass

class AlreadyExists(UmException):
	pass
