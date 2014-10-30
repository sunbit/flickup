import unittest
from sh import mkdir
from sh import rm
from sh import cp
from flickup.walker import Walker


TEST_FOLDER = '/tmp/flickup/'
ROOT_FOLDER = '/tmp/flickup/Root'
TEST_DB = '{}/flickup.db'.format(TEST_FOLDER)
TEST_IMAGE = '{}/test.jpg'.format(__file__[:__file__.rfind('/')])
TEST_SETTINGS = {
    'db': TEST_DB,
    'root': ROOT_FOLDER
}


def root(path):
    """
        Returns a path prefixed with the root folder
    """
    return '{}/{}'.format(ROOT_FOLDER, path.lstrip('/'))


def makedirs(path=''):
    """
        Creates all folders in a path
    """
    mkdir('-p', root(path))


def place_photos(path, count):
    for i in range(1, count + 1):
        filename = '{}/IMG_{:0>4}.jpg'.format(root(path), count)
        cp(TEST_IMAGE, filename)


def cleanup(walker):
    collections = walker.uploader.collections


class TestCollections(unittest.TestCase):

    def setUp(self):
        # Make sure everything is clean,
        rm('-rf', TEST_FOLDER)
        makedirs()
        self.walker = Walker(TEST_SETTINGS)

    def tearDown(self):
        rm('-rf', TEST_FOLDER)
        cleanup(self.walker)

    def test_create_nested_album(self):
        makedirs('Test/2014/Album1')
        place_photos('Test/2014/Album1', 1)
        self.walker.run(root('Test'))

        self.walker.uploader.get_collections_tree()
        collections = self.walker.uploader.collections
        self.assertIn('Test', collections)
        self.assertIn('2014', collections['Test']['collection'][0]['title'])
        self.assertIn('Album', collections['Test']['collection'][0]['set'][0]['title'])
