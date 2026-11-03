"""Run only against the disposable test schema, using exact retained-parent source."""
import asyncio, json, os, re, sys
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import Response
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.route66_ext.db.academic_classes import AcademicClassEvent
from src.route66_ext.adapters.db_users import User
from src.route66_ext.routers import academic_classes as api
assert os.environ['IDENTITY_TEST_PG_SOCKET'] == '/scratch'
assert re.fullmatch(r'identity_test_[0-9a-f]{32}', sys.argv[1])
assert AcademicClassEvent.model_fields['actor_user_id'].annotation is int
async def main():
 engine=create_async_engine('postgresql+asyncpg://fixture@/fixture', connect_args={'host':'/scratch','server_settings':{'search_path':sys.argv[1]}})
 sessions=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
 try:
  async with sessions() as db:
   records=(await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.actor_user_id.is_(None)))).all()
   assert records and all(e.details['origin']=='scheduled' for e in records)
   user=await db.get(User,2)
   async def context(*args): return user,SimpleNamespace(org_id=1),None
   with patch.object(api,'context',context): result=await api.roster(20,None,Response(),db)
   assert any(e['details'].get('origin')=='scheduled' for e in result['events'])
  print(json.dumps({'parent_actor_annotation':'required int','scheduled_history_readable':True,'manager_roster_readable':True}))
 finally: await engine.dispose()
asyncio.run(main())
