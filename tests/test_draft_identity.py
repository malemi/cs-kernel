from email.message import EmailMessage
from cs.authored_mail import authored_message, authored_plain, BODY_BYTES


def test_authored():
    old = 'Old message with a long quoted history. ' * 50
    msg = EmailMessage(); msg.set_content('New short follow-up\n\nOn Monday someone wrote:\n> ' + old)
    body, note = authored_message(msg.as_bytes())
    assert body == 'New short follow-up' and note is None
    assert body != authored_plain(old)[0]
    msg = EmailMessage(); msg.set_content('<div>New follow-up</div><blockquote>' + old + '</blockquote>', subtype='html')
    assert authored_message(msg.as_bytes()) == ('New follow-up', None)
    assert authored_message(b'x' * BODY_BYTES)[1]
    original = 'The previous authored message is long enough for duplicate comparisons.'
    for suffix in (
        '\n\nOn Monday someone wrote:\n> Older quoted history\n\nA new material term applies now.',
        '\n\nOn Monday someone wrote:\n> Earlier quote\nInline answer\n> Later quote',
        '\n\nOn Monday someone wrote:\nUnprefixed old history is ambiguous.',
    ):
        authored, note = authored_plain(original + suffix)
        assert authored == '' and note and 'ambiguous' in note
        msg = EmailMessage(); msg.set_content(original + suffix)
        assert authored_message(msg.as_bytes())[1]
    assert authored_plain(original + '\nOn Monday someone wrote:\n> Pure old quote') == (original, None)
    continuation = original + '\n-----\nA new material term applies now.'
    assert authored_plain(continuation)[0] != authored_plain(original)[0]
    msg = EmailMessage(); msg.set_content(continuation)
    assert authored_message(msg.as_bytes())[0] != authored_plain(original)[0]
    msg = EmailMessage(); msg.set_content(original)
    msg.add_alternative('<div>A new material term applies now.</div>', subtype='html')
    body, note = authored_message(msg.as_bytes())
    assert body == '' and note and 'divergent' in note
    msg = EmailMessage(); msg.set_content('Same authored text')
    msg.add_alternative('<div>Same authored text</div>', subtype='html')
    assert authored_message(msg.as_bytes()) == ('Same authored text', None)
    msg = EmailMessage(); msg.set_content('Clean text'); msg.add_attachment(old.encode(), maintype='text', subtype='plain', filename='history.txt')
    assert authored_message(msg.as_bytes()) == ('Clean text', None)


if __name__ == "__main__":
    test_authored()
