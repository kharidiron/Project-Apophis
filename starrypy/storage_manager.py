from contextlib import contextmanager
import logging
import pprint

import sqlalchemy as sqla
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


DeclarativeBase = declarative_base()
Session = sessionmaker()


# Database management stuff

def cache_query(result, collection=False):
    record = result

    if not isinstance(result, DeclarativeBase):
        return record

    if collection:
        record = []
        for r in result:
            record.append(SessionCacher(r))
    else:
        record = SessionCacher(result)

    return record


class SessionCacher(object):
    def __init__(self, record):
        self.__dict__["record"] = record

    def __getattr__(self, name):
        with db_session() as session:
            if sessionmaker.object_session(self.record) != session:
                session.add(self.record)
            session.refresh(self.record)
            val = getattr(self.record, name)
        return val

    def __setattr__(self, name, value):
        with db_session() as session:
            if sessionmaker.object_session(self.record) != session:
                session.add(self.record)
            session.refresh(self.record)
            setattr(self.record, name, value)
            session.merge(self.record)
            session.commit()

    def __str__(self):
        with db_session() as session:
            if sessionmaker.object_session(self.record) != session:
                session.add(self.record)
            session.refresh(self.record)
            return str(self.record)


@contextmanager
def db_session():
    logger = logging.getLogger("starrypy.storage_manager.db_session")
    session = Session()

    try:
        yield session
    except Exception as e:
        logger.error(f"Database access exception: {pprint.pformat(e)}")
        session.rollback()
    finally:
        session.close()


# Storage Manager

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
