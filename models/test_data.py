import os

from data import Data

SETTINGS_DIR = os.path.dirname(os.path.abspath(__file__))
UTILS_DIR = os.path.dirname(SETTINGS_DIR)
ROOT_DIR = os.path.dirname(UTILS_DIR)
DATA_DIR = f'{ROOT_DIR}/data'
MODELS_DIR = f'{ROOT_DIR}/models'

print(ROOT_DIR)
Data = Data()
Data.append('key', 'my name is asdfgdfgsdfsdfad', file_name='file')
data = Data.load(key = 'key' ,file_name = 'file')
print(data)
Data.append('new key', 'new value', file_name='file')
print('-----')
print(Data.load(file_name='file'))