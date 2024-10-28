__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from dataclasses import dataclass, field

import re

l = logging.getLogger(__name__)

@dataclass(slots = True, frozen = True)
class Rex:
	rstring: str
	compiled: re.Pattern = field(init = False)
	def __post_init__(self):
		object.__setattr__(self, 'compiled', re.compile(self.rstring)) # can't use simple 'self.compiled = ' because this is frozen

STRING32 = Rex(r'^.{1,32}$')
ALPHANUM = Rex(r'^[\w ]+$')
USERNAME = Rex(r'^[\w\-._]{1,20}$')
PASSWORD = Rex(r'^.{4,32}$')
EMAIL = Rex(r'(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)')
PHONE = Rex(r'^(\(?\+?\d{1,3}\)?)?[-.\s]?(\d{3}[-.\s]?){2}\d{4}$') # matches all forms of "+18 123 456 7890" with or without "+", using dashes, spaces, or dots between groups of numbers, with or without country code at all
SLUG = Rex(r'^[\w\-_]{2,32}$')
INVITATION = Rex(r'^.{24,24}$')

@dataclass(slots = True)
class Validator:
	required: bool
	regex: Rex | None = None
	min_length: int | None = None
	max_length: int | None = None
	message: str | None = None


async def invalids(hd, data, fields, invalid_handler, banner, break_on_one = True):
	result = {}
	checks = lambda field: \
		((not field.validator.regex) or field.validator.regex.compiled.match(value) != None) \
		and (not field.validator.min_length or field.validator.min_length <= len(value) <= field.validator.max_length)

	for field_name, field in fields.items():
		value = str(data[field_name])
		if field.validator:
			if (field.validator.required and not value) or (value and not checks(field)):
				result[field_name] = field.validator.message
				if break_on_one:
					await invalid_handler(hd, field.validator.message, banner)
					break
	if not break_on_one:
		await invalid_handler(hd, result, banner)
	return result
