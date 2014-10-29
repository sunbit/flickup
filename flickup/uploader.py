import json
import os
import re
import sys
import time
import unicodedata
import exifread
import datetime
import urllib

from flickr import FlickrAPI
from rauth import OAuth1Session


def dict_to_qs(d):
    joiner = u'&'.encode('utf-8')
    qs = joiner.join(['{}={}'.format(k.encode('utf8'), urllib.quote_plus(v.encode('utf-8'))) for k, v in d.items()])
    return qs


class Uploader(object):
    """
    """
    consumer_key = "9d0b69163c0ae8ddfe7a3d0582874b57"
    consumer_secret = "899b3a6340d8cb56"
    request_token_url = 'https://www.flickr.com/services/oauth/request_token'
    access_token_url = 'https://www.flickr.com/services/oauth/access_token'
    authorize_url = 'https://www.flickr.com/services/oauth/authorize'
    callback = 'http://test.beta.upcnet.es/callback'
    base_url = 'https://api.flickr.com/services/rest'
    upload_url = 'https://up.flickr.com/services/upload'
    session_access_token = '72157637665662093-bebe07e6387e9e87'
    session_access_token_secret = '6aff330f2cb038fc'

    def __init__(self, database):
        self.session = OAuth1Session(
            self.consumer_key,
            self.consumer_secret,
            self.session_access_token,
            self.session_access_token_secret
        )

        self.flickr = FlickrAPI(
            api_key=self.consumer_key,
            api_secret=self.consumer_secret,
            oauth_token=self.session_access_token,
            oauth_token_secret=self.session_access_token_secret
        )
        self.database = database
        self.collections = {}
        self.get_collections_tree()

    def extract_parts(self, filename):
        parts = filename.split('Pictures/')[1].split('/')
        image_title = parts[-1]
        photoset_title = parts[-2]
        collection_tree = parts[:-2]

        return (collection_tree, photoset_title, image_title)

    def session_post(self, method, params={}):
        params.update({'method': method, 'format': 'json'})
        resp = self.session.post(self.base_url, data={}, params=dict_to_qs(params), verify=False)
        if resp.status_code != 200:
            print resp.status_code, resp.content
        return json.loads(re.sub(r'jsonFlickrApi\((.*)\)', r'\1', resp.content))

    def session_get(self, method, params={}):
        params.update({'method': method, 'format': 'json'})
        resp = self.session.get(self.base_url, params=dict_to_qs(params), verify=False)
        if resp.status_code != 200:
            print resp.status_code, resp.content
        return json.loads(re.sub(r'jsonFlickrApi\((.*)\)', r'\1', resp.content))

    def get_collections_tree(self):
        resp = self.session_get("flickr.collections.getTree")
        root = resp['collections']
        self.recurse_collections(root, self.collections)

    def recurse_collections(self, node, base_col):
        for collection in node.get('collection', []):
            collection_title = unicodedata.normalize('NFD', collection['title'])
            base_col[collection_title] = dict(collection)
            base_col[collection_title]['type'] = 'collection'
            self.recurse_collections(collection, base_col[collection_title])

        for album in node.get('set', []):
            album_title = unicodedata.normalize('NFD', album['title'])
            base_col[album_title] = dict(album)
            base_col[album_title]['type'] = 'set'

    def create_collection(self, name, node, description=''):
        print 'Creating collection {} in {}'.format(name, node['title'])
        options = {'title': name}
        if node is not None:
            options['parent_id'] = node['id']

        resp = self.session_post('flickr.collections.create', params=options)
        new_collection_id = resp['collection']['id']
        node[name] = {
            'title': name,
            'description': description,
            'type': 'collection',
            'id': new_collection_id
        }

    def rename_photoset(self, photoset, new_title):
        options = dict(
            photoset_id=photoset['id'],
            title=new_title
        )

        resp = self.session_post('flickr.photosets.editMeta', params=options)
        return resp

    def delete_photoset(self, photoset):
        if photoset:
            options = dict(
                photoset_id=photoset['id'],
            )

            resp = self.session_post('flickr.photosets.delete', params=options)
            return resp

    def put_set_in_collection(self, collection, photoset=None):
        collection_dicts = [ps for ps_title, ps in collection.items() if isinstance(ps, dict)]
        current_photosets = [ps for ps in collection_dicts if ps.get('type') == 'set']
        if photoset:
            current_photosets.append(photoset)
        sorted_photosets = sorted(current_photosets, key=lambda x: x['title'])
        sorted_photoset_ids = [a['id'] for a in sorted_photosets]

        options = dict(
            collection_id=collection['id'],
            photoset_ids=','.join(sorted_photoset_ids),
            do_remove='0'
        )
        resp = self.session_get('flickr.collections.editSets', params=options)
        if photoset:
            collection[photoset['title']] = photoset
        return resp

    def put_photo_in_photoset(self, photoset, photo_id, photo_title):
        try:
            options = dict(
                photoset_id=photoset['id'],
                photo_id=photo_id,
            )
            resp = self.session_post('flickr.photosets.addPhoto', params=options)
            photoset['photos'][photo_title] = photo_id
            if resp['stat'] == 'ok':
                return True
            else:
                if 'not found' in resp['message']:
                    return 'deleted'
                return False
        except:
            return False

    def set_uploaded_date(self, photo_id, filename):
        """
            Set posted date to uploaded date ** except ** for photos taken before
            user flickr sign up date. This is a flickr restriction. Membership date
            will be used as posted date with this photos, to avoid appearing on top
            of photostream.
        """
        try:
            membership_date = datetime.datetime(2007, 10, 23, 0, 0, 0).strftime('%s')
            tags = exifread.process_file(open(filename))
            tag = tags.get('EXIF DateTimeOriginal')
            if tag:
                date_taken_parts = re.search(r'(\d{,4}):(\d{,2})\:(\d{,2}) (\d{,2}):(\d{,2}):(\d{,2})', tag.values).groups()
                try:
                    taken_date = datetime.datetime(*[int(a) for a in date_taken_parts]).strftime('%s')
                except:
                    taken_date = membership_date
            else:
                taken_date = membership_date

            options = dict(
                photo_id=photo_id,
                date_posted=taken_date if int(taken_date) > int(membership_date) else membership_date
            )
            self.session_post('flickr.photos.setDates', params=options)
        except:
            print "X   Could not change posted date to taken date"

    def upload_photo(self, filename):
        if DO_UPLOAD:
            files = open(filename, 'rb')
            options = {
                'title': filename.split('/')[-1],
                'is_public': '0',
                'content_type': '1'
            }
            start = time.time()
            try:
                added_photo = self.flickr.post(params=options, files=files)
                end = time.time()
                elapsed = int(end - start)

                filesize = os.path.getsize(filename)
                speed = (filesize / elapsed) / 1000
                print ' --> %.2f KB/s' % speed
                if added_photo.get('stat', False) == 'ok':
                    return added_photo.get('photoid', None)
                else:
                    return None
            except:
                return None

    def create_photoset(self, node, name, photo_id, photo_title, description=''):
        options = dict(
            title=name,
            primary_photo_id=photo_id
        )
        try:
            resp = self.session_post('flickr.photosets.create', params=options)
            new_set_id = resp['photoset']['id']
            new_photoset = {
                'title': name,
                'description': description,
                'type': 'set',
                'id': new_set_id,
                'photos': {photo_title: photo_id}
            }
            self.put_set_in_collection(node, new_photoset)

            # CHEK if failed
            # message "Invalid primary photo id" means photo is not really uploaded, so
            # db is inconsistent, maybe the user has deleted the photo on flickr
            return new_set_id
        except:
            return False

    def get_collection(self, parts, create=True):
        node = self.collections
        for pos, part in enumerate(parts):
            if not node.get(part, False):
                if create:
                    self.create_collection(part, node)
                else:
                    return None
            node = node[part]
        return node

    def get_photoset(self, parents, photoset_title, create=True):
        collection_node = self.get_collection(parents, create=create)
        if collection_node:
            photoset_node = collection_node.get(photoset_title, None)
            return photoset_node
        else:
            return {}

    def load_photoset_photos(self, photoset):
        if 'photos' not in photoset:
            options = dict(
                photoset_id=photoset['id']
            )
            resp = self.session_get('flickr.photosets.getPhotos', params=options)
            photoset['photos'] = dict([(a['title'], a['id']) for a in resp['photoset']['photo']])

    def upload(self, filename):
        if 'Pictures' in filename:
            collection_tree, photoset_title, image_title = self.extract_parts(filename)
            photoset_node = self.get_photoset(collection_tree, photoset_title)

            if photoset_node is not None:
                # We have an existing photoset, so get the photo list
                # and upload the photo if not already in
                self.load_photoset_photos(photoset_node)

                photos_currently_in_photoset = set(photoset_node['photos'].keys())
                photos_currently_in_folder = set([a for a in os.listdir(filename[:filename.rfind('/')]) if a.lower().endswith('jpg')])

                missing_in_disk = photos_currently_in_photoset - photos_currently_in_folder

                # UNUSED CODE, to populate all files into db
                # for photo_title, photo_id in photoset_node['photos'].items():
                #     print 'updated', photo_title
                #     self.database.update_photo(photo_title, photoset_title, 'uploaded', 1)
                #     self.database.update_photo(photo_title, photoset_title, 'flickr_photo_id', photo_id)
                #     self.database.update_photo(photo_title, photoset_title, 'flickr_photoset_id', photoset_node['id'])
                #     self.database.update_photo(photo_title, photoset_title, 'date_uploaded', '1384815600')

                # Get the photo from the database, to check if its flickr_id is assigned in the photoset
                db_photo = self.database.get_photo_by_filename_and_album(image_title, photoset_title)

                if bool(db_photo['uploaded']):
                    # The photo was uploaded to flickr in the past ...
                    if LOG_EXISTING:
                        print '>  {} already uploaded on flickr on {}'.format(image_title, datetime.datetime.utcfromtimestamp(int(db_photo['date_uploaded'])).isoformat().replace('T', ' '))
                    if db_photo['flickr_photo_id'] not in photoset_node['photos'].values():
                        # But the photo was not assigned to this photoset, so put it
                        success = self.put_photo_in_photoset(photoset_node, db_photo['flickr_photo_id'], image_title)
                        if success is True:
                            print '>  {} Assigning already uploaded photo {} to photoset'.format(image_title, datetime.datetime.utcfromtimestamp(int(db_photo['date_uploaded'])).isoformat().replace('T', ' '))
                            self.database.update_photo(image_title, photoset_title, 'flickr_photoset_id', photoset_node['id'])
                            self.set_uploaded_date(db_photo['flickr_photo_id'], filename)
                        else:
                            if success == 'deleted':
                                print u'>  Photo {} is not in flickr photoset {}, resetting_photo and... try later'.format(image_title, photoset_title)
                                self.database.update_photo(image_title, photoset_title, 'uploaded', 0)
                                self.database.update_photo(image_title, photoset_title, 'flickr_photoset_id', '')
                                self.database.update_photo(image_title, photoset_title, 'flickr_photo_id', '')
                                self.database.update_photo(image_title, photoset_title, 'date_uploaded', '')
                            else:
                                print u'X  Error assigning photo {} to photoset {}, try later'.format(image_title, photoset_title)
                    else:
                        # And is assigned to this photoset, do nothing
                        if LOG_EXISTING:
                            print u'>  {} already in photoset {}'.format(image_title, photoset_title)

                else:
                    # This photo is not uploaded to flickr, so upload it
                    sys.stdout.write(u'>  Uploading {} to existing photoset {}'.format(image_title, photoset_node['title']))
                    sys.stdout.flush()
                    new_photo_id = self.upload_photo(filename)
                    if new_photo_id:
                        self.database.update_photo(image_title, photoset_title, 'uploaded', 1)
                        self.database.update_photo(image_title, photoset_title, 'date_uploaded', datetime.datetime.now().strftime('%s'))
                        self.database.update_photo(image_title, photoset_title, 'flickr_photo_id', new_photo_id)
                        self.set_uploaded_date(new_photo_id, filename)

                        success = self.put_photo_in_photoset(photoset_node, new_photo_id, image_title)
                        if success:
                            self.database.update_photo(image_title, photoset_title, 'flickr_photoset_id', photoset_node['id'])
                        else:
                            print u'X  Error assigning photo {} to photoset {}, try later'.format(image_title, photoset_title)
                    else:
                        print u'X  Error posting {}, try later'.format(image_title)

            else:
                # We have a new album, so first we upload the photo
                # and next create the photoset with that photo as primary
                # In the case of first/all photos already uploaded but flickr album missing
                # just put photo in photoset:

                # Try get the photo from the database, to check if its uploaded
                collection_node = self.get_collection(collection_tree)
                db_photo = self.database.get_photo_by_filename_and_album(image_title, photoset_title)

                if bool(db_photo['uploaded']):
                    print u'>  Assigning already uploaded photo {} to new photoset {}'.format(image_title, photoset_title)
                    new_photoset_id = self.create_photoset(collection_node, photoset_title, db_photo['flickr_photo_id'], image_title)
                    if new_photoset_id:
                        self.database.update_photo(image_title, photoset_title, 'flickr_photoset_id', new_photoset_id)
                        self.set_uploaded_date(db_photo['flickr_photo_id'], filename)
                    else:
                        print u'X  Error creating photoset {}, try later'.format(photoset_title)
                else:
                    sys.stdout.write(u'>  Uploading {} to new photoset {}'.format(image_title, photoset_title))
                    sys.stdout.flush()
                    new_photo_id = self.upload_photo(filename)
                    if new_photo_id:
                        self.database.update_photo(image_title, photoset_title, 'uploaded', 1)
                        self.database.update_photo(image_title, photoset_title, 'date_uploaded', datetime.datetime.now().strftime('%s'))
                        self.database.update_photo(image_title, photoset_title, 'flickr_photo_id', new_photo_id)
                        self.set_uploaded_date(new_photo_id, filename)

                        new_photoset_id = self.create_photoset(collection_node, photoset_title, new_photo_id, image_title)
                        if new_photoset_id:
                            self.database.update_photo(image_title, photoset_title, 'flickr_photoset_id', new_photoset_id)
                        else:
                            print u'X  Error creating photoset {}, try later'.format(photoset_title)
                    else:
                        print u'x  Error posting {}, try later'.format(image_title)
