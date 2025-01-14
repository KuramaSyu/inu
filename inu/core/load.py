"""This file contains Algorithms to load tasks and commands"""

from typing import *
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from .bot import Inu

class LoaderABC(ABC):
    @abstractmethod
    async def load(self, inu: "Inu"):
        pass

class CommandLoader(LoaderABC):
    async def load(self):
        """
        Loads extensions in <folder_path> and ignores files starting with `_` and ending with `.py`
        """
        # TODO: remove when finished with testing
        def is_allowed(extension: str) -> bool:
            for allowed in ALLOWED_EXTENSIONS:
                if allowed in extension:
                    return True
            return False

        self.scheduler.start()  # TODO: this should go somewhere else
        modules: Dict[str, bool] = defaultdict(lambda: True)
        for extension in os.listdir(os.path.join(os.getcwd(), folder_path)):
            if (
                extension == "__init__.py" 
                or not extension.endswith(".py")
                or extension.startswith("_")
            ):
                continue
            try:
                trimmed_name = f"{folder_path.replace('/', '.')[4:]}{extension[:-3]}"
                modules[trimmed_name]
                if not is_allowed(trimmed_name):
                    modules[trimmed_name] = False
                    continue
                importlib.import_module(trimmed_name)
                await self.client.load_extensions(trimmed_name)
            except Exception:
                self.log.critical(f"can't load {extension}\n{traceback.format_exc()}", exc_info=True)
        table = tabulate.tabulate(modules.items(), headers=["Extension", "Loaded"])
        self.log.info(table, multiline=True, prefix="init")