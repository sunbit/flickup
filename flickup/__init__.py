# -*- coding: utf-8 -*-
"""
FlickUp Flickr Uploader

Usage:
  iteriatest [<path>]

Options:
"""

DO_CONVERT = False
DO_UPLOAD = True
LOG_EXISTING = False

from docopt import docopt
from flickup.walker import Walker
from flickup.utils import load


def main():
    arguments = docopt(__doc__, version='FlickUp Flickr Uploader')
    path = arguments['<path>'].decode('utf-8') if arguments.get('<path>') else u'.'
    import ipdb;ipdb.set_trace()

    settings = load()

    flickup = Walker(path, settings)
    flickup.run()

if __name__ == '__main__':
    main()
