"""Real MIME parser preserves exact reply identity while tolerating folding."""
import email
import unittest
from unittest.mock import patch

from cs import gmail_drafts, review_draft
from cs.draft_identity import canonical_message_id


class ReplyHeaderFolding(unittest.TestCase):
    def test_seven_retained_incident_cases(self):
        root, target = '<root@example.invalid>', '<target@example.invalid>'
        draft = dict(id='draft-fixture', owner_id='owner@example.invalid',
                     body='Fixture body', to_addresses=['recipient@example.invalid'],
                     subject='Fixture', in_reply_to=target, references=[root])
        prefix = ('From: owner@example.invalid\r\nTo: recipient@example.invalid\r\n'
                  'Subject: Fixture\r\nReferences: ' + root + '\r\n'
                  'X-CS-Engine-Draft-ID: draft-fixture\r\n'
                  'X-CS-Engine-Owner-UID: owner-fixture\r\n')
        cases = (
            ('normal', 'In-Reply-To: ' + target, True),
            ('folded', 'In-Reply-To:\r\n ' + target, True),
            ('duplicate', 'In-Reply-To: ' + target + '\r\nIn-Reply-To: <other@example.invalid>', False),
            ('duplicate_same', 'In-Reply-To: ' + target + '\r\nIn-Reply-To: ' + target, False),
            ('malformed', 'In-Reply-To: <broken', False),
            ('multiple', 'In-Reply-To: ' + target + ' <other@example.invalid>', False),
            ('changed', 'In-Reply-To: <other@example.invalid>', False),
        )
        for name, header, expected in cases:
            with self.subTest(name=name):
                raw = (prefix + header + '\r\nContent-Type: text/plain; charset=utf-8'
                       '\r\n\r\nFixture body\r\n').encode()
                row = {**gmail_drafts._header_evidence(email.message_from_bytes(raw)),
                       **gmail_drafts._mime_evidence(raw), 'is_draft': True,
                       'body_complete': True, 'body_note': None, 'body': 'Fixture body'}
                self.assertEqual(review_draft._matches(row, draft, root, 'owner-fixture'), expected)

    def test_never_extracts_or_repairs_malformed_ids(self):
        for value in ('text <x@y>', '<x@y> text', '<x@y>\r\n', '<x\r\n @y>',
                      '<x@@y>', '<x@y>\x00', '<x@y> <z@y>', '<x(comment)@y>',
                      '<x:y@z>', '<x,y@z>', '<x..y@z>', '<x@y..z>'):
            with self.subTest(value=value):
                self.assertIsNone(canonical_message_id(value))

    def test_sent_verifier_uses_the_same_exact_comparison(self):
        from cs import send_completion
        from test_send_completion import SentIMAP, DRAFT, ROOT, TARGET, settings

        for header, succeeds in (
            ('In-Reply-To:\n ' + TARGET, True),
            ('In-Reply-To: ' + TARGET + '\nIn-Reply-To: ' + TARGET, False),
            ('In-Reply-To: <broken', False),
            ('In-Reply-To: <other@example.test>', False),
        ):
            with self.subTest(header=header):
                provider = SentIMAP(DRAFT)
                raw = provider.message.as_bytes().replace(
                    ('In-Reply-To: ' + TARGET).encode(), header.encode())
                def uid(command, *args):
                    if command == 'SEARCH':
                        return 'OK', [b'1']
                    return 'OK', [(b'1 (UID 1 RFC822.SIZE ' + str(len(raw)).encode() + b')', raw)]
                with patch.object(provider, 'uid', side_effect=uid), \
                     patch.object(gmail_drafts, '_imap', return_value=provider):
                    if succeeds:
                        self.assertEqual(send_completion._sent(settings(), DRAFT, '<sent@example.test>'), ROOT)
                    else:
                        with self.assertRaises(ValueError):
                            send_completion._sent(settings(), DRAFT, '<sent@example.test>')


if __name__ == '__main__':
    unittest.main()
