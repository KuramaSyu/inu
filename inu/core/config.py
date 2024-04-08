from configparser import RawConfigParser as ConfigParser
import logging
import io
from optparse import Option
import os
from typing import *
from typing_extensions import Self
from dotenv import dotenv_values
import pprint
import yaml
import builtins
from enum import Enum

from . import Singleton

class SectionProxy:
    def __init__(
        self,
        section_name: str, 
        section_options: Dict[str, Any],
        case_insensitive: bool = True
    ):
        """
        Represents one Section of a `config.[yaml|ini]` file

        NOTE:
        -----
            - __getattr__ is case insensitive
        """
        self.case_insensitive = case_insensitive
        self.name = section_name
        self.options = {}
        self._options = section_options
        for key, value in section_options.items():
            if isinstance(value, dict):
                self.options[str(key)] = self._dict_to_section_proxy(key, value)
            else:
                self.options[str(key)] = value
        if self.case_insensitive:
            self.options = {k.lower(): v for k, v in self.options.items()}

    def __getattr__(self, name: str) -> str:
        name = name.lower()
        result = self.options.get(name, None)
        if result is None:
            raise AttributeError(f"config section: `{self.name}` has no attribute `{name}`")
        return result

    def __repr__(self):
        return f"<`SectionProxy` section:{self.name}; attrs: {self.options}>"
    
    def __str__(self):
        return f"{self.name}: {pprint.pformat(self.options)}"
    
    def pprint(self):
        pprint.pprint(
            {self.name: self._options},
            indent=4,
            compact=False,
            underscore_numbers=True
        )


    def get(self, item, default=None):
        return self.options.get(item, default)


    @classmethod
    def _dict_to_section_proxy(cls, key: str, d: dict):
        return cls(key, d)

class ConfigProxy(metaclass=Singleton):
    """
    Proxy for the `config.ini` and `.env` file

    NOTE:
    -----
        - __getattr__ is caseinsensitive
    """
    def __init__(
        self,
        config_type: Union[Callable[[Optional[str]], "ConfigProxy"], "ConfigType", None],
        path: Optional[str] = None,
    ):
        if config_type is None:
            raise RuntimeError("config_type cannot be None when initialized first time")
        self.sections, self._config = config_type(path)  #type: ignore

    def __getattr__(self, name: str) -> str:
        name = name.lower()
        sections = [s for s in self.sections if s.name == name]
        if sections == []:
            #search = [value for section in self.sections for value in section.options.values() if value == name]
            if len(sections) > 1:
                raise AttributeError(f"config has multiple attrs called `{name}`; specify it with section")
            if len(sections) == 0:
                raise AttributeError(f"no section in config with name: `{name}`")
        elif len(sections) > 1:
            raise RuntimeError(f"config has multiple sections named `{name}`")
        return sections[0]
    
    def __repr__(self) -> str:
        sections = [str(s) for s in self.sections]
        return f"<ConfigProxy sections: {sections}>"
    
    def __str__(self) -> str:
        sections = ",\n".join(str(s) for s in self.sections)
        return f"<ConfigProxy sections: {sections}>"

    def __iter__(self):
        return (s for s in self.sections)
    
    def pprint(self):
        return pprint.pprint(
            self._config,
            indent=4,
            compact=False,
            underscore_numbers=True
        )

    @staticmethod
    def create(config_type: Optional[Callable] = None, path: Optional[str] = None) -> "ConfigProxy":
        """
        Returns:
        --------
            - (~.ConfigProxy) configproxy of cwd (config.ini and .env)
        """
        if config_type is None:
            config_type = ConfigAlgorithms.yaml_config
        return config_type(path)


class ConfigAlgorithms:
    @staticmethod
    def yaml_config(path: Optional[str] = None) -> Tuple[List[SectionProxy], Dict[str, Any]]:
        if path is None:
            path = f"{os.getcwd()}/config.yaml"
        stream = ""
        with open(path, "r", encoding="utf-8") as f:
            stream = f.read()
        config = yaml.load(stream, Loader=yaml.CLoader)
        return [SectionProxy(k, v) for k, v in config.items()], config

    @staticmethod
    def ini_config(path: Optional[str] = None) -> Tuple[List[SectionProxy], List[str]]:
        config = ConfigParser(allow_no_value=True)
        config.read(f"{os.getcwd()}/config.ini")

        section_proxies = []
        for section in config.sections():
            tmp_options = {}
            for option in config.options(section):
                tmp_options[option] = config.get(section, option)
            section_proxies.append(SectionProxy(section, tmp_options))
        #section_proxies.append(SectionProxy("env", dotenv_values()))       
        return section_proxies, config


class ConfigType(Enum):
    YAML = ConfigAlgorithms.yaml_config
    INI = ConfigAlgorithms.ini_config

    @staticmethod
    def get_type(func: Callable) -> str:
        if func is ConfigAlgorithms.ini_config:
            return "ini"
        elif func is ConfigAlgorithms.yaml_config:
            return "yaml"
        else:
            raise RuntimeError(f"Function {func} is an unknown type")


if __name__ == "__main__":
    config = ConfigProxy(ConfigType.YAML)
    for s in config:
        pprint.pprint(s)
        
    
