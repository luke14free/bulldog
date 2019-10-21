from functools import wraps
from typing import Callable, List, Any, Dict, Union
from pathos.multiprocessing import ProcessingPool as Pool

from copy import deepcopy
from collections import OrderedDict, namedtuple
from multiprocessing import cpu_count

version = "1.0.3"

FROZEN_ERROR = "model data is readonly. It can only be modified with a data_modifier"
DATA_MODIFIER_NOT_CALLABLE_ERROR = "data_modifier(s) should be committed, not called directly"
BUSINESS_LOGIC_NOT_CALLABLE_ERROR = "business_logic(s) should be dispatched, not called directly"
DATA_MODIFIER_NOT_FOUND = "{} is not a registered data_modifier"
BUSINESS_LOGIC_NOT_FOUND = "{} is not a registered business_logic"
BUSINESS_LOGIC_ALREADY_EXECUTED = "{} was already executed, raising and error since `unique_bl_steps` was set to true"


class BusinessLogicNotCallableException(Exception):
    pass


class DataModifierNotCallableException(Exception):
    pass


class DataNotDirectlyModifiableException(Exception):
    pass


class DataModifierNotFound(Exception):
    pass


class BusinessLogicNotFound(Exception):
    pass


class NoCheckpointAvailableForKey(Exception):
    pass


class BusinessLogicAlreadyExecutedException(Exception):
    pass


Version = namedtuple('Version', 'step name')


class Model:
    def __init__(self, data: Dict, max_pool_size=0, unique_bl_steps=True,
                 on_checkpoint_save: Union[None, Callable] = None,
                 on_checkpoint_restore: Union[None, Callable] = None) -> None:
        self._data = data
        self.checkpoints = []
        self.data_modifiers = {}
        self.business_logics = {}
        self.analyses = {}
        self.parallelizables = []
        self._history = OrderedDict({})
        self.unique_bl_steps = unique_bl_steps
        self.pool = Pool(max_pool_size or cpu_count())
        self.on_checkpoint_save = on_checkpoint_save
        self.on_checkpoint_restore = on_checkpoint_restore

    @property
    def data(self) -> Dict:
        return deepcopy(self._data)

    @data.setter
    def data(self, value: Dict) -> None:
        raise DataNotDirectlyModifiableException(FROZEN_ERROR)

    @data.deleter
    def data(self) -> None:
        raise DataNotDirectlyModifiableException(FROZEN_ERROR)

    @property
    def history(self) -> Dict:
        return deepcopy(self._history)

    @history.setter
    def history(self, value: Dict) -> None:
        raise DataNotDirectlyModifiableException(FROZEN_ERROR)

    @history.deleter
    def history(self) -> None:
        raise DataNotDirectlyModifiableException(FROZEN_ERROR)

    def data_modifier(self, func: Callable) -> Callable:
        self.data_modifiers[func.__name__] = func

        @wraps
        def wrapper():
            raise DataModifierNotCallableException(DATA_MODIFIER_NOT_CALLABLE_ERROR)

        return wrapper

    def business_logic(self, func: Callable) -> Callable:
        self.business_logics[func.__name__] = func

        @wraps
        def wrapper():
            raise BusinessLogicNotCallableException(BUSINESS_LOGIC_NOT_CALLABLE_ERROR)

        return wrapper

    def run_analyses(self):
        if not self.parallelizables:
            for func in self.analyses.values():
                func(self.data, self._history)
        else:
            analyses = [i for i in self.analyses.keys() if i in self.parallelizables]

            def run_analysis_by_key(key: str) -> Any:
                if key in self.parallelizables:
                    return self.analyses[key](self.data, self._history)
                else:
                    return None

            self.pool.map(run_analysis_by_key, analyses)
            for func_name, func in self.analyses.items():
                if func_name not in self.parallelizables:
                    func(self.data, self._history)

    def commit(self, data_modifier_name: str, *commit_args: List, **commit_kwargs: Dict) -> Dict:
        version_key = Version(step=len(self._history), name=data_modifier_name)
        self._history[version_key] = None
        try:
            self._data = self.data_modifiers[data_modifier_name](self.data, *commit_args, **commit_kwargs)
        except KeyError:
            raise DataModifierNotFound(DATA_MODIFIER_NOT_FOUND.format(data_modifier_name))
        if data_modifier_name in self.checkpoints:
            self.run_analyses()
            self._history[version_key] = self.data if not self.on_checkpoint_save else self.on_checkpoint_save(
                self.data, self.history)
        return self._data

    def dispatch(self, business_logic_name: str, *args: List, **kwargs: Dict) -> Any:
        commit = self.commit
        if self.unique_bl_steps:
            for key in self.history.keys():
                if key.name == business_logic_name:
                    raise BusinessLogicAlreadyExecutedException(BUSINESS_LOGIC_ALREADY_EXECUTED)
        try:
            output = self.business_logics[business_logic_name](self.data, *args, **kwargs, commit=commit)
        except KeyError:
            raise BusinessLogicNotFound(BUSINESS_LOGIC_NOT_FOUND.format(business_logic_name))
        version_key = Version(step=len(self._history), name=business_logic_name)
        if business_logic_name in self.checkpoints:
            self.run_analyses()
            self._history[version_key] = self.data if not self.on_checkpoint_save else self.on_checkpoint_save(
                self.data, version_key, self.history)
        else:
            self._history[version_key] = None
        return output

    def checkpoint(self, func: Callable) -> Callable:
        self.checkpoints.append(func.__name__)
        return func

    def parallelizable(self, func: Callable) -> Callable:
        self.parallelizables.append(func.__name__)
        return func

    def analysis(self, func: Callable) -> Callable:
        self.analyses[func.__name__] = func
        return func

    def revert_version(self, version_key: Version) -> None:
        prev_value = self._history[version_key] if not self.on_checkpoint_restore else self.on_checkpoint_restore(
            version_key, self._history)
        if not prev_value:
            raise NoCheckpointAvailableForKey(version_key)
        self._data = prev_value
        for key in self.history.keys():
            if key.step > version_key.step:
                del self._history[key]

    def rollback(self, number_of_steps: int = 1) -> None:
        version_key = list(self._history.keys())[-(number_of_steps + 1)]
        self.revert_version(version_key)
