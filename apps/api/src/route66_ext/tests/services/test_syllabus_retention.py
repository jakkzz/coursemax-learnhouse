"""Extension composition contracts; no native source edits or route replacement."""
from contextlib import asynccontextmanager
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from src.route66_ext.security.syllabus_retention import deletion_target, reorders_activities


class TargetTests(unittest.TestCase):
    def test_exact_native_routes_and_integer_spellings(self):
        for path, expected in [('/api/v1/chapters/1', ('chapters', 1)),
                               ('/api/v1/chapters/+001/', ('chapters', 1)),
                               ('/api/v1/chapters/1.0', ('chapters', 1)),
                               ('/api/v1/activities/activity_a/', ('activities', 'activity_a'))]:
            self.assertEqual(deletion_target({'type': 'http', 'method': 'DELETE', 'path': path}), expected)
        for path in ('/api/v1/chapters/no', '/api/v1/chapters/', '/api/v1/activities/activity_a/versions/1',
                     '/api/v1/courses/course_a', '/api/v1/activities/activity_a/bookmark'):
            self.assertIsNone(deletion_target({'type': 'http', 'method': 'DELETE', 'path': path}))
        self.assertIsNone(deletion_target({'type': 'lifespan'}))
        self.assertIsNone(deletion_target({'type': 'http', 'method': 'GET', 'path': '/api/v1/chapters/1'}))

    def test_only_reordering_needs_the_additional_shared_link_lock(self):
        path = '/api/v1/chapters/course/course_a/order'
        self.assertTrue(reorders_activities({'type': 'http', 'method': 'PUT', 'path': path}))
        self.assertTrue(reorders_activities({'type': 'http', 'method': 'PUT', 'path': path + '/'}))
        self.assertFalse(reorders_activities({'type': 'http', 'method': 'GET', 'path': path}))
        self.assertFalse(reorders_activities({'type': 'http', 'method': 'PUT', 'path': '/api/v1/chapters/1'}))
        self.assertFalse(reorders_activities({'type': 'websocket'}))


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_auth_commits_cannot_release_the_guard_lock(self):
        from starlette.responses import Response
        from src.route66_ext.security.syllabus_retention import SyllabusRetentionMiddleware
        order = []

        @asynccontextmanager
        async def session():
            try:
                yield object()
            finally:
                order.append('release')

        async def authenticate(*args):
            order.append('auth commit')
            return object()

        async def lock(*args):
            order.append('lock')

        async def native(scope, receive, send):
            order.append('native')
            await Response(status_code=204)(scope, receive, send)

        app = SyllabusRetentionMiddleware(native, sessions=session)
        with patch('src.route66_ext.security.syllabus_retention.authenticate', new=authenticate), \
             patch('src.route66_ext.security.syllabus_retention.serialize', new=lock), \
             patch('src.route66_ext.security.syllabus_retention.deletion_targets', new=AsyncMock(return_value=[])):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://learn.example.com') as client:
                self.assertEqual((await client.delete('/api/v1/chapters/1')).status_code, 204)
        self.assertEqual(order, ['auth commit', 'lock', 'native', 'release'])

    async def test_factory_retains_native_routes_lifespan_and_http_behavior(self):
        from app import app as native
        from src.route66_ext.adapters.application import create_app
        original_middlewares, original_stack = list(native.user_middleware), native.middleware_stack
        routes, lifespan = list(native.routes), native.router.lifespan_context
        try:
            app = create_app()
            self.assertIs(app, native)
            self.assertEqual(app.routes, routes)
            self.assertIs(app.router.lifespan_context, lifespan)
            self.assertEqual([m.cls.__name__ for m in app.user_middleware[:3]],
                             ['CORSMiddleware', 'CSRFProtectionMiddleware', 'SyllabusRetentionMiddleware'])
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://learn.example.com') as client:
                response = await client.get('/')
                self.assertEqual(response.status_code, 200)
                response = await client.options('/api/v1/chapters/1', headers={
                    'Origin': 'https://learn.example.com', 'Access-Control-Request-Method': 'DELETE'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['access-control-allow-origin'], 'https://learn.example.com')
        finally:
            native.user_middleware[:] = original_middlewares
            native.middleware_stack = original_stack

    def test_api_launcher_uses_factory_and_native_port(self):
        from config.config import get_learnhouse_config
        from src.route66_ext.adapters.application import run_api
        with patch('uvicorn.run') as run:
            run_api()
        config = get_learnhouse_config()
        run.assert_called_once_with('src.route66_ext.adapters.application:create_app', factory=True,
                                    host='0.0.0.0', port=config.hosting_config.port,
                                    reload=config.general_config.development_mode)

    def test_container_launcher_keeps_native_services(self):
        script = Path(__file__).resolve().parents[2] / 'start.sh'
        subprocess.run(['sh', '-n', str(script)], check=True)
        commands = script.read_text()
        self.assertIn('pm2 start uv --cwd /app/api --name learnhouse-api -- run python -m src.route66_ext', commands)
        self.assertIn('pm2 start server-wrapper.js --cwd /app/web --name learnhouse-web', commands)
        self.assertIn('pm2 start node --cwd /app/collab --name learnhouse-collab -- dist/index.js', commands)
        self.assertIn("nginx -g 'daemon off;'", commands)
        self.assertIn('exec pm2 logs --raw', commands)
