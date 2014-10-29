from setuptools import setup, find_packages

version = '0.0'

setup(name='flickup',
      version=version,
      description="Yet another Flickr File Uploader",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Carles Bruguera',
      author_email='carlesba@gmail.com',
      url='https://github.com/sunbit/flickup',
      license='GPL',
      packages=find_packages(exclude=['ez_setup', 'examples']),
      include_package_data=True,
      test_suite="tests",
      zip_safe=True,
      install_requires=[
          # -*- Extra requirements: -*-
          "python-flickr",
          "rauth",
          "docopt",
          "pysqlite",
          "sh",
          "exifread",
          "pyyaml"
      ],
      extras_require={
          'tests': []
      },
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      flickup = flickup:main
      """,
      )
