import argparse
import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config_manager import ConfigManager
from .server import ClientSideConnectionFactory


__version__ = '3.0dev4'


def main():
    parser = argparse.ArgumentParser(description="Python-based proxy server implementation for Starbound.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Enables verbose (debug) output.")
    parser.add_argument("-c", "--config", type=Path, default=(Path.home() / ".starrypy"),
                        help="Defines a custom path to the configuration directory.")
    parser.add_argument("-l", "--logfile", type=Path, default=(Path.home() / ".starrypy" / "starrypy.log"),
                        help="Defines a custom path to use for the log file.")
    parser.add_argument("-m", "--maintenance", action="store_true", help="Currently non-functional.")
    parser.add_argument("--headless", action="store_true", help="Currently non-functional.")

    args = parser.parse_args()

    if args.verbose >= 1:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.INFO

    main_logger = logging.getLogger("starrypy")
    aio_logger = logging.getLogger("asyncio")
    log_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s # %(message)s",
                                      datefmt='%Y-%m-%d %H:%M:%S')
    if not args.config.exists():
        os.makedirs(args.config)
        os.makedirs(Path.home() / ".starrypy" / "plugins")
        with open(Path.home() / ".starrypy" / "plugins" / "__init__.py", 'a'):
            os.utime(Path.home() / ".starrypy" / "plugins" / "__init__.py", None)

    if not args.logfile.exists():
        args.logfile.touch()
    file_handler = RotatingFileHandler(args.logfile, maxBytes=1048576, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(log_formatter)
    stream_handler = logging.StreamHandler()  # This is temporary until urwid gets in
    stream_handler.setFormatter(log_formatter)

    main_logger.setLevel(loglevel)
    main_logger.addHandler(file_handler)
    main_logger.addHandler(stream_handler)
    aio_logger.setLevel(loglevel)
    aio_logger.addHandler(file_handler)
    aio_logger.addHandler(stream_handler)

    main_logger.info("Starting main loop.")

    config_mgr = ConfigManager(args)
    client_factory = ClientSideConnectionFactory(config_mgr)

    try:
        srv = asyncio.start_server(client_factory, port=config_mgr.config['listen_port'])
        loop = asyncio.get_event_loop()
        loop.run_until_complete(srv)
        loop.run_forever()
    except Exception:
        main_logger.exception("Exception occurred in main loop.", exc_info=True)
        sys.exit(1)
