import re
from inspect import (
    getdoc,
    iscoroutinefunction,
    isfunction,
    ismethod,
    signature,
)
from typing import Union, List, Mapping


class ObjectTreeViewer():
    N = "\n"

    @staticmethod
    def _get_obj_tree_list(
            object,
            search_for: str = '',
            with_docs=False,
            with_dunder_attr=False,
            depth=2,
            method_sign=True,
    ) -> List[Mapping[str, Union[str, list]]]:

        info_list = []
        dir_list = [attr for attr in dir(object) if search_for in attr]

        # removes private attrs for obj checking
        def remove_dunder(dir_list: list):
            copy_dir_list = [attr for attr in dir_list 
                            if not attr.startswith("_") 
                            and not attr.endswith("_")]
            return copy_dir_list

        if not with_dunder_attr:
            dir_list = remove_dunder(dir_list)
        
        # iterates throught object
        for attr in dir_list:
            str_attr = attr
            try:
                attr = getattr(object, attr)
            except Exception:
                pass
            
            is_method_or_func = isfunction(attr) or ismethod(attr)
            is_coro = iscoroutinefunction(attr)
            docs = None
            if is_method_or_func and (doc := getdoc(attr)) and with_docs:
                docs = str(doc + "\n")
            
            # create prefix
            prefix = ""
            try:
                if isinstance(attr, (int, str, dict, list, tuple, float, bool)):
                    prefix = str(type(attr))[8:-2] + " "
                elif is_coro:
                    prefix = "coro "
                elif is_method_or_func:
                    prefix = "func "
                elif remove_dunder(dir_list):
                    prefix = "obj "
                else:
                    prefix = "? "
            except Exception:
                pass

            # getting subobjects recursivly
            sub_attrs = []
            if (
                prefix == "obj "
                and not str_attr.startswith("__")
                and depth
            ):
                sub_attrs = __class__._get_obj_tree_list(
                    object=attr,
                    with_docs=with_docs,
                    depth=depth-1,
                    with_dunder_attr=with_dunder_attr,
                    method_sign=False,
                )

            # creates dict of object and all its subobjects
            info = {
                "prefix": prefix,
                "attr": 
                f'{str_attr}{signature(attr) if is_method_or_func and method_sign else ""}',
                "docs": f'{docs if docs else ""}',
                "sub_attrs": sub_attrs,
            }
            info_list.append(info)
        return info_list

    @staticmethod
    def _to_tree(
        info: List[Mapping[str, Union[str, list]]],
        depth=2,
        with_docs=False,
        _indent="|",
        _current_depth=0,
    ) -> str:
        """
        Converts the list from __class__._get_obj_tree_dict() to a string 
        which looks like a tree
        """

        N = "\n"
        info_str = ""
        l = len(info)

        # enumerates through the list with objects
        for i, d in enumerate(info):
            last_item_ = True if i+1 == l else False
            sub_conc_attr = None

            # if object is not a primary datatype it will be recursivly resolved
            if "obj" in d['prefix']:
                sub_conc_attr = __class__._to_tree(
                    info=d['sub_attrs'],
                    _indent=f"{_indent}    {'│'}",
                    _current_depth=_current_depth+1,
                )

            docs = ""
            if with_docs and d['docs']:
                #doc_list = crumble(d['docs'], max_len=79-len(_indent))
                doc_list = [d['docs']]
                for line in doc_list:
                    line = line.replace('\n', '')
                    docs += f'\n{_indent}    └──>{line}'

            # create print of object
            conc_attr = f"{str(_indent)[:-1]}{'└' if last_item_ else '├'}──"\
                        f"{d['prefix']}{d['attr']}"\
                        f"{docs}"\
                        f"{N}{sub_conc_attr if sub_conc_attr else ''}"\
                        f"{N if not last_item_ else ''}"

            info_str += conc_attr
        while "\n\n\n" in info_str:
            info_str = re.sub("\n\n\n", "\n", info_str)
        while "\n\n" in info_str:
            info_str = re.sub("\n\n", "\n", info_str)
        return info_str

    @staticmethod
    def _wrap_objects_by_root_object(object_, object_list):
        info = {
            "prefix": f'root_object - {object_.__class__.__name__}',
            "attr": '',
            "docs": '',
            "sub_attrs": object_list,
        }
        return [info]

    @staticmethod
    def tree_view(
        object_,
        search_for='',
        depth=0,
        with_docs=False,
        with_dunder=False,
        with_method_sign: bool = False,
    ) -> str:
        """
        Converts <object> to a tree with <depth> sub_objects if any. 
        Only attributes which contain <search_for> will be displayed.
        <with_dunder>: wehter or not __dunder__ attributes should be displayed.
        <with_docs> wether or not docs should be displayed.
        """

        obj_tree_list: list = __class__._get_obj_tree_list(
            object=object_,
            search_for=search_for,
            with_docs=with_docs,
            with_dunder_attr=with_dunder,
            depth=depth,
            method_sign=with_method_sign,
        )
        # wr_obj_tree_list = __class__._wrap_objects_by_root_object(
        #     object_=object,
        #     object_list=obj_tree_list,
        # )
        tree: str = __class__._to_tree(
            obj_tree_list,
            depth=depth,
            with_docs=with_docs,
            )
        return tree


def tree(
    obj=None,
    depth: int = 0,
    search_for: str = '',
    with_method_sign: bool = False,
    with_docs: bool = False,
    with_private: bool = False,
) -> str:
    """
    Converts <object> to a tree with <depth> sub_objects if any.
    Only attributes which contain <search_for> will be displayed.
    <with_dunder>: wehter or not _dunder_ (also single one) attributes should be displayed.
    <with_docs> wether or not docs should be displayed.
    Same as ObjectTreeViewer.tree_view() .
    Returns this, when object stays None.
    """

    TREE_BUILD = f'as_tree{signature(tree)}'
    TREE_DOC = tree.__doc__

    if obj == None:
        return f"{TREE_BUILD}\n{TREE_DOC}"

    return ObjectTreeViewer.tree_view(
        object_=obj,
        search_for=search_for,
        depth=depth,
        with_docs=with_docs,
        with_dunder=with_private,
        with_method_sign=with_method_sign,
    )