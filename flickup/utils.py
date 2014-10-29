import yaml
import os

__config_path__ = os.path.expanduser('~/.flickup')
__config_file__ = '{}/config.yaml'.format(__config_path__)

__defaults__ = {
    "db": 'flickup.db',
    "processed": 'processed'
}


def load():
    """ Loads app settings. Generates defaults on first load."""
    if not os.path.exists(__config_path__):
        os.mkdir(__config_path__)

    if not os.path.exists(__config_file__):
        save(__defaults__)

    try:
        config = yaml.load(open(__config_file__).read())
    except:
        # Fallback to defaults if fail
        config = __defaults__

    config['db'] = '{}/{}'.format(__config_path__, config['db'])
    config['processed'] = '{}/{}'.format(__config_path__, config['processed'])
    return config


def save(config):
    """ Saves settings
    """
    open(__config_file__, 'w').write(yaml.dump(config))
