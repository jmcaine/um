__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'


doc_prefix = 'um... '

# Page titles:
users = 'Users'
join = 'Join'
invite = 'Invite'

# Fieldset titles:
name = 'Name'
email = 'Email'
phone = 'Phone'
username = 'Username'
password = 'Password'
user = 'User'
person = 'Person'

# Button titles:
login = 'Log In'
create = 'Create'
next = 'Next ►'
save = 'Save'
cancel = 'Cancel'
edit = 'Edit...'
add = 'Add...'
delete = 'Delete'
submit = 'Submit'
send = 'Send!'
finish = 'Finish!'
more_detail = 'More detail...'
close = 'Close'
forgot_password = 'Forgot Password...'
tag = 'Tag'
done = 'Done'

# Label prefixes:
your = 'Your'
friends = "Friend's"

# Other labels/hints:
username_hint = '"{suggestion}" or similar'
new_username = 'Now create a NEW username'
new_password = 'Set your NEW password'
filtersearch = 'Filter / Search...'
show_inactives = 'Show inactives, too'
change_settings = 'Settings'
admin = 'Administrative tools'
messages = 'Messages'
logout = 'Log out of this session'
deep_search = 'Search "deep"'
tags = 'Tags'
invite_new_user = 'Invite new user...'
create_new_tag = 'Create new tag...'

# Fieldset legends:
emails = 'Emails'
phones = 'Phones'
password_reset = 'Reset Password'

# Messages:
welcome = 'Welcome!  "Log in" or "Join" to get started... '
change_detail_success = 'Successfully changed {change}'
detail_for = 'detail for'
invalid_login = 'Invalid username/login; please try again or click "forgot password" below.'
forgot_password_prelude = "What's your email address?  We'll send a password reset link!"
auth_required = "You aren't authorized to access this function.  If you have a different login with authorization for this function, log out from your current session and log back in as an authorized user to access this function."
deletion_succeeded = 'Deletion succeeded.'
invite_succeeded = 'Successfully invited {name}. (User will be "inactive" until invitation is accepted.)'
added_tag_success = 'Successfully added tag {name}.'
removed_user_from_tag = 'Successfully UNsubscribed {username} from tag "{tag_name}".'
added_user_to_tag = 'Successfully subscribed {username} to tag "{tag_name}".'
internal_error = 'Internal error; please refer to with this error ID: {reference}'


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
	tag_name = 'Tag name must be provided, and must be 2-32 characters in length'
