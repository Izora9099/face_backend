"""
Re-encrypt stored face encodings after SECRET_KEY changes.

django-cryptography derives the AES key from CRYPTOGRAPHY_KEY (defaults to
SECRET_KEY) and signs every value with SECRET_KEY, so changing SECRET_KEY makes
existing Student.face_encoding values unreadable. This command decrypts them
with the old key and saves them under the current settings.

    python manage.py rotate_encryption_key --old-secret-key '<previous SECRET_KEY>'
"""

import pickle

from cryptography.hazmat.primitives.kdf import pbkdf2
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils.encoding import force_bytes
from django_cryptography.core.signing import FernetSigner
from django_cryptography.utils.crypto import FernetBytes

from core.models import Student


def _derive(key):
    kdf = pbkdf2.PBKDF2HMAC(
        algorithm=settings.CRYPTOGRAPHY_DIGEST,
        length=settings.CRYPTOGRAPHY_DIGEST.digest_size,
        salt=settings.CRYPTOGRAPHY_SALT,
        iterations=30000,
        backend=settings.CRYPTOGRAPHY_BACKEND,
    )
    return kdf.derive(force_bytes(key))


class Command(BaseCommand):
    help = 'Re-encrypt Student.face_encoding from an old SECRET_KEY to the current one.'

    def add_arguments(self, parser):
        parser.add_argument('--old-secret-key', required=True,
                            help='SECRET_KEY the data was written with.')
        parser.add_argument('--old-field-key', default=None,
                            help='Old CRYPTOGRAPHY_KEY if it differed from the old SECRET_KEY.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, old_secret_key, old_field_key, dry_run, **options):
        old = FernetBytes(key=_derive(old_field_key or old_secret_key),
                          signer=FernetSigner(key=old_secret_key))
        table = Student._meta.db_table

        # Read ciphertext directly: loading through the ORM would try (and fail)
        # to decrypt with the current key.
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT id, face_encoding FROM {table}')
            rows = cursor.fetchall()

        converted, empty, failed = 0, 0, []
        plain = {}
        for pk, blob in rows:
            try:
                value = pickle.loads(old.decrypt(bytes(blob)))
            except Exception:
                failed.append(pk)
                continue
            plain[pk] = value
            if value:
                converted += 1
            else:
                empty += 1

        if failed and not plain:
            raise CommandError('No rows could be decrypted with the given old key; nothing changed.')

        if not dry_run:
            with transaction.atomic():
                for pk, value in plain.items():
                    # .update() runs the field's encryption with the current key.
                    Student.objects.filter(pk=pk).update(
                        face_encoding=value,
                        face_images_count=1 if value else 0,
                    )

        verb = 'Would re-encrypt' if dry_run else 'Re-encrypted'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {converted} encodings ({empty} empty rows).'))
        if failed:
            self.stdout.write(self.style.WARNING(
                f'{len(failed)} rows could not be decrypted with the old key (ids: {failed}); '
                'those students must re-enrol their face.'))
