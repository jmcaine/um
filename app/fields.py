__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'

from dataclasses import dataclass

from . import text
from . import html
from . import valid
from .valid import Validator

@dataclass(slots = True, frozen = True)
class Field:
	validator: Validator | None
	html_field: html.Input # | html.Other... in future, possibly; input field seems to cover the bases, though
	
	def __post_init__(self):
		# Apply some validator specs, like 'required' and 'regex' TO the html field attributes to get client-side pre-validation:
		if self.validator:
			if self.validator.required:
				self.html_field.bool_attrs.append('required')
			if rex := self.validator.regex:
				self.html_field.attrs['pattern'] = rex.rstring
			if ml := self.validator.max_length:
				self.html_field.attrs['maxlength'] = ml

PERSON = {
	'first_name': Field(
		Validator(True, valid.STRING32, 1, 32, text.Valid.name),
		html.Input(autofocus = True, attrs = {'title': text.Title.name, 'autocomplete': 'off'})),
	'last_name': Field(
		Validator(True, valid.STRING32, 1, 32, text.Valid.name),
		html.Input(attrs = {'title': text.Title.name, 'autocomplete': 'off'})),
}
	
EMAIL = {
	'email': Field(
		Validator(True, valid.EMAIL, 5, 128, text.Valid.email),
		html.Input(type_ = 'email', attrs = {'title': text.Title.email})),
}
	
PHONE = {
	'phone': Field(
		Validator(True, valid.PHONE, 10, 20, text.Valid.phone), # 20 is oversize, but if symbols are used, char count can go up
		html.Input(type_ = 'tel', attrs = {'title': text.Title.phone})),
}

CHILD = PERSON | {
	'birth_date': Field(Validator(True), html.Input(type_ = 'date')),
}

USERNAME_VALIDATOR = Validator(True, valid.USERNAME, 3, 20, text.Valid.username)
NEW_USERNAME = {
	'username': Field(
		USERNAME_VALIDATOR,
		html.Input(
			label = text.new_username,
			placeholder = False, # depart from the 'label-as-placeholder' motif for this one, to make the label stand out on top of the input-box, and perhaps auto-populate the box with a real suggestion like firstname.lastname....
			attrs = {'title': text.Title.username},
		)),
}
		
PASSWORD_VALIDATOR = Validator(True, valid.STRING32, 6, 32, text.Valid.password)

LOOSE_USERNAME_OR_EMAIL_VALIDATOR = Validator(True, valid.LOOSE_USERNAME_OR_EMAIL, 3, 128, text.Valid.username_or_email)
LOGIN = {
	'username': Field(LOOSE_USERNAME_OR_EMAIL_VALIDATOR, html.Input(text.username)),
	'password': Field(PASSWORD_VALIDATOR, html.Input(type_ = 'password')),
}

USER = {
	'username': Field(USERNAME_VALIDATOR, html.Input(text.username, placeholder = False)),
	'verified': Field(Validator(False), html.Input(type_ = 'date')),
	'active': Field(None, html.Input(type_ = 'checkbox')),
}

RESET_CODE = {
	'code': Field(
		Validator(True, valid.CODE, 3, 20, text.Valid.code),
		html.Input(	autofocus = True, attrs = {'title': text.Title.code, 'autocomplete': 'off'}),
	),
}

NEW_PASSWORD = {
	'password': Field(
		PASSWORD_VALIDATOR,
		html.Input(
			label = text.new_password,
			placeholder = False, # depart from the 'label-as-placeholder' motif for this one, to make the label stand out on top of the input-box
			type_ = 'password', 
			attrs = {'title': text.Title.password}
		)),
	'password_confirmation': Field(
		Validator(True, valid.STRING32, 5, 32, text.Valid.password_match),
		html.Input(type_ = 'password', attrs = {'title': text.Title.password_confirmation})),
}

TAG = {
	'name': Field(Validator(True, valid.STRING32, 1, 32, text.Valid.tag_name), html.Input()),
	'active': Field(None, html.Input(type_ = 'checkbox', bool_attrs = ['checked',])),
}
