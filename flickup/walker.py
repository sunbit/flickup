from flickup.uploader import Uploader
from flickup.db import PhotoDatabase
from sh import convert

import os
import re
import sys

from flickup import DO_CONVERT


class Walker(object):
    valid_formats = ['jpg']

    def __init__(self, settings):
        self.settings = settings
        homedir = os.path.expanduser("~")
        self.config_dir = '{}/.flickup'.format(homedir)

        self.database = PhotoDatabase(
            self.settings['db']
        )
        self.uploader = Uploader(
            self.database,
            settings['root']
        )

        self.baked_convert = convert.bake('-interlace', 'Plane', '-quality', '85%')

    def convert(self, filename):
        if DO_CONVERT:
            newfilename = re.sub(r'(.*)(\.\w+)$', r'\1_\2', filename)
            self.baked_convert(filename, newfilename)
            os.remove(filename)
            os.rename(newfilename, filename)
            print 'Converted ', filename
        self.database.save_processed(filename)

    def run(self, path):
        self.recurse_dir(os.path.realpath(path))

    def is_temp_file(self, filename):
        valid_formats_regex = '|'.join(self.valid_formats)
        is_temp_file_format = re.match(r'.*_\.({})$'.format(valid_formats_regex), filename, re.IGNORECASE)
        return os.path.isfile(filename) and is_temp_file_format and filename

    def is_valid_dir(self, filename):
        return os.path.isdir(filename) and not filename.startswith('.')

    def is_valid_file(self, filename):
        valid_formats_regex = '|'.join(self.valid_formats)
        has_valid_format = re.match(r'.*\.({})$'.format(valid_formats_regex), filename, re.IGNORECASE)
        return os.path.isfile(filename) and has_valid_format and filename

    def is_folder_renamed(self, files, path):
        def find_unique(files):
            for filename in files:
                photos = self.database.get_photos_by_filename(filename)
                if len(photos) == 1:
                    yield photos[0]
        try:
            # Search for a photo in the folder that it's filename appears
            # only once in the database
            photo = find_unique(files).next()

            # construct the real_filename of the found photo, that is a candidate
            # photo of a hipotetically renamed folder
            real_filename = u'{}/{}'.format(unicode(path), unicode(photo['filename']))

            # If the folder really was renamed, then it's older name its the found photo album_title
            old_photoset_title = photo['album_title']

            # Extract parts of the file we're processing,and try to get the photoset
            # from flickr collection tree, but with the hipotetical photoset title
            collection_tree, new_photoset_title, image_title = self.uploader.extract_parts(real_filename)
            photoset = self.uploader.get_photoset(collection_tree, old_photoset_title, create=False)

            # If we get a photoset, it means that the folder of the file we're processing, was uploaded
            # and assigned to this photoset sometime, but the folder in disk was renamed, but not so was
            # the photo's entries data on the database.
            # If we don't get a photoset, it means that the hipotetical rename never took part, and it's a
            # legitimate new file and new photoset
            if photoset:
                collection = self.uploader.get_collection(collection_tree, create=False)
                return (old_photoset_title, new_photoset_title, photoset, collection)
            else:
                return None

        except StopIteration:
            print "WARNING: Folder is probably renamed, but couldn't determine it's old name ..."
            return None

    def recurse_dir(self, path):
        """
            Processes all files of a folder, and recurses on found folders.
            You can pass following command arguments:

            reset uploaded --> unsets the uploaded marker and related flickr data, to force reupload of the photos in this folder/s
            reset album --> unsets the link to a flickr photoset

            Both options delete the photoset on flickr

            Afther this tries to detect if a folder has been renamed on disk and updates database and flickr

        """
        files = [f.decode('utf-8') for f in os.listdir(path) if f not in ['.DS_Store']]
        print 'Entering ', path
        for files_pos, filename in enumerate(files):
            real_filename = u'{}/{}'.format(unicode(path), unicode(filename))

            if self.is_temp_file(real_filename):
                os.remove(real_filename)
                print u'Removing temp file {}'.format(real_filename.decode('utf-8'))
            elif self.is_valid_dir(real_filename):
                self.recurse_dir(real_filename)
            elif self.is_valid_file(real_filename):
                if len(sys.argv) > 2:
                    if sys.argv[1] == 'reset' and sys.argv[2] == 'uploaded':
                        collection_tree, photoset_title, image_title = self.uploader.extract_parts(real_filename)
                        self.database.update_photo(image_title, photoset_title, 'uploaded', 0)
                        self.database.update_photo(image_title, photoset_title, 'date_uploaded', '')
                        self.database.update_photo(image_title, photoset_title, 'flickr_photo_id', '')
                        self.database.update_photo(image_title, photoset_title, 'flickr_photoset_id', '')
                        if files_pos == 0:
                            self.uploader.delete_photoset(self.uploader.get_photoset(collection_tree, photoset_title))
                    if sys.argv[1] == 'reset' and sys.argv[2] == 'album':
                        collection_tree, photoset_title, image_title = self.uploader.extract_parts(real_filename)
                        self.database.update_photo(image_title, photoset_title, 'flickr_photoset_id', '')
                        if files_pos == 0:
                            self.uploader.delete_photoset(self.uploader.get_photoset(collection_tree, photoset_title))

                # self.database.save_processed(real_filename)
                # a, photoset_title, image_title = self.uploader.extract_parts(real_filename)
                # self.database.update_photo(image_title, photoset_title, 'uploaded', 1)
                if not self.database.photo_processed(real_filename):
                    # If we can't find the photo processed in the database, try to guess if
                    # the folder has been renamed, (check only in the first folder pass)
                    renamed = False
                    if files_pos == 0:
                        folder_photo_renamed = self.is_folder_renamed(files, path)
                        if folder_photo_renamed:
                            old_folder_name, new_folder_name, photoset, collection = folder_photo_renamed
                            print u'>  Detected rename of former disk folder "{}" to "{}", updating DB and flickr photoset'.format(old_folder_name, new_folder_name)
                            self.database.rename_photoset(old_folder_name, new_folder_name)
                            self.uploader.rename_photoset(photoset, new_folder_name)

                            photoset['title'] = new_folder_name
                            collection[new_folder_name] = photoset
                            del collection[old_folder_name]

                            renamed = True
                    if not renamed:
                        print 'Optimitzant imatge...'
                        self.convert(real_filename)
                if self.database.photo_processed(real_filename):
                    self.uploader.upload(real_filename)
