import sqlite3
from collections import OrderedDict
import unicodedata


class PhotoDatabase(object):
    def __init__(self, database):
        self.conn = sqlite3.connect(database)
        cursor = self.conn.cursor()
        current_tables = [a for a in cursor.execute("SELECT * FROM sqlite_master WHERE type='table';")]
        table_ids = [a[1] for table in current_tables]
        self.tables = {}
        self.tables['photos'] = OrderedDict()
        self.tables['photos']['filename'] = 'text'
        self.tables['photos']['album_title'] = 'text'
        self.tables['photos']['processed'] = 'int'
        self.tables['photos']['uploaded'] = 'int'
        self.tables['photos']['date_uploaded'] = 'text'
        self.tables['photos']['flickr_photo_id'] = 'text'
        self.tables['photos']['flickr_photoset_id'] = 'text'

        if 'photos' not in table_ids:
            field_definition = ', '.join(['{} {}'.format(k, v) for k, v in self.tables['photos'].items()])
            sentence = "CREATE TABLE photos({})".format(field_definition)
            cursor.execute(sentence)

    def get_photos_by_filename(self, filename):
        fname = filename.encode('utf-8')
        cursor = self.conn.cursor()
        photos = [a for a in cursor.execute('SELECT * FROM photos WHERE filename="{}"'.format(fname))]
        return [dict(zip(self.tables['photos'].keys(), photo)) for photo in photos] if photos else []

    def get_photo_by_filename_and_album(self, filename, album):
        fname = filename.encode('utf-8')
        aname = album.encode('utf-8')
        cursor = self.conn.cursor()
        photos = [a for a in cursor.execute('SELECT * FROM photos WHERE filename="{}" AND album_title="{}"'.format(fname, aname))]
        if len(photos) > 1:
            print 'WARNING photo {} duplicated'. format(filename)
        return dict(zip(self.tables['photos'].keys(), photos[0])) if photos else None

    def photo_processed(self, filename_path):
        parts = filename_path.split('/')
        filename = parts[-1]
        album = parts[-2]
        photo = self.get_photo_by_filename_and_album(filename, album)
        if photo is None:
            return False
        else:
            return bool(photo['processed'])

    def normalize_album_titles(self):
        cursor = self.conn.cursor()
        photos = [a for a in cursor.execute('select * from photos') if a[1] != unicodedata.normalize('NFD', a[1])]
        for photo in photos:
            self.update_photo(photo[0], photo[1], 'album_title', unicodedata.normalize('NFD', a[1]).encode('utf-8'))
            print '.'
        self.conn.commit()

    def photo_uploaded(self, filename_path):
        parts = filename_path.split('/')
        filename = parts[-1]
        album = parts[-2]
        photo = self.get_photo_by_filename_and_album(filename, album)
        if photo is None:
            return False
        else:
            return bool(photo['uploaded'])

    def rename_photoset(self, old_title, new_title):
        cursor = self.conn.cursor()
        ot = old_title.encode('utf-8')
        nt = new_title.encode('utf-8')

        cursor.execute('UPDATE photos SET album_title="{}" WHERE album_title="{}"'.format(nt, ot))
        self.conn.commit()

    def create_photo(self, filename, album):
        cursor = self.conn.cursor()
        fname = filename.encode('utf-8')
        aname = album.encode('utf-8')
        data = dict(
            filename=fname,
            album_title=aname,
            processed=1,
            uploaded=0,
            date_uploaded='',
            flickr_photo_id='',
            flickr_photoset_id=''
        )
        cursor.execute('INSERT INTO photos VALUES ("{filename}","{album_title}",{processed},{uploaded},"{date_uploaded}","{flickr_photo_id}","{flickr_photoset_id}")'.format(**data))
        self.conn.commit()

    def update_photo(self, filename, album, field, value):
        fname = filename.encode('utf-8')
        aname = album.encode('utf-8')

        cursor = self.conn.cursor()
        cursor.execute('UPDATE photos SET {}="{}" WHERE filename="{}" AND album_title="{}"'.format(field, value, fname, aname))
        self.conn.commit()

    def save_processed(self, filename_path):
        parts = filename_path.split('/')
        filename = parts[-1]
        album = parts[-2]

        photo = self.get_photo_by_filename_and_album(filename, album)
        if photo is None:
            self.create_photo(filename, album)
        else:
            self.update_photo(filename, album, 'processed', 1)
