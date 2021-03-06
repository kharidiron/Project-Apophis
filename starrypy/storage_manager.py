import logging
from contextlib import contextmanager

import sqlalchemy as sqla
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


DeclarativeBase = declarative_base()
Session = sessionmaker()


@contextmanager
def db_session(_sessionmaker):
    session = _sessionmaker()

    try:
        yield session
    except:
        session.rollback()
    finally:
        session.close()


class SessionAccessMixin:
    def __init__(self, *args, **kwargs):
        super(self).__init__(*args, **kwargs)
        self.session = Session


class StorageManager:
    def __init__(self, factory):
        self.logger = logging.getLogger("starrypy.storage_manager")
        self.factory = factory
        self.config_manager = factory.config_manager

        conf = self.config_manager.config
        db_file = conf['config_path'] / conf['database_file']
        self.engine = sqla.create_engine(f"sqlite:///{db_file}")

        DeclarativeBase.metadata.create_all(self.engine, checkfirst=True)
        Session.configure(bind=self.engine)

