
import sqlite3

from . import emailer


dbc = sqlite3.connect('um.db', isolation_level = None)
dbc.row_factory = sqlite3.Row

#f'select tag.name, count(*) from message join message_tag on message_tag.message = message.id join tag on message_tag.tag = tag.id join user_tag on user_tag.tag = tag.id join user_tag.user = ? and user_tag.tag = tag.id where not exists (select 1 from message_stashed where message.id = message_stashed.message and user.id = message_stashed.stashed_by)'

unstashed_count_sql = '''
select tag.name, count(message.id) as count
    from message
    join message_tag on message_tag.message = message.id
    join tag on message_tag.tag = tag.id
    join user_tag on tag.id = user_tag.tag
    join user on user_tag.user = user.id
    where not exists (select 1 from message_stashed where message.id = message_stashed.message and user.id = message_stashed.stashed_by)
    and user.id = ? and message.deleted is null and message.sent is not null
''' # group by tag.name (unnecessary, implied)

unsent_count_sql = 'select count(message.id) as count from message where sent is null and message.author = ? and message.deleted is null'

unstashed_by_others_sql = '''
	select message.teaser, group_concat(user.username, ', ') as users
	from message
	join message_tag on message_tag.message = message.id
	join tag on message_tag.tag = tag.id
	join user_tag on tag.id = user_tag.tag
	join user on user_tag.user = user.id
	where not exists (select 1 from message_stashed where message.id = message_stashed.message and user.id = message_stashed.stashed_by)
	and message.author = ? and message.deleted is null
	group by message.id order by message.id desc
'''

users = '''
	select user.id, person.first_name, person.last_name, email.email
	from user
	join person on user.person = person.id
	join email on email.person = person.id
	where user.active = 1
'''

def run():
	for u in dbc.execute(users, ()):
		print(f"{u['first_name']} {u['last_name']} -- {u['id']}")
		unstashed_counts = dbc.execute(unstashed_count_sql, (u['id'],))
		unstashed_counts = [{'name': item['name'], 'count': item['count']} for item in unstashed_counts] if unstashed_counts else []
		unstashed_count_lines = [f"{count['name']} - {count['count']} unstashed messages" for count in unstashed_counts] if unstashed_counts else []
		unstashed_total_count = sum([count['count'] for count in unstashed_counts]) if unstashed_counts else 0
		unstashed_by_others = dbc.execute(unstashed_by_others_sql, (u['id'],)).fetchall()
		unstashed_by_others_lines = [f"""Your message: "{unstashed['teaser']}" - the following have not yet read: {unstashed['users']}""" for unstashed in unstashed_by_others] if unstashed_by_others else []
		unsent_count = dbc.execute(unsent_count_sql, (u['id'],)).fetchone()
		unsents = f" and {unsent_count['count']} message drafts that you haven't pushed 'SEND' on" if (unsent_count and unsent_count['count'] > 0) else ''
		paragraphs = [
			f"{u['first_name']} {u['last_name']},",
			f"You currently have {unstashed_total_count} unstashed messages{unsents}." + ('  Go to <a href="https://um.openhome.school/">https://um.openhome.school/</a> to stash some messages!' if unstashed_total_count else ""),
		] + unstashed_count_lines + unstashed_by_others_lines
		text = '\n\n'.join(paragraphs)
		html = '<html><body>' + ''.join(['<p>' + paragraph + '</p>' for paragraph in paragraphs]) + '</body></html>'

		emailer.send_email(u['email'], '"Um..." digest', text, html)
		#print(text + '\n\n\n')

if __name__ == '__main__':
	run()
