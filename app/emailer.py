import smtplib
from email.message import EmailMessage

def send_email(to, subject, body):
	server = smtplib.SMTP('localhost',25)
	msg = EmailMessage()
	msg['Subject'] = subject
	msg['To'] = to
	msg['From'] = 'noreply@openhome.school'
	msg.set_content(body)
	server.send_message(msg)
