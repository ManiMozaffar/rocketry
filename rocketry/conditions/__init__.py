from functools import partial

from rocketry.time.interval import TimeOfHour, TimeOfMinute, TimeOfMonth

from .func import FuncCond
from .task import *
from .scheduler import *
from .time import *
from .parameter import ParamExists, IsEnv
from .meta import TaskCond

from rocketry.session import Session
from rocketry.core.condition import CLS_CONDITIONS
from rocketry.core.condition import AlwaysFalse, AlwaysTrue, All, Any, Not, BaseCondition

true = AlwaysTrue()
false = AlwaysFalse()

def _from_period_task_has(cls, span_type=None, inverse=False, **kwargs):
    from rocketry.time.construct import get_full_cycle, get_between, get_after, get_before
    from rocketry.time import TimeDelta

    period_func = {
        "between": get_between,
        "after": get_after,
        "before": get_before,
        "starting": get_full_cycle,
        None: get_full_cycle,
        "every": TimeDelta,
        "on": get_on,

        "past": TimeDelta,
    }[span_type]

    task = kwargs.pop("task", None)
    period = period_func(**kwargs)

    cls_kwargs = {"task": task} if task is not None else {}
    if inverse:
        return Not(cls(period=period, **cls_kwargs))
    else:
        return cls(period=period, **cls_kwargs)


def _set_is_period_parsing():
    
    from functools import partial

    def _get_is_period(period_constructor, *args, **kwargs):
        period = period_constructor(*args, **kwargs)
        return IsPeriod(period=period)

    cond_parsers = Session._cls_cond_parsers
    time_parsers = Session._time_parsers
    
    cond_parsers.update(
        {
            parsing: partial(_get_is_period, period_constructor=parser)
            for parsing, parser in time_parsers.items()
        }
    )

def _set_task_has_parsing():

    cond_parsers = Session._cls_cond_parsers

    clss = [
        ("failed", TaskFailed),
        ("succeeded", TaskSucceeded),
        ("finished", TaskFinished),
        ("terminated", TaskTerminated),
        ("inacted", TaskInacted),
        ("started", TaskStarted)
    ]
    for (action, cls) in clss:
        func = partial(_from_period_task_has, cls=cls)
        for prefix in ("", r"task '(?P<task>.+)' "):
            cond_parsers.update(
                {
                    re.compile(fr"{prefix}has {action}"): cls,
                    re.compile(fr"{prefix}has {action} (?P<type_>this month|this week|today|this hour|this minute) (?P<span_type>starting) (?P<start>.+)"): func,
                    re.compile(fr"{prefix}has {action} (?P<type_>this month|this week|today|this hour|this minute) (?P<span_type>between) (?P<start>.+) and (?P<end>.+)"): func,
                    re.compile(fr"{prefix}has {action} (?P<type_>this month|this week|today|this hour|this minute) (?P<span_type>after) (?P<start>.+)"): func,
                    re.compile(fr"{prefix}has {action} (?P<type_>this month|this week|today|this hour|this minute) (?P<span_type>before) (?P<end>.+)"): func,
                    re.compile(fr"{prefix}has {action} (?P<type_>this month|this week|today|this hour|this minute)"): func,
                    re.compile(fr"{prefix}has {action} (?P<type_>this month|this week|today|this hour|this minute) (?P<span_type>on) (?P<start>.+)"): func,
                    re.compile(fr"{prefix}has {action} (in )?past (?P<past>.+)"): partial(func, span_type='past'),
                }
            )

def _set_scheduler_parsing():

    cond_parsers = Session._cls_cond_parsers

    cls = SchedulerStarted
    func = partial(_from_period_task_has, cls=cls)
    cond_parsers.update(
        {
            re.compile(fr"scheduler has run over (?P<past>.+)"): partial(func, span_type='past', inverse=True),
            re.compile(fr"scheduler started (?P<past>.+) ago"): partial(func, span_type='past'),
        }
    )

def _set_task_exec_parsing():
    cond_parsers = Session._cls_cond_parsers

    conds = {
        "minutely": minutely,
        "hourly": hourly,
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
    }
    options = {
        r' (?P<span_type>before) (?P<end>.+)': 'before',
        r' (?P<span_type>between) (?P<start>.+) and (?P<end>.+)': 'between',
        r' (?P<span_type>after) (?P<start>.+)': 'after',
        r' (?P<span_type>starting) (?P<start>.+)': 'starting',
        r' (?P<span_type>on) (?P<start>.+)': 'on',
    }

    for str_period, cond in conds.items():
        cond_parsers[str_period] = cond

        for str_option, method_name in options.items():
            syntax = f"{str_period}{str_option}"
            method = getattr(cond, method_name)

            # Add to the syntax
            cond_parsers[syntax] = method

class _TimeCondition(BaseCondition):

    def __init__(self, cls_cond, cls_period):
        self._cls_cond = cls_cond
        self._cls_period = cls_period

    def between(self, start, end):
        period = self._cls_period(start, end)
        return self._cls_cond(period=period)

    def before(self, end):
        period = self._cls_period(None, end)
        return self._cls_cond(period=period)

    def after(self, start):
        period = self._cls_period(start, None)
        return self._cls_cond(period=period)

    def on(self, span):
        period = self._cls_period(span, time_period=True)
        return self._cls_cond(period=period)

    def starting(self, start):
        period = self._cls_period(start, start)
        return self._cls_cond(period=period)

    def __bool__(self):
        period = self._cls_period(None, None)
        return bool(self._cls_cond(period=period))

# Task finish 
minutely = _TimeCondition(TaskExecutable, TimeOfMinute)
hourly = _TimeCondition(TaskExecutable, TimeOfHour)
daily = _TimeCondition(TaskExecutable, TimeOfDay)
weekly = _TimeCondition(TaskExecutable, TimeOfWeek)
monthly = _TimeCondition(TaskExecutable, TimeOfMonth)


_set_is_period_parsing()
_set_task_has_parsing()
_set_scheduler_parsing()
_set_task_exec_parsing()