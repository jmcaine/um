
from enum import StrEnum

NewMessageNotify = StrEnum('NewMessageNotify', [
	'reload',
	'inject_replies',
	'tease'
])

Filter = StrEnum('Filter', [
	'unarchived',
	'archived',
		'pinned',
		'day',
		'this_week'
])
