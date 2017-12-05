from __future__ import print_function

import re
import threading
import traceback

import six
from flask import request

from actions import Action
from util import ConfigurationException


class Endpoint(object):
    current = None

    def __init__(self, route, settings, action_metrics):
        if not route:
            raise ConfigurationException('An endpoint must have its route defined')

        if settings is None:
            settings = dict()

        self._route = route
        self._method = settings.get('method', 'POST')
        self._async = settings.get('async', False)
        self._headers = settings.get('headers', dict())
        self._body = settings.get('body', dict())

        with Endpoint.on_setup(self):
            self._actions = list(Action.create(name, **(action_settings if action_settings else dict()))
                                 for action_item in settings.get('actions', list())
                                 for name, action_settings in action_item.items())

        self._action_metrics = action_metrics

    @property
    def route(self):
        return self._route

    @property
    def method(self):
        return self._method

    @property
    def async(self):
        return self._async

    @property
    def headers(self):
        return dict(self._headers)

    @property
    def body(self):
        return dict(self._body)

    @classmethod
    def on_setup(cls, endpoint):
        class EndpointSetupContext(object):
            def __enter__(self):
                cls.current = endpoint

            def __exit__(self, *args, **kwargs):
                cls.current = None

        return EndpointSetupContext()

    def setup(self, app):
        @app.route(self._route, endpoint=self._route[1:], methods=[self._method])
        def receive():
            if not request.json:
                if self._body:
                    return self._make_response(400, 'No payload')

            if not self.accept():
                return self._make_response(409, 'Invalid payload')

            if self._async:
                args = (app, request.environ.copy(), request.json)

                threading.Thread(target=self._safe_run_actions, args=args).start()

            else:
                try:
                    self._run_actions()

                except Exception:
                    traceback.print_exc()
                    return self._make_response(500, 'Internal Server Error')

            return self._make_response(200, 'OK\n')

    def _run_actions(self):
        for idx, action in enumerate(self._actions):
            labels = (self._route, self._method, action.action_name, idx)

            with self._action_metrics.labels(*labels).time():
                action.run()

    def _safe_run_actions(self, app, request_environment, json):
        with app.request_context(request_environment):
            # reassigning the JSON body of the request on a different thread
            setattr(request, '_cached_json', json)

            try:
                self._run_actions()

            except Exception:
                traceback.print_exc()

    @staticmethod
    def _make_response(status, message):
        return message, status, {'Content-Type': 'text/plain'}

    def accept(self):
        return self._accept_headers(request.headers, self._headers) and self._accept_body(request.json, self._body)

    @staticmethod
    def _accept_headers(headers, rules):
        for key, rule in rules.items():
            value = headers.get(key, '')

            if not re.match(rule, value):
                print('Failed to validate the "%s" header: "%s" does not match "%s"' %
                      (key, value, rule))
                return False

        return True

    def _accept_body(self, data, rules, prefix=''):
        for key, rule in rules.items():
            value = data.get(key, dict() if isinstance(rule, dict) else '')

            if isinstance(value, list):
                for idx, item in enumerate(value):
                    if not self._check_body(item, rule, '%s.%s[%d]' % (prefix, key, idx)):
                        return False

            else:
                if not self._check_body(value, rule, '%s.%s' % (prefix, key)):
                    return False

        return True

    def _check_body(self, value, rule, property_path):
        if isinstance(rule, dict) and isinstance(value, dict):
            if not self._accept_body(value, rule, property_path):
                return False

        elif not isinstance(rule, six.string_types) or not re.match(rule, str(value)):
            print('Failed to validate "%s": "%s" does not match "%s"' %
                  (property_path[1:], value, rule))
            return False

        return True
