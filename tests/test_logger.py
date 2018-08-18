import datetime
import logging

from gunicorn.config import Config
from gunicorn.glogging import Logger, add_instrumentation
from gunicorn.six import StringIO

from support import SimpleNamespace


def test_atoms_defaults():
    response = SimpleNamespace(
        status='200', response_length=1024,
        headers=(('Content-Type', 'application/json'),), sent=1024,
    )
    request = SimpleNamespace(headers=(('Accept', 'application/json'),))
    environ = {
        'REQUEST_METHOD': 'GET', 'RAW_URI': '/my/path?foo=bar',
        'PATH_INFO': '/my/path', 'QUERY_STRING': 'foo=bar',
        'SERVER_PROTOCOL': 'HTTP/1.1',
    }
    logger = Logger(Config())
    atoms = logger.atoms(response, request, environ, datetime.timedelta(seconds=1))
    assert isinstance(atoms, dict)
    assert atoms['r'] == 'GET /my/path?foo=bar HTTP/1.1'
    assert atoms['m'] == 'GET'
    assert atoms['U'] == '/my/path'
    assert atoms['q'] == 'foo=bar'
    assert atoms['H'] == 'HTTP/1.1'
    assert atoms['b'] == '1024'
    assert atoms['B'] == 1024
    assert atoms['{accept}i'] == 'application/json'
    assert atoms['{content-type}o'] == 'application/json'


def test_get_username_from_basic_auth_header():
    request = SimpleNamespace(headers=())
    response = SimpleNamespace(
        status='200', response_length=1024, sent=1024,
        headers=(('Content-Type', 'text/plain'),),
    )
    environ = {
        'REQUEST_METHOD': 'GET', 'RAW_URI': '/my/path?foo=bar',
        'PATH_INFO': '/my/path', 'QUERY_STRING': 'foo=bar',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'HTTP_AUTHORIZATION': 'Basic YnJrMHY6',
    }
    logger = Logger(Config())
    atoms = logger.atoms(response, request, environ, datetime.timedelta(seconds=1))
    assert atoms['u'] == 'brk0v'


class ConfigMock(Config):
    def __init__(self, sio):
        Config.__init__(self)
        self.sio = sio

    @property
    def instrumentation_classes(self):
        return [InstrumentationMock]


class InstrumentationMock(object):
    def __init__(self, cfg):
        self.cfg = cfg
        self.sio = cfg.sio

    def info(self, *args, **kwargs):
        self.sio.write('instrumentation-info-called')

    def critical(self):
        self.sio.write('instrumentation-critical-called')

    def error(self, *args, **kwargs):
        raise Exception('instrumentation-raised-exception')


def test_add_inst_methods():
    sio = StringIO()
    c = ConfigMock(sio)
    logger = Logger(c)
    add_instrumentation(logger, c)

    logger.error_log.addHandler(logging.StreamHandler(sio))

    log_msg = 'logger-info-called'
    logger.info(log_msg, extra={})
    inst_msg = 'instrumentation-info-called'
    assert log_msg in sio.getvalue()
    assert inst_msg in sio.getvalue()

    # TypeError should be caught and logged by logger
    log_msg = 'logger-critical-called'
    logger.critical(log_msg)
    mismatch_msg = 'Error: Argument mismatch between logger and instrumentation'
    assert log_msg in sio.getvalue()
    assert mismatch_msg in sio.getvalue()

    # Any other exception from instrumentation should be caught and logged by logger
    log_msg = 'logger-error-called'
    logger.error(log_msg)
    exception_msg = 'Error in instrumentation: instrumentation-raised-exception'
    print(sio.getvalue())
    assert log_msg in sio.getvalue()
    assert exception_msg in sio.getvalue()
