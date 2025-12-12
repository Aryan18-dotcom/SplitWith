
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config
import traceback

def send_email(to_email: str, subject: str, html_body: str = None, plain_body: str = None):
    """
    Simple SMTP sender using Config.SMTP_EMAIL, Config.SMTP_PASS, Config.SMTP_HOST, Config.SMTP_PORT
    html_body preferred, fallback to plain_body.
    Returns (True, None) on success or (False, error_message) on failure.
    """
    sender_email = Config.SMTP_EMAIL
    sender_password = Config.SMTP_PASS
    host = Config.SMTP_HOST
    port = Config.SMTP_PORT

    if not sender_email or not sender_password:
        return False, "SMTP credentials not configured."

    # Prepare message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = to_email

    if plain_body is None and html_body:
        # strip tags naive fallback
        plain_body = html_body

    if plain_body:
        part1 = MIMEText(plain_body, "plain")
        msg.attach(part1)
    if html_body:
        part2 = MIMEText(html_body, "html")
        msg.attach(part2)

    try:
        server = smtplib.SMTP(host, port, timeout=20)
        server.ehlo()
        if port == 587:
            server.starttls()
            server.ehlo()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        return True, None
    except Exception as e:
        tb = traceback.format_exc()
        return False, f"{e}\n{tb}"
