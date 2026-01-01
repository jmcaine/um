
import sqlite3

dbc = sqlite3.connect('um.db', isolation_level = None)

def run():
	dbc.execute('delete from message where message = "<br>"', ())
	dbc.execute('delete from message where message is null', ())

if __name__ == '__main__':
	run()
