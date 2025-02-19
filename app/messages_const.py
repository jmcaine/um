
from enum import StrEnum

NewMessageNotify = StrEnum('NewMessageNotify', [
	'reload',
	'inject',
	'inject_replies',
	'tease',
])

Filter = StrEnum('Filter', [
	'unarchived',
	'all',
	'pinned',
	'day',
	'this_week',
	'archived', # not currently used
])
