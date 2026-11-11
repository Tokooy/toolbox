"""Serve Toolbox's synchronous routes and static resources under ASGI."""

import logging
from urllib.parse import urlsplit

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request as ASGIRequest
from starlette.responses import Response

from core import http


class ToolboxRoutes:
    def __init__(self, router, mounts):
        self.router = router
        self.mounts = mounts

    async def __call__(self, scope, receive, send):
        request = ASGIRequest(scope, receive)
        raw_path = scope.get('raw_path')
        target = raw_path.decode('latin-1') if raw_path else request.url.path
        if scope['query_string']:
            target += '?' + scope['query_string'].decode('latin-1')
        path = urlsplit(target).path
        if request.method not in {'GET', 'POST', 'HEAD'}:
            response = Response(status_code=501)
        else:
            hit = self.router.resolve(request.method, path)
            body = await request.body() if hit and request.method == 'POST' else b''
            response = await run_in_threadpool(self.dispatch, request.method, target, path, hit, body)
        await response(scope, receive, send)

    def dispatch(self, method, target, path, hit, body):
        response = None

        def respond(status, headers, content):
            nonlocal response
            response = Response(content, status_code=status, headers=headers)

        handler, params = hit or (None, {})
        request = http.Request(method, target, params, lambda: body, respond)
        try:
            if handler:
                handler(request)
            else:
                for mount in self.mounts:
                    file = mount.resolve(path)
                    if file is not None:
                        request.send_file(file)
                        break
                else:
                    request.send_error(404, 'Not Found')
        except Exception as exc:
            logging.getLogger(__name__).exception('%s %s', method, path)
            if response is None:
                request.send_error(500, str(exc))
        return response if response is not None else Response(status_code=500)
