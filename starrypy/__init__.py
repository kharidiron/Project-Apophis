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
    # Set the current working directory to avoid funkiness with running as script
    os.chdir(Path(__file__).parent)

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

    stream_handler = logging.StreamHandler()    # This is temporary until urwid gets in
    stream_handler.setFormatter(log_formatter)  # We want to init this early for early log events
    main_logger.setLevel(loglevel)
    aio_logger.setLevel(loglevel)
    main_logger.addHandler(stream_handler)
    aio_logger.addHandler(stream_handler)

    if not args.config.exists():
        main_logger.warning(f"Specified config directory {args.config} does not exist! Creating now...")
        plugins_folder = args.config / "plugins"
        plugins_folder.mkdir(parents=True)  # Creates recursively
        init_file = args.config / "plugins" / "__init__.py"
        init_file.touch()  # Makes the __init__ file for the plugin folder, if you don't know what touch means

    if not args.logfile.exists():
        args.logfile.touch()
    file_handler = RotatingFileHandler(args.logfile, maxBytes=1048576, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(log_formatter)  # This part's done later, once we know we have a valid config directory.
    main_logger.addHandler(file_handler)
    aio_logger.addHandler(file_handler)

    main_logger.info("Starting main loop.")

    config_mgr = ConfigManager(args)
    client_factory = ClientSideConnectionFactory(config_mgr)

    # noinspection PyBroadException
    try:
        srv = asyncio.start_server(client_factory, port=config_mgr.config['listen_port'])
        loop = asyncio.get_event_loop()
        loop.run_until_complete(srv)
        loop.run_forever()
    except Exception:
        main_logger.exception("Exception occurred in main loop.", exc_info=True)
        sys.exit(1)
