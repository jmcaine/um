
doc_prefix = 'um... '

# Page titles:
person = 'Person'
list_people = 'List People'
join = 'Join'
invite = 'Invite'

# Fieldset titles:
name = 'Name'
email = 'Email'
phone = 'Phone'
username = 'Username'
password = 'Password'

# Button titles:
create = 'Create'
next = 'Next ►'
save = 'Save'
submit = 'Submit'
send = 'Send!'
finish = 'Finish!'

# Label prefixes:
your = 'Your'
friends = "Friend's"

# Other labels/hints:
username_hint = '"{suggestion}" or similar'
new_username = 'Now create a NEW username'
new_password = 'Set your NEW password'

# Hover / validation "title" hints:
class Title:
	name = 'Enter a name' # "(use 32 or fewer characters)" - but technically, the maxlength setting limits user; only a bot or non-normal entry could push more (and fail validation after submission)
	email = 'Enter an email address, such as name@site.com'
	phone = 'Enter a phone number, such as 555-123-4567 or +1-555-123-4567'
	username = 'Enter a username'
	password = 'Enter a password, six characters or longer'
	password_confirmation = 'Enter the password again, to confirm'

# Validation:
class Valid:
	name = 'Name must be provided, and must be 32 or fewer characters.'
	email = 'Email must be provided, and must follow the format: name@site.com'
	phone = 'Phone must be provided, and must be a valid phone number (with or without country-code prefix)'
	username = 'Username must be provided, and must be 3-20 characters in length'
	username_exists = 'Sorry, that username is already in use.  Please try another.'
	password = 'Password must be six characters or longer'
	password_match = 'Password and confirmation must match'
