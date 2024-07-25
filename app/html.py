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
	action: str # form action, upon submit POST
	field_values: dict # name:value pairs (name:None if no value (yet) known)
	validators: dict | None = None # name:Validator pairs...
	invalids: list | None = None # list of names (field names) for which entered values were invalid (failed validation)
	error: str | None = None # an overall error message to be displayed at the top (and bottom, or whatever) generalizing the input error situation


# Handlers --------------------------------------------------------------------

def test(person = None):
	d = _doc('Test')
	with d:
		if person:
			t.div(f'Hello {person["first_name"]}!')
		t.div('This is a test')
	return d.render()


def person(form):
	title = text.person
	d = _doc(title)
	with d:
		with t.form(action = form.action, method = 'post'):
			#_error(form.error) # TODO!
			id = form.field_values.get('id')
			_small_fieldset(title, form, [
					Text_Input(form, 'first_name', bool_attrs = ('required', 'autofocus')).build(),
					Text_Input(form, 'last_name', bool_attrs = ('required',)).build(),
					t.input_(name = 'id', id = 'id', type = 'hidden', value = id),
				], text.create if not id else text.save)
	return d.render()


def list_people(persons):
	d = _doc(text.list_people)
	with d:
		with t.table():
			for person in persons:
				with t.tr(cls = 'selectable_row', onclick = f"location.assign('/person/{person['id']}');"):
					t.td(person['first_name'], align = 'right')
					t.td(person['last_name'], align = 'left')
	return d.render()



# Utils -----------------------------------------------------------------------

k_cache_buster = '?v=1'
def _doc(title, css = None):
	d = document(title = text.doc_prefix + title)
	with d.head:
		t.meta(name = 'viewport', content = 'width=device-width, initial-scale=1')
		t.link(href = '/static/css/common.css' + k_cache_buster, rel = 'stylesheet')
		if css:
			for c in css:
				t.link(href = f'/static/css/{c}' + k_cache_buster, rel = 'stylesheet')
	return d

@dataclass(slots = True)
class Text_Input:
	form: Form # contains field_values, if they exist (from earlier entry or DB, e.g.)
	name: str # expected to be a lowercase alphanumeric "variable name" without spaces - use underscores ('_') to separate words for a mult-word name.
	label: str | None = None # label, or None, to indicate that label should be auto-calculated as name.replace('_', ' ').title()
	placeholder: str | bool = False # placeholder string (for inside field box) OR `False` (for none) or `True` to use `label` as placeholder (instead of as a prompt, in front)
	type_: str | None = None # HTML `input` arg `type`, such as 'password' for a password input field, or None for plain 'text' type
	attrs: dict | None = None # other HTML field attrs like 'maxlength', 'autocomplete', etc.
	bool_attrs: list | None = None # other HTML bool attrs like 'readonly'

	def build(self):
		if not self.label:
			self.label = self.name.replace('_', ' ').title()
		attrs = _combine_attrs(self.attrs, self.bool_attrs)

		i = t.input_(name = self.name, id = self.name, type = self.type_ if self.type_ else 'text', **attrs)
		value = self.form.field_values.get(self.name)
		if value:
			i['value'] = value
		if self.placeholder:
			if type(self.placeholder) == str:
				i['placeholder'] = self.placeholder
			elif self.placeholder == True:
				i['placeholder'] = self.label
			result = t.label(i)
		else: # no placeholder provided; prompt with label:
			result = t.label(self.label + ':', t.br(), i)
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
		for field in fields:
			t.div(field)
		t.div(t.button(button_title, type = 'submit'))
	return result

