import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(to, subject, body, body_html = None):
	server = smtplib.SMTP('localhost', 25)
	msg = EmailMessage() if not body_html else MIMEMultipart('alternative')
	msg['Subject'] = subject
	msg['To'] = to
	msg['From'] = 'noreply@openhome.school'
	if not body_html:
		msg.set_content(body)
	else:
		msg.attach(MIMEText(body_html, 'html'))
		msg.attach(MIMEText(body, 'text'))

	server.send_message(msg)
