import argparse
import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .config_manager import ConfigManager
from .server import ClientSideConnectionFactory


def main():
    parser = argparse.ArgumentParser(description="Python-based proxy server implementation for Starbound.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Enables verbose (debug) output.")
    parser.add_argument("-c", "--config", type=Path, default=(Path.home() / ".starrypy"),
                        help="Defines a custom path to the configuration directory.")
    parser.add_argument("-l", "--logfile", type=Path, default=(Path.home() / ".starrypy" / "starrypy.log"),
                        help="Defines a custom path to use for the log file.")
    parser.add_argument("-m", "--maintenace", action="store_true", help="Currently non-functional.")
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

    config_manager = ConfigManager(args)
    client_factory = ClientSideConnectionFactory(config_manager)

    try:
        srv = asyncio.start_server(client_factory, port=config_manager.config['listen_port'])
        loop = asyncio.get_event_loop()
        loop.run_until_complete(srv)
        loop.run_forever()
    except Exception as e:
        main_logger.exception("Exception occurred in main loop.", exc_info=True)
        sys.exit(1)