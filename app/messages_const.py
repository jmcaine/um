
from enum import StrEnum

NewMessageNotify = StrEnum('NewMessageNotify', [
	'reload',
	'inject',
	'tease',
])

Filter = StrEnum('Filter', [
	'new', # DEPRECATED: 'unarchived'
	'all',
	'pinned',
	'day',
	'this_week',
])
