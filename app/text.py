__author__ = 'J. Michael Caine'
__copyright__ = '2024'
__version__ = '0.1'
__license__ = 'MIT'


doc_title = 'um... '

# Page titles:
users = 'Users'
join = 'Join'
invite = 'Invite'

# Fieldset titles:
name = 'Name'
email = 'Email'
phone = 'Phone'
child = 'Child'
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
cancel_return = 'Cancel (Return)'
clear = 'Clear (blank out)'
edit = 'Edit...'
add = 'Add...'
delete = 'Delete'
submit = 'Submit'
send = 'Send!'
send_message = 'Send message...'
save_draft = 'Save draft'
finish = 'Finish!'
more_detail = 'More detail...'
close = 'Close'
download = 'Download'
forgot_password = 'Reset Password...'
tag = 'Tag'
done = 'Done'
brand_new_message = 'Brand New Message...'
dos = 'Do'
news = 'New'
days = '2Day'
this_weeks = 'Week'
week = 'Week'
pins = 'Pins'
pegs = 'Pegs'
alls = 'All'
thread = 'Show whole thread'
currents = 'Current'
previouses = 'Previous'
nexts = 'Next'
today = 'Today'


# Label prefixes:
your = 'Your'
friends = "Friend's"

# Other labels/hints:
username_hint = '"{suggestion}" or similar'
new_username = 'Now create a NEW username'
new_password = 'Set your NEW password'
filtersearch = 'Search / Filter...'
show_inactives = 'Incl. inactives'
dont_limit = 'Show all'
change_settings = 'Settings'
admin = 'Administrative tools'
messages = 'Messages'
trash_draft = 'Trash this draft message'
draft_trashed = 'Draft successfully trashed'
draft_saved = 'Draft successfully saved (to send later)'
show_trashed = 'Show only my "trashed" messages' # TODO: UNUSED, at present; but should be a checkbox in a retrieval interface (for accidentally-deleted messages... note, change "trashed" to "deleted")
delete_confirmation = 'Are you sure you want to delete that draft?'
attach = 'Attach/upload picture, etc.'
session_account_details = 'Session / Account Details'
account_details = 'Edit Account Details'
logout = 'Log Out'
switch_to = 'Switch to...'
deep_search = 'Search "deep"'
tags = 'Tags'
invite_new_user = 'Invite new user...'
create_new_tag = 'Create new tag...'
recipients = 'Recipients'
not_recipients = 'Click "+" to add...'
loading_messages = 'Loading messages...'
loading_assignments = 'Loading assignments...'
assignments = 'Assignments'
stash = 'Stash message'
delete_message = 'Delete (UN-send) message'
message_deleted = 'Message deleted'
show_news = 'Show ONLY "new" messages'
show_alls = 'Show ALL messages'
show_all_assignments = 'Show ALL assignments (entire year)'
show_days = "Show ONLY messages from the last 24 hours"
show_this_weeks = "Show ONLY this week's messages"
show_pins = 'Show ONLY my pinned messages'
show_pegs = 'Show ONLY the permanently pegged messages'
reply = 'Reply to this message'
pin = 'Pin this message'
unpin = 'UNpin this message'
edit_message = 'Edit this message'
edited = 'Edited'
view_older = 'View older messages'
view_newer = 'View newer messages'
reply_one = 'Reply to sender only'
reply_all = 'Reply to entire group'
just_now = 'just now'
child_password = 'Provide a "password" to enable sub-account for child; blank out to disable'
pretend_password = '********'
show_currents = "Show THIS WEEK's assignments"
show_previouses = "Show LAST WEEK's assignments"
show_nexts = "Show NEXT WEEK's assignments"

# Fieldset legends:
emails = 'Emails'
phones = 'Phones'
spouse = 'Spouse'
children = 'Children'
password_reset = 'Reset Password'
reset_code = 'Reset Code'

