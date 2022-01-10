from configparser import ConfigParser
import logging
import io
import os
from typing import *
from dotenv import dotenv_values
import pprint


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
        self.options = section_options

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
            search = [value for section in self.sections for value in section.options.values() if value == name]
            if len(search) > 1:
                raise AttributeError(f"`config` (./config.ini) has multiple arrs called `{name}`; specify it with section")
            if len(search) == 0:
                raise AttributeError(f"no section in config has a attr `{name}`")
        elif len(sections) > 1:
            raise RuntimeError(f"config file (./config.ini) has multiple sections named `{name}`. Consider changing it!")
        return sections[0]

    @staticmethod
    def create() -> "ConfigProxy":
        """
        Returns:
        --------
            - (~.ConfigProxy) configproxy of cwd (config.ini and .env)
        """
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

