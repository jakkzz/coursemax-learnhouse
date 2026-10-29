"""Protect bound syllabuses before native handlers can delete files or version rows."""
from fastapi import HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlmodel import select
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.route66_ext.adapters.native_deletion import authenticate, deletion_targets, session
from src.route66_ext.db.academic_classes import AcademicClassEvent
from src.route66_ext.services.academic_rosters import serialize

_CHAPTER_ID = TypeAdapter(int)  # Match FastAPI's accepted path spellings, including "1.0".


def deletion_target(scope):
    if scope['type'] != 'http' or scope['method'] != 'DELETE':
        return None
    parts = scope['path'].rstrip('/').split('/')
    if len(parts) != 5 or parts[:3] != ['', 'api', 'v1'] or not parts[4]:
        return None
    kind, identifier = parts[3:]
    if kind == 'chapters':
        try:
            return kind, _CHAPTER_ID.validate_python(identifier)
        except ValidationError:
            return None  # Native validation returns 422.
    if kind == 'activities':
        return kind, identifier
    return None


def reorders_activities(scope):
    if scope['type'] != 'http' or scope['method'] != 'PUT':
        return False
    parts = scope['path'].rstrip('/').split('/')
    return (len(parts) == 7 and parts[:5] == ['', 'api', 'v1', 'chapters', 'course']
            and bool(parts[5]) and parts[6] == 'order')


class SyllabusRetentionMiddleware:
    def __init__(self, app, sessions=session):
        self.app, self.sessions = app, sessions

    async def __call__(self, scope, receive, send):
        target = deletion_target(scope)
        if target is None and not reorders_activities(scope):
            await self.app(scope, receive, send)
            return
        async with self.sessions() as db:
            try:
                request = Request(scope, receive)
                # Native API-token authentication may commit its usage timestamp.
                # Finish that before taking the lock; native handlers still recheck auth.
                user = await authenticate(request, db) if target else None
                # Hold the existing academic lock THROUGH the native response/commit.
                # Preparation and native reordering cannot change bindings/links after our check.
                await serialize(db)
                uuids = await deletion_targets(request, db, *target, user) if target else []
                if uuids:
                    evidence = (await db.exec(select(AcademicClassEvent.id).where(
                        AcademicClassEvent.kind == 'class_syllabus_prepared',
                        AcademicClassEvent.details['activity_uuid'].astext.in_(uuids),
                    ).limit(1))).first()
                    if evidence is not None:
                        raise HTTPException(409, 'This syllabus is linked to academic history. Edit it instead of deleting it.')
            except HTTPException as error:
                await JSONResponse({'detail': error.detail}, status_code=error.status_code,
                                   headers=error.headers)(scope, receive, send)
                return
            await self.app(scope, receive, send)
