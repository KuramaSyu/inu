import os
import json
import traceback
#from utils.settings import DATA_DIR

# json dump -> file is given in method
# json dumps -> declares variable as json object 


class Data():
    '''
    Class for storing and loading Data from Disk easily
    '''

    def __init__(self, sub_folder=None, mid_level_folder=None,
                 top_level_folder=None, file_name=None):
        if top_level_folder:
            self.TOP_LEVEL_FOLDER = f'{os.getcwd()}/{top_level_folder}'
        else:
            self.TOP_LEVEL_FOLDER = f'{os.getcwd()}/data'
        if mid_level_folder:
            self.MID_LEVEL_FOLDER = f'{mid_level_folder}'
        else:
            self.MID_LEVEL_FOLDER = f'individual_data'
        if sub_folder:
            self.SUB_LEVEL_FOLDER = f'{sub_folder}'
        else:
            self.SUB_LEVEL_FOLDER = f'default'
        if file_name:
            self.file_name = f'{file_name}'
        else:
            self.file_name = f'default.json'
        #self.file = file_name
        #if sub_folder_shortcut:
        #    self.append(key=str(sub_folder), value=str(sub_folder_shortcut), file_name='dns')

    def save(self, key, value, file_name = None, sub_folder = None, as_pickle = False) -> None:
        '''
        saves key:value in folder_name
        '''
        if not sub_folder:
            if self.SUB_LEVEL_FOLDER:
                sub_folder = self.SUB_LEVEL_FOLDER
            else:
                sub_folder = 'default'

        if not file_name:
            if self.file_name:
                file_name = self.file_name
            else:
                file_name = 'default'

        file_path = self.compile_path(f'{file_name}{".json" if not as_pickle else ".pickle"}')
            
        data = {str(key):value}
        if not as_pickle: # as json
            with open(file_path, 'w') as data_file:
                json.dump(data, data_file)

    def compile_path(self, file_name) ->str:
        '''
        NOTE: Filename WITH ENDING
        creates or fetches top, mid and sub_folder
        returns: sub_folder
        '''
        path = self.TOP_LEVEL_FOLDER
        if not os.path.isdir(path):
            os.mkdir(path)

        path = os.path.join(self.TOP_LEVEL_FOLDER, self.MID_LEVEL_FOLDER)
        if not os.path.isdir(path):
            os.mkdir(path)

        path_sub_folder = os.path.join(path, f'{self.SUB_LEVEL_FOLDER}')
        if not os.path.isdir(path_sub_folder):
            os.mkdir(path_sub_folder)      
        path_to_file = f'{path_sub_folder}/{file_name}'
            
        return path_to_file

    def load(self, key = None, file_name = None, sub_folder = None, as_pickle = False) -> dict:
        '''
        returns file or key:value; both in form of dict
        by default all keys and values von default.json are returned
        '''
        if not sub_folder:
            if self.SUB_LEVEL_FOLDER:
                sub_folder = self.SUB_LEVEL_FOLDER
            else:
                sub_folder = 'default'

        if not file_name:
            if self.file_name:
                file_name = self.file_name
            else:
                file_name = 'default'

        file_path = self.compile_path(f'{file_name}{".json" if not as_pickle else ".pickle"}')

        try:
            if not as_pickle:  # as json
                with open(file_path, 'r') as data_file:
                    data_dict = json.load(data_file)

            if not key:
                return data_dict

            data = data_dict[key]
            data_dict = {
                key: data
            }
            return data_dict
        except Exception:
            traceback.print_exc()

    def append(self, key: str, value: str, file_name: str = None, sub_folder = None, as_pickle = False) -> None:
        '''
        saves key:value in folder_name
        '''

        if not sub_folder:
            if self.SUB_LEVEL_FOLDER:
                sub_folder = self.SUB_LEVEL_FOLDER
            else:
                sub_folder = 'default'

        if not file_name:
            if self.file_name:
                file_name = self.file_name
            else:
                file_name = 'default'

        file_path = self.compile_path(f'{file_name}{".json" if not as_pickle else ".pickle"}')
        file_ = file_path

        if not as_pickle: # as json
           # load data 
            data_dict = {}
            if os.path.isfile(file_):
                with open(file_, 'r') as data_file:
                    data_dict = json.load(data_file)

            # extend data
            if str(key) in data_dict.keys():
                if not isinstance(data_dict[key], list):
                    new_value = [data_dict[key], value]
                    data_dict[str(key)] = new_value
                else:
                    data_dict[str(key)].append(value)
            else:
                data_dict[str(key)] = value

            print(data_dict)

            # save data
            with open(file = file_, mode = 'w') as data_file:
                json.dump(data_dict, data_file)