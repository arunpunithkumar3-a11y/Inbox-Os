from gmail.tools.read_emails import read_emails
from gmail.tools.send_email import send_email
from gmail.tools.reply_to_email import reply_to_email
from gmail.tools.mark_as_read import mark_as_read
from gmail.tools.archive_email import archive_email
from gmail.tools.trash_email import trash_email
from gmail.tools.add_label import add_label
from gmail.tools.remove_label import remove_label
from gmail.tools.list_labels import list_labels
from gmail.tools.create_draft import create_draft
from gmail.tools.get_email_stats import get_email_stats

tools_list = [
    read_emails,
    send_email,
    reply_to_email,
    mark_as_read,
    archive_email,
    trash_email,
    add_label,
    remove_label,
    list_labels,
    create_draft,
    get_email_stats,
]
