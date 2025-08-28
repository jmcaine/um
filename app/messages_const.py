
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
	'pegged',
	'day',
	'this_week',
])
