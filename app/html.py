__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from dominate import document
from dominate import tags as t

from . import text


# Logging ---------------------------------------------------------------------

l = logging.getLogger(__name__)


# Handlers --------------------------------------------------------------------

def test(person = None):
	d = _doc(text.doc_prefix + 'Test')
	with d:
		if person:
			t.div(f'Hello {person["first_name"]}!')
		t.div('This is a test')
	return d.render()


# Utils -----------------------------------------------------------------------

k_cache_buster = '?v=1'
def _doc(title, css = None):
	d = document(title = title)
	with d.head:
		t.meta(name = 'viewport', content = 'width=device-width, initial-scale=1')
		t.link(href = '/static/css/common.css' + k_cache_buster, rel = 'stylesheet')
		if css:
			for c in css:
				t.link(href = f'/static/css/{c}' + k_cache_buster, rel = 'stylesheet')
	return d
