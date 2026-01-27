from enum import StrEnum

NewMessageNotify = StrEnum('NewMessageNotify', [
	'reload',
	'inject',
	'tease',
])

Filter = StrEnum('Filter', [
	'new',
	'deferred',
	'all',
	'pinned',
	'pegged',
	#'day',
	#'this_week',
])
