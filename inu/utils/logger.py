import logging


def build_logger(name=__name__, level=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    file_handler = logging.FileHandler("inu.log", mode="a")
    file_handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="{levelname} - {asctime} in {name}:\n{message}",
        datefmt="%b %d %H:%M:%S",
        style="{"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger

