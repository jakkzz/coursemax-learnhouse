"""Isolated PostgreSQL + actual HTTP LINE/LIFF lifecycle, no live provider calls."""
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime,timezone
import asyncio
import hashlib
import os
import time
import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs,urlsplit
from unittest.mock import AsyncMock,patch
import httpx
from fastapi import FastAPI,HTTPException
from sqlmodel import select
from src.route66_ext.db.provider_identity import ProviderIdentity
from src.db.users import User
from src.security.auth import create_access_token,decode_jwt,decode_refresh_token,get_current_user
from src.route66_ext.security.provider_session import resolve_provider_session, carried_claims
from src.route66_ext.services.auth.line_config import LineSettings
from src.route66_ext.services.auth.line_handoff import LineHandoffConfig, LINE_TOKEN_URL
from src.route66_ext.services.auth.native_line import retire_line_identity
from src.route66_ext.services.auth.oauth_transactions import OAuthClient, OAuthTransactions
from src.route66_ext.services.auth.provider_proof import LINE_VERIFY_URL
from src.route66_ext.tests.services.test_native_google_sessions import NativeGoogleTests, request
from src.route66_ext.tests.services.test_google_handoff import Store

class NativeLineTests(NativeGoogleTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.env=patch.dict(os.environ,{'LEARNHOUSE_LINE_SUBJECT_LOGIN_ENABLED':'true',
            'LEARNHOUSE_LINE_PROVIDER_ID':'123456789','LEARNHOUSE_LINE_LIFF_ENABLED':'true'})
        self.env.start()
        self.line_policy=patch('src.route66_ext.services.auth.native_line.enforce_login_auth_method',new=AsyncMock())
        self.line_policy.start()
        self.line=replace(self.line,namespace='123456789')
        await self.link()
        _,session=await self.login()
        self.google_token=session.access_token
        self.config=LineSettings(LineHandoffConfig(OAuthClient('line','1234567890',
            'https://learn.example.com','123456789'),'x'*32),1,'line-test',b'y'*32,'1234567890-fixture')
        self.provider_requests=[];self.used={};self.store=Store();self.nonce=None;self.claim_changes={}

    async def asyncTearDown(self):
        self.line_policy.stop()
        self.env.stop()
        await super().asyncTearDown()

    @asynccontextmanager
    async def line_http(self,google=True):
        from src.core.events.database import get_db_session
        from src.route66_ext.routers import line_subject_auth as route
        from src.routers.auth import router as auth_router
        from src.routers.mfa import router as mfa_router
        real_client=httpx.AsyncClient
        async def provider(req):
            self.provider_requests.append(str(req.url))
            self.assertNotIn('authorization',req.headers);self.assertNotIn('cookie',req.headers)
            data=parse_qs(req.content.decode())
            if str(req.url)==LINE_TOKEN_URL:
                self.assertEqual(data['redirect_uri'],[self.config.handoff.client.callback_uri])
                self.assertIn('code_verifier',data)
                return httpx.Response(200,json={'id_token':'fixture-line-token','access_token':'never-line-access'})
            self.assertEqual(str(req.url),LINE_VERIFY_URL)
            now=int(time.time())
            claims={'iss':'https://access.line.me','aud':'1234567890','sub':self.line.subject,
                'iat':now-1,'exp':now+120,'nonce':self.nonce,'email':'not-verified@example.com'}
            claims.update(self.claim_changes)
            return httpx.Response(200,json=claims)
        async def set_once(key,value,*,nx=False,ex=None):
            if nx and key in self.used:return False
            self.used[key]=value;return True
        @asynccontextmanager
        async def resources(config):
            yield SimpleNamespace(eval=AsyncMock(return_value=1),set=set_once),OAuthTransactions(
                self.store,deployment=config.deployment,secret=config.secret)
        async def database():
            async with self.sessions() as db:yield db
        app=FastAPI();app.include_router(route.router,prefix='/auth/line')
        app.include_router(auth_router,prefix='/auth');app.include_router(mfa_router,prefix='/auth/mfa')
        app.dependency_overrides[get_db_session]=database
        with patch('src.routers.auth.check_refresh_rate_limit',return_value=(True,0)),patch.object(route,'line_settings',return_value=self.config),patch.object(route,'resources',resources),patch.object(route,'httpx',SimpleNamespace(AsyncClient=lambda **kw:real_client(transport=httpx.MockTransport(provider)))):
            async with real_client(transport=httpx.ASGITransport(app=app),base_url='https://learn.example.com',
                                  headers={'Origin':'https://learn.example.com'}) as client:
                if google:client.cookies.set('LH_access',self.google_token)
                yield client

    async def start_line(self,client,intent):
        response=await client.post('/auth/line/start',json={'intent':intent,'return_path':'/home'})
        self.assertEqual(response.status_code,200,response.text)
        params=parse_qs(urlsplit(response.json()['url']).query)
        self.assertEqual(params['redirect_uri'],['https://learn.example.com/auth/callback/line'])
        self.nonce=params['nonce'][0]
        return {'state':params['state'][0],'intent':intent,'code':'fixture-code'}

    async def link_line(self,client):
        body=await self.start_line(client,'link')
        response=await client.post('/auth/line/complete',json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json(),{'linked':True,'return_path':'/home'})
        self.assertEqual(decode_jwt(client.cookies.get('LH_access'))['amr'],'google')
        async with self.sessions() as db:
            row=(await db.exec(select(ProviderIdentity).where(ProviderIdentity.provider=='line'))).first()
            return row.id

    async def test_line_link_then_linked_signin_native_subject_and_email_preserved(self):
        async with self.line_http() as client:
            await self.link_line(client);client.cookies.clear()
            body=await self.start_line(client,'signin');res=await client.post('/auth/line/complete',json=body)
            self.assertEqual(res.status_code,200,res.text)
            self.assertNotIn('never-line-access',res.text)
            payload=decode_jwt(res.json()['tokens']['access_token'])
            self.assertEqual(payload['sub'],'lh:user:1');self.assertEqual(payload['amr'],'line')
            async with self.sessions() as db:
                user=await get_current_user(request(res.json()['tokens']['access_token']),db)
                self.assertEqual(user.email,'fixture1@example.com')
            original_auth_time=payload['lh_auth_time']
            refreshed=await client.get('/auth/refresh')
            self.assertEqual(refreshed.status_code,200,refreshed.text)
            new_payload=decode_jwt(refreshed.json()['access_token'])
            self.assertEqual(new_payload['amr'],'line')
            self.assertEqual(new_payload['lh_auth_time'],original_auth_time)
            logged_out=await client.delete('/auth/logout')
            self.assertEqual(logged_out.status_code,200,logged_out.text)
            async with self.sessions() as db:
                with self.assertRaises(HTTPException):await get_current_user(request(refreshed.json()['access_token']),db)
        self.assertEqual(tuple(await self.counts()),(2,2,3))

    async def test_line_mfa_completion_preserves_binding_and_is_one_use(self):
        from fastapi import Response
        from src.routers.mfa import api_login_mfa, MFALoginRequest
        from src.route66_ext.services.auth.native_line import complete_native_line
        from src.route66_ext.services.auth.line_handoff import VerifiedLineHandoff
        async with self.line_http() as client:await self.link_line(client)
        with patch('src.services.auth.session.is_mfa_active',new=AsyncMock(return_value=True)):
            async with self.sessions.begin() as db:
                _,pending=await complete_native_line(db,VerifiedLineHandoff(self.line,'signin','/home'),org_id=1,namespace=self.line.namespace)
        before=decode_jwt(pending.mfa_token)
        with patch('src.routers.mfa._check_mfa_rate_limit'),patch('src.routers.mfa.get_user_mfa',new=AsyncMock(return_value=SimpleNamespace(confirmed_at='yes'))),patch('src.routers.mfa.consume_backup_code',new=AsyncMock(return_value=True)),patch('src.routers.mfa.count_unused_backup_codes',new=AsyncMock(return_value=3)):
            async with self.sessions() as db:
                result=await api_login_mfa(request(),Response(),MFALoginRequest(mfa_token=pending.mfa_token,code='fixture-backup',is_backup_code=True),db)
        after=decode_jwt(result['tokens']['access_token'])
        self.assertEqual(after['amr'],'line');self.assertEqual(after['sub'],'lh:user:1')
        self.assertEqual(after['lh_identity'],before['lh_identity'])
        self.assertEqual(after['lh_auth_time'],before['lh_auth_time'])
        from src.route66_ext.security.provider_session import consume_mfa_challenge
        with self.assertRaises(HTTPException):consume_mfa_challenge(before)

    async def test_line_unknown_never_creates_account_or_changes_email(self):
        before=await self.counts()
        async with self.line_http(google=False) as client:
            body=await self.start_line(client,'signin');res=await client.post('/auth/line/complete',json=body)
            self.assertEqual(res.status_code,409);self.assertIn('line_link_required',res.text)
        self.assertEqual(await self.counts(),before)

    async def test_line_public_signup_extra_actor_and_origin_denied(self):
        async with self.line_http() as client:
            self.assertEqual((await client.post('/auth/line/start',json={'intent':'register'})).status_code,422)
            self.assertEqual((await client.post('/auth/line/start',json={'intent':'link','actor_user_id':2})).status_code,422)
            self.assertEqual((await client.post('/auth/line/start',json={'intent':'signin'},headers={'Origin':'https://evil.example'})).status_code,403)

    async def test_line_cancel_replay_no_provider_or_identity_mutation(self):
        before=await self.counts()
        async with self.line_http() as client:
            body=await self.start_line(client,'link')
            res=await client.post('/auth/line/complete',json={**body,'code':None,'provider_error':'access_denied'})
            self.assertEqual(res.status_code,409)
            self.assertEqual((await client.post('/auth/line/complete',json=body)).status_code,409)
        self.assertEqual(self.provider_requests,[]);self.assertEqual(await self.counts(),before)

    async def test_line_actor_session_change_does_not_link_other_account(self):
        async with self.line_http() as client:
            body=await self.start_line(client,'link')
            client.cookies.clear();client.cookies.set('LH_access',create_access_token({**decode_jwt(self.google_token),'iat':time.time()-0.1}))
            self.assertEqual((await client.post('/auth/line/complete',json=body)).status_code,409)
        self.assertEqual(self.provider_requests,[])

    async def test_line_stale_google_auth_not_refreshed_by_new_issuance_time(self):
        old={**decode_jwt(self.google_token),'lh_auth_time':time.time()-1000,'iat':time.time()}
        self.assertEqual(carried_claims(old)['lh_auth_time'],old['lh_auth_time'])
        async with self.line_http(google=False) as client:
            client.cookies.set('LH_access',create_access_token(old))
            self.assertEqual((await client.post('/auth/line/start',json={'intent':'link'})).status_code,401)

    async def test_line_identity_collision_leaves_both_owners_unchanged(self):
        async with self.line_http() as client:await self.link_line(client)
        from src.route66_ext.services.auth.provider_identities import link_existing_identity
        async with self.sessions.begin() as db:
            await link_existing_identity(db,actor_user_id=2,proof=replace(self.google,subject='fixture-owner-2'))
        _,other=await self.login(replace(self.google,subject='fixture-owner-2'))
        async with self.line_http(google=False) as client:
            client.cookies.set('LH_access',other.access_token)
            body=await self.start_line(client,'link');res=await client.post('/auth/line/complete',json=body)
            self.assertEqual(res.status_code,409);self.assertIn('identity_already_owned',res.text)
        self.assertEqual(tuple(await self.counts()),(3,3,3))

    async def test_line_wrong_nonce_and_audience_fail_before_binding(self):
        for changes in ({'nonce':'wrong'},{'aud':'wrong'},{'exp':int(time.time())-1}):
            self.claim_changes=changes
            async with self.line_http() as client:
                body=await self.start_line(client,'link')
                self.assertEqual((await client.post('/auth/line/complete',json=body)).status_code,409)
        self.assertEqual(tuple(await self.counts()),(1,1,3))

    async def test_line_unlink_revokes_access_refresh_pending_mfa_and_reserves_subject(self):
        async with self.line_http() as client:
            ident=await self.link_line(client)
        from src.route66_ext.services.auth.native_line import complete_native_line
        from src.route66_ext.services.auth.line_handoff import VerifiedLineHandoff
        async with self.sessions.begin() as db:
            _,session=await complete_native_line(db,VerifiedLineHandoff(self.line,'signin','/home'),org_id=1,namespace=self.line.namespace)
        with patch('src.services.auth.session.is_mfa_active',new=AsyncMock(return_value=True)):
            async with self.sessions.begin() as db:
                _,pending=await complete_native_line(db,VerifiedLineHandoff(self.line,'signin','/home'),org_id=1,namespace=self.line.namespace)
        async with self.line_http() as client:
            self.assertEqual((await client.post('/auth/line/unlink',json={'expected_identity_id':ident,'confirm_remove':False})).status_code,400)
            res=await client.post('/auth/line/unlink',json={'expected_identity_id':ident,'confirm_remove':True})
            self.assertEqual(res.status_code,200,res.text)
            body=await self.start_line(client,'link')
            self.assertEqual((await client.post('/auth/line/complete',json=body)).status_code,409)
        for token,payload in ((session.access_token,decode_jwt(session.access_token)),(session.refresh_token,decode_refresh_token(session.refresh_token)),(pending.mfa_token,decode_jwt(pending.mfa_token))):
            async with self.sessions() as db:
                with self.assertRaises(HTTPException):await resolve_provider_session(db,payload)
        async with self.sessions() as db:
            self.assertEqual((await get_current_user(request(self.google_token),db)).id,1)

    async def test_line_account_status_private_and_google_confirmation_required(self):
        async with self.line_http() as client:
            ident=await self.link_line(client)
            response=await client.get('/auth/line/account')
            self.assertEqual(response.json(),{'linked':True,'identity_id':ident,'can_manage':True})
            self.assertEqual(response.headers['cache-control'],'private, no-store')
            self.assertNotIn(self.line.subject,response.text)
            old={**decode_jwt(self.google_token),'lh_auth_time':time.time()-1000}
            client.cookies.clear();client.cookies.set('LH_access',create_access_token(old))
            self.assertFalse((await client.get('/auth/line/account')).json()['can_manage'])

    async def test_liff_conflicting_browser_account_cannot_switch_silently(self):
        async with self.line_http() as client:await self.link_line(client)
        from src.route66_ext.services.auth.provider_identities import link_existing_identity
        async with self.sessions.begin() as db:
            await link_existing_identity(db,actor_user_id=2,proof=replace(self.google,subject='fixture-owner-2'))
        _,other=await self.login(replace(self.google,subject='fixture-owner-2'))
        async with self.line_http(google=False) as client:
            client.cookies.set('LH_access',other.access_token)
            start=await client.post('/auth/line/liff/start')
            res=await client.post('/auth/line/liff/session',json={'state':start.json()['state'],'id_token':'liff-switch-fixture'})
            self.assertEqual(res.status_code,409,res.text)
            self.assertEqual(client.cookies.get('LH_access'),other.access_token)
            self.assertFalse(self.used)

    async def test_line_disabled_namespace_lock_membership_and_global_revocation_deny(self):
        async with self.line_http() as client:await self.link_line(client)
        from src.route66_ext.services.auth.native_line import complete_native_line
        from src.route66_ext.services.auth.line_handoff import VerifiedLineHandoff
        async with self.sessions.begin() as db:
            _,session=await complete_native_line(db,VerifiedLineHandoff(self.line,'signin','/home'),org_id=1,namespace=self.line.namespace)
        for env in ({'LEARNHOUSE_LINE_SUBJECT_LOGIN_ENABLED':'false'},{'LEARNHOUSE_LINE_PROVIDER_ID':'other'}):
            with patch.dict(os.environ,env):
                async with self.sessions() as db:
                    with self.assertRaises(HTTPException):await get_current_user(request(session.access_token),db)
        from src.db.user_organizations import UserOrganization
        async with self.sessions.begin() as db:
            user=await db.get(User,1)
            user.locked_until=datetime.fromtimestamp(time.time()+300,timezone.utc).isoformat()
            db.add(user)
        async with self.sessions() as db:
            with self.assertRaises(HTTPException):await get_current_user(request(session.access_token),db)
        async with self.sessions.begin() as db:
            user=await db.get(User,1);user.locked_until=None;db.add(user)
            membership=(await db.exec(select(UserOrganization).where(UserOrganization.user_id==1))).first()
            await db.delete(membership)
        async with self.sessions() as db:
            with self.assertRaises(HTTPException):await get_current_user(request(session.access_token),db)
        async with self.sessions.begin() as db:
            db.add(UserOrganization(user_id=1,org_id=1,role_id=4,creation_date='fixture',update_date='fixture'))
        self.redis.data['jwt_revoked_before:1']=str(time.time()+1)
        async with self.sessions() as db:
            with self.assertRaises(HTTPException):await get_current_user(request(session.access_token),db)

    async def test_liff_server_verification_challenge_and_token_replay(self):
        async with self.line_http() as client:await self.link_line(client)
        async with self.line_http(google=False) as client:
            started=await client.post('/auth/line/liff/start')
            self.assertEqual(started.status_code,200,started.text)
            body={'state':started.json()['state'],'id_token':'liff-fixture-id-token'}
            res=await client.post('/auth/line/liff/session',json=body)
            self.assertEqual(res.status_code,200,res.text)
            self.assertEqual(decode_jwt(res.json()['tokens']['access_token'])['amr'],'line')
            self.assertEqual((await client.post('/auth/line/liff/session',json=body)).status_code,409)
            client.cookies.clear()
            fresh=await client.post('/auth/line/liff/start')
            res=await client.post('/auth/line/liff/session',json={**body,'state':fresh.json()['state']})
            self.assertEqual(res.status_code,401,res.text)

    async def test_liff_oauth_state_not_accepted_and_unknown_user_not_created(self):
        before=await self.counts()
        async with self.line_http(google=False) as client:
            oauth=await self.start_line(client,'signin')
            res=await client.post('/auth/line/liff/session',json={'state':oauth['state'],'id_token':'liff-fixture'})
            self.assertEqual(res.status_code,409)
            fresh=await client.post('/auth/line/liff/start')
            res=await client.post('/auth/line/liff/session',json={'state':fresh.json()['state'],'id_token':'liff-fixture'})
            self.assertEqual(res.status_code,409)
        self.assertEqual(await self.counts(),before)

    async def test_liff_continuation_survives_login_existing_session_and_mfa(self):
        destination='/attendance/check-in?handoff='+'a'*43
        async with self.line_http() as client:await self.link_line(client)
        async with self.line_http(google=False) as client:
            started=await client.post('/auth/line/liff/start',json={'return_path':destination})
            response=await client.post('/auth/line/liff/session',json={'state':started.json()['state'],'id_token':'synthetic-continuation-token'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['return_path'],destination)
            started=await client.post('/auth/line/liff/start',json={'return_path':destination})
            repeated=await client.post('/auth/line/liff/session',json={'state':started.json()['state'],'id_token':'synthetic-continuation-token'})
            self.assertEqual(repeated.json(),{'existing_session':True,'return_path':destination})
        with patch('src.services.auth.session.is_mfa_active',new=AsyncMock(return_value=True)):
            async with self.line_http(google=False) as client:
                started=await client.post('/auth/line/liff/start',json={'return_path':destination})
                response=await client.post('/auth/line/liff/session',json={'state':started.json()['state'],'id_token':'synthetic-continuation-mfa'})
                self.assertTrue(response.json()['mfa_required'])
                self.assertEqual(response.json()['return_path'],destination)
                self.assertNotIn('LH_access',client.cookies)
        async with self.line_http(google=False) as client:
            for path in ('https://foreign.example/','//foreign.example/','/attendance/check-in#raw'):
                self.assertEqual((await client.post('/auth/line/liff/start',json={'return_path':path})).status_code,400)

    async def test_liff_pending_mfa_does_not_set_access_cookie(self):
        async with self.line_http() as client:await self.link_line(client)
        with patch('src.services.auth.session.is_mfa_active',new=AsyncMock(return_value=True)):
            async with self.line_http(google=False) as client:
                start=await client.post('/auth/line/liff/start')
                res=await client.post('/auth/line/liff/session',json={'state':start.json()['state'],'id_token':'liff-mfa-fixture'})
                self.assertEqual(res.status_code,200,res.text);self.assertTrue(res.json()['mfa_required'])
                self.assertNotIn('LH_access',client.cookies)
                payload=decode_jwt(res.json()['mfa_token'])
                self.assertEqual(payload['amr'],'line');self.assertEqual(payload['purpose'],'mfa_pending')


def load_tests(loader,tests,pattern):
    # Reuse native fixtures without counting inherited Google cases twice.
    names=[name for name in loader.getTestCaseNames(NativeLineTests) if name in NativeLineTests.__dict__ and name.startswith(('test_line_','test_liff_'))]
    return unittest.TestSuite(NativeLineTests(name) for name in names)

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