# Banners:
welcome = 'Welcome!  "Log in" or "Join" to get started... '
change_detail_success = 'Successfully changed {change}'
detail_for = 'detail for'
invalid_login = 'Invalid username/login; please try again or click "reset password" below.'
forgot_password_prelude = "What's your email address?  We'll send a password reset link!"
unknown_email = "That email address is not on record; please try another, or contact an administrator."
enter_reset_code = "Paste or type the code you received over email..."
enter_reset_code_retry = "That didn't work; retry entering your reset code carefully..."
auth_required = "You aren't authorized to access this function.  If you have a different login with authorization for this function, log out from your current session and log back in as an authorized user to access this function."
deletion_succeeded = 'Deletion succeeded.'
invite_succeeded = 'Successfully invited {name}. (User will be "inactive" until invitation is accepted.)'
added_tag_success = 'Successfully added tag {name}.'
removed_user_from_tag = 'Successfully UNsubscribed {username} from tag "{tag_name}".'
added_user_to_tag = 'Successfully subscribed {username} to tag "{tag_name}".'
internal_error = 'Internal error; please refer to with this error ID: {reference}'
removed_tag_from_user = 'Successfully UNsubscribed from tag "{name}".'
added_tag_to_user = 'Successfully subscribed to tag "{name}".'
removed_tag_from_message = 'Successfully removed tag "{name}" from message.'
added_tag_to_message = 'Successfully added tag "{name}" to message.'
choose_message_draft = f'Choose a draft message, below, to finish, or click "{brand_new_message}" to start a brand new message.  You may also delete any drafts you no longer care about.'
no_more_drafts = f'No more draft messages! Click "{brand_new_message}", below, to start a brand new message.'
cant_send_empty_message = 'Cannot send an empty message - type some text first!'
cant_send_message_without_recipients = 'Cannot send a message with no recipients - add some tags to designate some recipients first!'
message_sent = 'Message sent!'
filter_for_more = '... (filter to see more...)'
no_such_invitation_code = 'Uh oh!  No such invitation code can be found on record!  Please contact an admin.'
not_found = 'No messages found that match the search "{searchtext}"'
no_messages = 'No messages here!'

reset_email_subject = 'Reset...'
password_reset_code_email_body = "You requested a password reset code for um.openhome.school. Here it is: {code} <-- type or paste that code into your browser, where it's requested."
email_invite_subject = 'Invitation link - openhome.school messenger'
email_invite_body = "This is your invite email to um.openhome.school - go to https://um.openhome.school/invite/{code} to accept...."
email_invite_body_html = """<html><body>This is your invite email to um.openhome.school - click on <a href="https://um.openhome.school/invite/{code}">this link to accept....</a></body></html>"""

# Hover / validation "title" hints:
class Title:
	name = 'Enter a name' # "(use 32 or fewer characters)" - but technically, the maxlength setting limits user; only a bot or non-normal entry could push more (and fail validation after submission)
	email = 'Enter an email address, such as name@site.com'
	phone = 'Enter a phone number, such as 555-123-4567 or +1-555-123-4567'
	username = 'Enter a username'
	password = 'Enter a password, six characters or longer'
	password_confirmation = 'Enter the password again, to confirm'
	code = 'Code'

# Validation:
class Valid:
	name = 'Name must be provided, and must be 32 or fewer characters.'
	email = 'Email must be provided, and must follow the format: name@site.com'
	phone = 'Phone must be provided, and must be a valid phone number (with or without country-code prefix)'
	username = 'Username must be provided, and must be 3-20 characters in length'
	username_or_email = 'A username or email address must be provided'
	username_exists = 'Sorry, that username is already in use.  Please try another.'
	password = 'Password must be six characters or longer'
	password_match = 'Password and confirmation must match'
	tag_name = 'Tag name must be provided, and must be 2-32 characters in length'
	code = 'Code must be copied or reproduced exactly as shown in the email.'
