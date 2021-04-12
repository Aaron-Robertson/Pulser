# Copyright 2020 Pulser Development Team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from functools import partialmethod
from itertools import chain
import operator
import warnings

from pulser.parametrized import Parametrized
from pulser.utils import obj_to_dict

# Availabe operations on parameterized objects with OpSupport
reversible_ops = [
    "__add__",
    "__sub__",
    "__mul__",
    "__truediv__",
    "__floordiv__",
    "__pow__",
    "__mod__"
]


class OpSupport:
    """Methods for supporting operators on parametrized objects."""

    def _do_op(self, op_name, other):
        return ParamObj(getattr(operator, op_name), self, other)

    def _do_rop(self, op_name, other):
        return ParamObj(getattr(operator, op_name), other, self)

    def __neg__(self):
        return ParamObj(operator.neg, self)

    def __abs__(self):
        return ParamObj(operator.abs, self)


# Inject operator magic methods into OpSupport
for method in reversible_ops:
    rmethod = "__r" + method[2:]
    setattr(OpSupport, method, partialmethod(OpSupport._do_op, method))
    setattr(OpSupport, rmethod, partialmethod(OpSupport._do_rop, method))


class ParamObj(Parametrized, OpSupport):
    def __init__(self, cls, *args, **kwargs):
        """Holds a call to a given class.

        When called, a ParamObj instance returns `cls(*args, **kwargs)`.

        Args:
            cls (callable): The object to call. Usually it's a class that's
                instantiated when called.
            args: The args for calling `cls`.
            kwargs: The kwargs for calling `cls`.
        """
        self.cls = cls
        self._variables = {}
        if isinstance(self.cls, Parametrized):
            self._variables.update(self.cls.variables)
        for x in chain(args, kwargs.values()):
            if isinstance(x, Parametrized):
                self._variables.update(x.variables)
        self.args = args
        self.kwargs = kwargs
        self._instance = None
        self._vars_state = {}

    @property
    def variables(self):
        return self._variables

    def build(self):
        """Builds the object with it's variables last assigned values."""
        vars_state = {key: var._count for key, var in self._variables.items()}
        if vars_state != self._vars_state:
            self._vars_state = vars_state
            # Builds all Parametrized arguments before feeding them to cls
            args_ = [arg.build() if isinstance(arg, Parametrized) else arg
                     for arg in self.args]
            kwargs_ = {key: val.build() if isinstance(val, Parametrized)
                       else val for key, val in self.kwargs.items()}
            obj = (self.cls.build() if isinstance(self.cls, ParamObj)
                   else self.cls)
            self._instance = obj(*args_, **kwargs_)
        return self._instance

    def _to_dict(self):
        if isinstance(self.cls, Parametrized):
            cls_dict = self.cls._to_dict()
        else:
            cls_dict = obj_to_dict(self, _build=False, _name=self.cls.__name__,
                                   _module=self.cls.__module__)
        return obj_to_dict(self, cls_dict, *self.args, **self.kwargs)

    def __call__(self, *args, **kwargs):
        obj = ParamObj(self, *args, **kwargs)
        warnings.warn("Calls to methods of parametrized objects are only "
                      "executed if they serve as arguments of other "
                      "parametrized objects that are themselves built. If this"
                      f" is not the case, the call to {obj} will not be "
                      "executed upon sequence building.")
        return obj

    def __getattr__(self, name):
        if hasattr(self.cls, name):
            return ParamObj(getattr, self, name)
        else:
            raise AttributeError(f"No attribute named '{name}' in {self}.")

    def __str__(self):
        args = [str(a) for a in self.args]
        kwargs = [f"{key}={str(value)}" for key, value in self.kwargs.items()]
        name = (str(self.cls) if isinstance(self.cls, Parametrized)
                else self.cls.__name__)
        return f"{name}({', '.join(args+kwargs)})"
