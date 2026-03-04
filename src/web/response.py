"""HTTP response helpers with a stable envelope."""

from aiohttp import web

from ..application.errors import AppError, InternalServerError


def success(payload=None, status=200):
    if payload is None:
        body = {'ok': True, 'data': None}
    elif isinstance(payload, dict):
        body = {'ok': True, **payload}
    else:
        body = {'ok': True, 'data': payload}
    return web.json_response(body, status=status)


def error(exc, status=None):
    if not isinstance(exc, AppError):
        exc = InternalServerError(str(exc))

    body = {
        'ok': False,
        'error': {
            'code': exc.code,
            'message': exc.message,
        },
    }
    return web.json_response(body, status=status or exc.http_status)
