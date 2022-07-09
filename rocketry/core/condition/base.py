import datetime
from abc import abstractmethod
from typing import Callable, Dict, Pattern, Union, Type

from rocketry._base import RedBase
from rocketry.core.meta import _add_parser, _register
from rocketry.core.parameters.parameters import Parameters
from rocketry.session import Session


CLS_CONDITIONS: Dict[str, Type['BaseCondition']] = {}
PARSERS: Dict[Union[str, Pattern], Union[Callable, 'BaseCondition']] = {}


class _ConditionMeta(type):
    def __new__(mcs, name, bases, class_dict):

        cls = type.__new__(mcs, name, bases, class_dict)

        # Store the name and class for configurations
        # so they can be used in dict construction
        _register(cls, CLS_CONDITIONS)

        # Add the parsers
        if cls.session is None:
            # Rocketry's default conditions
            # storing to the class
            _add_parser(cls, container=Session._cls_cond_parsers)
        else:
            # User defined conditions
            # storing to the object
            _add_parser(cls, container=Session._cls_cond_parsers)
        return cls


class BaseCondition(RedBase, metaclass=_ConditionMeta):
    """A condition is a thing/occurence that should happen in 
    order to something happen.

    Conditions are used to determine whether a task can be started,
    a task should be terminated or the scheduler should shut 
    down. Conditions are either true or false.

    A condition could answer for any of the following questions:
        - Current time is as specified (ie. Monday afternoon).
        - A given task has already run.
        - The machine has at least a given amount of RAM.
        - A specific file exists.

    Each condition should have the method ``__bool__`` specified
    as minimum. This method should return ``True`` or ``False``
    depending on whether the condition holds or does not hold.  

    Examples
    --------

    Minimum example:

    >>> from rocketry.core import BaseCondition
    >>> class MyCondition(BaseCondition):
    ...     def __bool__(self):
    ...         ... # Code that defines state either 
    ...         return True

    Complicated example with parser:

    >>> import os, re
    >>> class IsFooBar(BaseCondition):
    ...     __parsers__ = {
    ...         re.compile(r"is foo '(?P<outcome>.+)'"): "__init__"
    ...     }
    ...
    ...     def __init__(self, outcome):
    ...         self.outcome = outcome
    ...
    ...     def __bool__(self):
    ...         return self.outcome == "bar"
    ...
    ...     def __repr__(self):
    ...         return f"IsFooBar('{self.outcome}')"
    ...
    >>> from rocketry.parse import parse_condition
    >>> parse_condition("is foo 'bar'")
    IsFooBar('bar')

    """
    # The session (set in rocketry.session)
    session: Session

    __parsers__ = {}
    __register__ = False

    def observe(self, **kwargs):
        "Observe the status of the condition"
        cond_params = Parameters._from_signature(self.get_state, **kwargs)
        return self.get_state(**cond_params)

    def __bool__(self) -> bool:
        """Check whether the condition holds."""
        return self.observe()

    @abstractmethod
    def get_state(self):
        """Get the status of the condition 
        (using arguments)
        
        Override this method."""

    def __and__(self, other):
        # self & other
        # bitwise and
        # using & operator

        return All(self, other)

    def __or__(self, other):
        # self | other
        # bitwise or

        return Any(self, other)

    def __invert__(self):
        # ~self
        # bitwise not
        return Not(self)

    def __eq__(self, other):
        "Equal operation"
        is_same_class = isinstance(other, type(self))
        return is_same_class

    def __str__(self):
        if hasattr(self, "_str"):
            return self._str
        else:
            raise AttributeError(f"Condition {type(self)} is missing __str__.")


class _ConditionContainer:
    "Wraps another condition"

    def __getitem__(self, val):
        return self.subconditions[val]

    def __iter__(self):
        return iter(self.subconditions)

    def __eq__(self, other):
        "Equal operation"
        is_same_class = isinstance(other, type(self))
        if is_same_class:
            return self.subconditions == other.subconditions
        else:
            return False

    def __repr__(self):
        string = ', '.join(map(str, self.subconditions))
        return f'{type(self).__name__}({string})'

class Any(_ConditionContainer, BaseCondition):

    def __init__(self, *conditions):
        self.subconditions = []

        self_type = type(self)
        for cond in conditions:
            # Avoiding nesting (like Any(Any(...), ...) --> Any(...))
            conds = cond.subconditions if isinstance(cond, self_type) else [cond]
            self.subconditions += conds

    def observe(self, **kwargs) -> bool:
        for subcond in self.subconditions:
            if subcond.observe(**kwargs):
                return True
        return False

    def __str__(self):
        try:
            return super().__str__()
        except AttributeError:
            string = ' | '.join(map(str, self.subconditions))
            return f'({string})'


class All(_ConditionContainer, BaseCondition):

    def __init__(self, *conditions):
        self.subconditions = []

        self_type = type(self)
        for cond in conditions:
            # Avoiding nesting (like All(All(...), ...) --> All(...))
            conds = cond.subconditions if isinstance(cond, self_type) else [cond]
            self.subconditions += conds

    def observe(self, **kwargs) -> bool:
        for subcond in self.subconditions:
            if not subcond.observe(**kwargs):
                return False
        return True

    def __str__(self):
        try:
            return super().__str__()
        except AttributeError:
            string = ' & '.join(map(str, self.subconditions))
            return f'({string})'

    def __getitem__(self, val):
        return self.subconditions[val]


class Not(_ConditionContainer, BaseCondition):

    def __init__(self, condition):
        # TODO: rename condition as child
        self.condition = condition

    def observe(self, **kwargs):
        return not(self.condition.observe(**kwargs))

    def __repr__(self):
        string = repr(self.condition)
        return f'~{string}'

    def __str__(self):
        try:
            return super().__str__()
        except AttributeError:
            string = str(self.condition)
            return f'~{string}'

    @property
    def subconditions(self):
        return (self.condition,)

    def __iter__(self):
        return iter((self.condition,))
        
    def __invert__(self):
        "inverse of inverse is the actual condition"
        return self.condition

    def __eq__(self, other):
        "Equal operation"
        is_same_class = isinstance(other, type(self))
        if is_same_class:
            return self.condition == other.condition
        else:
            return False


class AlwaysTrue(BaseCondition):
    "Condition that is always true"
    def observe(self, **kwargs):
        return True

    def __repr__(self):
        return 'AlwaysTrue'

    def __str__(self):
        try:
            return super().__str__()
        except AttributeError:
            return 'true'


class AlwaysFalse(BaseCondition):
    "Condition that is always false"

    def observe(self, **kwargs):
        return False

    def __repr__(self):
        return 'AlwaysFalse'

    def __str__(self):
        try:
            return super().__str__()
        except AttributeError:
            return 'false'