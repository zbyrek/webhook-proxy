import os
import time
import threading
import traceback

from flask import request
from jinja2 import Template

from util import ActionInvocationException
from util import ConfigurationException


def _safe_import():
    class SafeImportContext(object):
        def __enter__(self):
            pass

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_tb:
                error_file = traceback.extract_tb(exc_tb)[1][0]
                name, _ = os.path.splitext(os.path.basename(error_file))

                if name.startswith('action_'):
                    name = name[len('action_'):].replace('_', '-')

                print('The "%s" action is not available' % name)

                return True

    return SafeImportContext()


def _register_available_actions():
    from actions.action_log import LogAction
    from actions.action_execute import ExecuteAction
    from actions.action_github_verify import GitHubVerifyAction
    from actions.action_sleep import SleepAction
    from actions.action_metrics import MetricsAction

    with _safe_import():
        from actions.action_http import HttpAction


class _ContextHelper(object):
    _context = threading.local()

    def __getattr__(self, item):
        return getattr(self._context, item)

    def set(self, name, value):
        setattr(self._context, name, value)


class _CauseTraceback(object):
    def __init__(self):
        self.content = list()

    def write(self, data):
        self.content.append('  %s' % data)

    def __str__(self):
        return ''.join(self.content)


class Action(object):
    action_name = None
    _registered_actions = dict()

    def run(self):
        try:
            return self._run()

        except Exception as ex:
            cause = _CauseTraceback()
            traceback.print_exc(file=cause)

            raise ActionInvocationException('Failed to invoke %s.run:\n'
                                            '  Reason (%s): %s\n'
                                            'Cause:\n%s' %
                                            (type(self).__name__, type(ex).__name__, ex, cause))

    def _run(self):
        raise ActionInvocationException('%s.run not implemented' % type(self).__name__)

    def _render_with_template(self, template, **kwargs):
        template = Template(template)
        return template.render(request=request,
                               timestamp=time.time(),
                               datetime=time.ctime(),
                               context=_ContextHelper(),
                               error=self.error,
                               **kwargs)

    def error(self, message=''):
        if not message:
            message = 'The "%s" action threw an error' % self.action_name

        raise ActionInvocationException(message)

    @classmethod
    def register(cls, name, action_type):
        if name in cls._registered_actions:
            raise ConfigurationException('Action already registered: %s' % name)

        cls._registered_actions[name] = action_type

    @classmethod
    def create(cls, name, **settings):
        if name not in cls._registered_actions:
            raise ConfigurationException('Unkown action: %s (registered: %s)' %
                                         (name, cls._registered_actions.keys()))

        try:
            return cls._registered_actions[name](**settings)

        except Exception as ex:
            raise ConfigurationException('Failed to create action: %s (settings = %s)\n'
                                         '  Reason (%s): %s' %
                                         (name, settings, type(ex).__name__, ex))


def action(name):
    def invoke(cls):
        cls.action_name = name

        Action.register(name, cls)

        return cls

    return invoke


_register_available_actions()
