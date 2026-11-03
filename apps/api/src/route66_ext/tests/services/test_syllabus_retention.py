"""Owned transaction-hook and launcher contracts; no route replacement."""
from pathlib import Path
import subprocess
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from src.route66_ext.security import syllabus_retention as guard


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_guard_uses_the_writer_session_without_committing(self):
        db = AsyncMock()
        order = []

        async def lock(session):
            self.assertIs(session, db)
            order.append('lock')

        async def targets(request, session, kind, identifier, user):
            self.assertIs(session, db)
            order.append('targets')
            return []

        with patch.object(guard, 'serialize', lock), patch.object(guard, 'deletion_targets', targets):
            await guard.protect_deletion(None, db, 'chapters', 1, None)
        self.assertEqual(order, ['lock', 'targets'])
        db.commit.assert_not_awaited()
        db.close.assert_not_awaited()

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
            self.assertEqual([m.cls.__name__ for m in app.user_middleware[:2]],
                             ['CORSMiddleware', 'CSRFProtectionMiddleware'])
            self.assertNotIn('SyllabusRetentionMiddleware', [m.cls.__name__ for m in app.user_middleware])
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
