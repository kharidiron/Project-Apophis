import logging
import yaml
from pathlib import Path
from shutil import copyfile


class ConfigManager:
    def __init__(self, argv):
        self.argv = argv
        self.config_path = argv.config
        if self.config_path.is_dir():
            self.config_path /= "config.yaml"
        self.logger = logging.getLogger("starrypy.config_manager")
        self.logger.debug("Initialized config manager.")
        self.config = self.load_config()
        self.config["config_path"] = self.config_path.parents[0]
        self.config["system_plugin_path"] = Path(__file__).parents[0] / "plugins"
        self.config["user_plugin_path"] = self.config_path.parents[0] / "plugins"

    def load_config(self):
        self.logger.debug("Loading configuration.")

        default_config = Path(__file__).parents[0] / "_example" / "config.yaml"

        try:
            with self.config_path.open(encoding="utf-8") as fp:
                conf = yaml.safe_load(fp)
        except FileNotFoundError:
            self.logger.error(f"File {self.config_path.expanduser()} does not exist! Copying default.")
            copyfile(default_config, self.config_path)
            self.logger.warning(f"Please edit the file at {self.config_path} before running again.")
            raise SystemExit
        except yaml.YAMLError:
            self.logger.exception(f"File {self.config_path.expanduser()} is not valid YAML!", exc_info=True)
            raise
        return conf

    def save_config(self):
        temp_path = self.config_path.with_suffix(".yaml.temp")
        with temp_path.open("w", encoding="utf-8") as fp:
            yaml.safe_dump(self.config, fp)
        temp_path.replace(self.config_path)
        self.logger.debug("Saved config file.")
