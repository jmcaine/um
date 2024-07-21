__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

import logging

from dataclasses import dataclass

from dominate import document
from dominate import tags as t

from . import text


# Logging ---------------------------------------------------------------------

l = logging.getLogger(__name__)


# Utils -----------------------------------------------------------------------

@dataclass(slots = True)
class Form:
	action: str
	field_values: dict
	validators: dict | None = None
	invalids: list | None = None
	error: str | None = None


# Handlers --------------------------------------------------------------------

def test(person = None):
	d = _doc(text.doc_prefix + 'Test')
	with d:
		if person:
			t.div(f'Hello {person["first_name"]}!')
		t.div('This is a test')
	return d.render()


def add_person(form):
	title = text.add_person
	d = _doc(text.doc_prefix + title)
	with d:
		with t.form(action = form.action, method = 'post'):
			_small_fieldset(title, form, [
					Text_Input('first_name', bool_attrs = ('required', 'autofocus')),
					Text_Input('last_name', bool_attrs = ('required',)),
				], text.create)
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

@dataclass(slots = True)
class Text_Input:
	name: str # expected to be a lowercase alphanumeric "variable name" without spaces - use underscores ('_') to separate words for a mult-word name.
	label: str | None = None # label, or None, to indicate that label should be auto-calculated as name.replace('_', ' ').title()
	placeholder: str | bool = False # placeholder string (for inside field box) OR `False` (for none) or `True` to use `label` as placeholder (instead of as a prompt, in front)
	type_: str | None = None # HTML `input` arg `type`, such as 'password' for a password input field, or None for plain 'text' type
	attrs: dict | None = None # other HTML field attrs like 'maxlength', 'autocomplete', etc.
	bool_attrs: list | None  = None # other HTML bool attrs like 'readonly'
	value: str | None = None # value, if entry has already happened or current value is provided (e.g., from database)
	invalid_div: t.div | None = None # div prepared with error message, to follow this text input in such a case

	def render(self):
		if not self.label:
			self.label = self.name.replace('_', ' ').title()
		attrs = _combine_attrs(self.attrs, self.bool_attrs)

		i = t.input_(name = self.name, id = self.name, type = self.type_ if self.type_ else 'text', **attrs)
		if self.value:
			i['value'] = self.value
		if self.placeholder:
			if type(self.placeholder) == str:
				i['placeholder'] = self.placeholder
			elif self.placeholder == True:
				i['placeholder'] = self.label
			result = t.label(i)
		else: # no placeholder provided; prompt with label:
			result = t.label(self.label + ':', i)
		if self.invalid_div:
			result += self.invalid_div
		return result

def _combine_attrs(attrs: dict | None, bool_attrs: list | None):
	if attrs == None:
		attrs = {}
	if bool_attrs:
		attrs.update(dict([(f, True) for f in bool_attrs]))
	return attrs

def _small_fieldset(title, form, fields, button_title = text.submit):
	result = t.fieldset(cls = 'small_fieldset')
	with result:
		t.legend(title + '...')
		#_error(form.error) # TODO!
		for field in fields:
			field.value = form.field_values.get(field.name)
			t.div(field.render())
		t.div(t.button(button_title, type = 'submit'))
	return result

