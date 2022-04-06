from os import path
import sys
import subprocess

# implement pip as a subprocess:a
def update_package(package: str) -> None:
    if " @ " in package and "https://github.com" in package:
        # github package
        display_name, path_name = package.split(" @ ")
    elif "==" in package:
        # traditional package
        display_name, _ = package.split("==")
        path_name = display_name
    else:
        display_name = path_name = package
    print(display_name, path_name)
    try:
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', path_name]
        )
    except Exception as e:
        print("Error while installing dependencies")
        print(e)

def remove_sha(path_name):
    split_index = None
    for i, c in enumerate(reversed(path_name)):
        if c == "@":
            split_index = len(path_name - i)
    if split_index:
        path_name = path_name[:split_index]
    print(path_name)
    return path_name

def main():
    # install latest
    with open("requirements.txt", "r") as reqs:
        for line in reqs.readlines():
            line.strip()
            update_package(line)
    print("installation complete")

if __name__ == "__main__":
    main()
