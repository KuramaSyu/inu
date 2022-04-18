import logging

class Singleton(type):
    _instances = {}
    _log = logging.getLogger(__name__)
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
            cls._log.info("Created Singleton for `{cls.__name__}`")
        cls._log.info("Returned Singleton for `{cls.__name__}`")
        return cls._instances[cls]