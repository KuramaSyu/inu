from abc import ABC, abstractmethod
import inspect

# Define a function to recursively find unimplemented abstract methods
def check_unimplemented_methods(cls) -> set:
    """
    Checks which methods of a class are still abstract and need implementation
    """
    unimplemented = set()

    # Go through the MRO (method resolution order) to include all base classes
    for base in inspect.getmro(cls):
        if hasattr(base, "__abstractmethods__"):
            abstract_methods = base.__abstractmethods__
            implemented_methods = {
                name for name, _ in cls.__dict__.items() if callable(_) or isinstance(_, property)
            }
            unimplemented.update(abstract_methods - implemented_methods)

    return unimplemented