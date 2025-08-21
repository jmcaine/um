from datetime import datetime

import sqlite3

dbc = sqlite3.connect('um.db', isolation_level = None)
dbc.row_factory = sqlite3.Row


author_id = 2

k_now_ = '%Y-%m-%d %H:%M:%SZ'
k_now = f"strftime('{k_now_}')"

s_users = '''
	select user.id as uid, person.id as pid, person.first_name, person.last_name
	from user
	join person on user.person = person.id
	where user.active = 1
'''
#	and user.id = 2

s_phones = 'select phone from phone where phone.person = ?'
s_emails = 'select email from email where email.person = ?'
s_children = 'select person.first_name, person.last_name, person.birth_date from person join child_guardian on child_guardian.child = person.id where child_guardian.guardian = ?'

teaser = 'This "auto" message takes the place of filling in a registration form this year'
prelude = f'''<div>{teaser}.  Simply reply to confirm that everything below is correct, or with any corrections that need to be made, and I'll update the records accordingly and you'll be all registered!  Note that if I'm missing any children (most likely your oldest, who have graduated out, or your youngest, who may not be old enough for me to have on record), please provide name(s) and birthdate(s) for me in your reply.  I don't technically need your "graduates", but I would like to have babies up-to-date, to assess nursery needs and for future planning.  Thanks!</div>'''

bd = lambda date: datetime.fromisoformat(date).strftime('%m/%d/%Y')

def run():
	for u in dbc.execute(s_users, ()):
		print(f"{u['first_name']} {u['last_name']}")
		message = prelude + \
			"<div>Phone Numbers:<br>" + \
			'<br>'.join([f"* {p['phone']}" for p in dbc.execute(s_phones, (u['pid'],))]) + \
			"</div><div>Email Addresses:<br>" + \
			'<br>'.join([f"* {e['email']}" for e in dbc.execute(s_emails, (u['pid'],))]) + \
			"</div><div>Children:<br>" + \
			'<br>'.join([f"* {c['first_name']} {c['last_name']} ({bd(c['birth_date'])})" for c in dbc.execute(s_children, (u['pid'],))]) + \
			"</div>"

		m = dbc.execute(f'insert into message (message, author, created, sent, thread_updated, teaser) values (?, ?, {k_now}, {k_now}, {k_now}, ?)', (message, author_id, teaser))
		ut = dbc.execute('select user_tag.tag from user_tag where user_tag.user = ?', (u['uid'],))
		dbc.execute(f'insert into message_tag (message, tag) values (?, ?)', (m.lastrowid, ut.fetchone()['tag']))

if __name__ == '__main__':
	run()
