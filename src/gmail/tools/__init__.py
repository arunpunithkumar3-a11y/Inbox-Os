from src.gmail.tools.read_emails import read_emails
from src.gmail.tools.send_email import send_email
from src.gmail.tools.reply_to_email import reply_to_email
from src.gmail.tools.mark_as_read import mark_as_read
from src.gmail.tools.archive_email import archive_email
from src.gmail.tools.trash_email import trash_email

tools_list = [
    read_emails,
    send_email,
    reply_to_email,
    mark_as_read,
    archive_email,
    trash_email,
]
