from configparser import RawConfigParser as ConfigParser
import logging
import io
from optparse import Option
import os
from typing import *
from dotenv import dotenv_values
import pprint
import yaml
import builtins
from enum import Enum

class SectionProxy:
    def __init__(
        self,
        section_name: str, 
        section_options: Dict[str, Any],
    ):
        """
        Represents one Section of a config.ini file

        NOTE:
        -----
            - __getattr__ is caseinsensitive
        """
        self.name = section_name
        self.options = {}
        for key, value in section_options.items():
            if isinstance(value, dict):
                self.options[key] = self._dict_to_section_proxy(key, value)
            else:
                self.options[key] = value

    def __getattr__(self, name: str) -> str:
        name = name.lower()
        result = self.options.get(name, None)
        if result is None:
            raise AttributeError(f"config.ini section: `{self.name}` has no attribute `{name}`")
        return result

    def __repr__(self):
        return f"<`SectionProxy` section:{self.name}; attrs: {self.options}>"

    def get(self, item, default=None):
        return self.options.get(item, default)

    @staticmethod
    def _attribute_converter(attr: str):
        # to bool
        if attr == "True":
            return True
        elif attr == "False":
            return False
        # to float if `.` in attr
        elif attr.isdigit() and "." in attr:
            try:
                return float(attr)
            except Exception:
                pass
        # to int
        elif attr.isdigit and not "." in attr:
            try:
                return int(attr)
            except Exception:
                pass      
        # str as default
        return attr

    @classmethod
    def _dict_to_section_proxy(cls, key: str, d: dict):
        return cls(key, d)

class ConfigProxy():
    """
    Proxy for the `config.ini` and `.env` file

    NOTE:
    -----
        - __getattr__ is caseinsensitive
    """
    def __init__(self, config: List[SectionProxy]):
        self.sections = config

    def __getattr__(self, name: str) -> str:
        name = name.lower()
        sections = [s for s in self.sections if s.name == name]
        if sections == []:
            #search = [value for section in self.sections for value in section.options.values() if value == name]
            if len(sections) > 1:
                raise AttributeError(f"`config` (./config.ini) has multiple arrs called `{name}`; specify it with section")
            if len(sections) == 0:
                raise AttributeError(f"no section in config with name: `{name}`")
        elif len(sections) > 1:
            raise RuntimeError(f"config file (./config.ini) has multiple sections named `{name}`. Consider changing it!")
        return sections[0]
    
    def __repr__(self) -> str:
        sections = [str(s) for s in self.sections]
        return f"<ConfigProxy sections: {sections}>"

    def __iter__(self):
        return (s for s in self.sections)

    @staticmethod
    def create(config_type: Callable, path: Optional[str] = None) -> "ConfigProxy":
        """
        Returns:
        --------
            - (~.ConfigProxy) configproxy of cwd (config.ini and .env)
        """
        return config_type(path)


class ConfigAlgorithms:
    @staticmethod
    def yaml_config(path: Optional[str] = None):
        if path is None:
            path = f"{os.getcwd()}/config.yaml"
        stream = ""
        with open(path, "r", encoding="utf-8") as f:
            stream = f.read()
        config = yaml.load(stream, Loader=yaml.CLoader)
        return ConfigProxy(
            [SectionProxy(k, v) for k, v in config.items()]
        )

    @staticmethod
    def ini_config(path: Optional[str] = None):
        config = ConfigParser(allow_no_value=True)
        config.read(f"{os.getcwd()}/config.ini")

        section_proxies = []
        for section in config.sections():
            tmp_options = {}
            for option in config.options(section):
                tmp_options[option] = config.get(section, option)
            section_proxies.append(SectionProxy(section, tmp_options))
        #section_proxies.append(SectionProxy("env", dotenv_values()))       
        configproxy = ConfigProxy(section_proxies)
        return configproxy


class ConfigType:
    YAML = ConfigAlgorithms.yaml_config
    INI = ConfigAlgorithms.ini_config

if __name__ == "__main__":
    config = ConfigProxy.create(ConfigType.YAML)
    for s in config:
        print(s)
        
    
