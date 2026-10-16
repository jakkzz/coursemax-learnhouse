"""Explicit extension registration, no network calls or schema migration on import."""
from fastapi import APIRouter


def register_models():
    # Native src/db shims also import these modules. Python imports each model
    # definition once, preserving SQLModel table identity and guard listeners.
    from .db import academic_classes, class_attendance, provider_identity, provider_profile_import, school_calendar, school_identity
    return (academic_classes, class_attendance, provider_identity, provider_profile_import, school_calendar, school_identity)


def build_router():
    register_models()
    from .routers import academic_classes, class_attendance, google_subject_auth, line_subject_auth, school_calendars, school_identity
    router = APIRouter()
    router.include_router(school_identity.router, prefix='/school-identity', tags=['school-identity'])
    router.include_router(academic_classes.router, prefix='/academic-classes', tags=['academic-classes'])
    router.include_router(class_attendance.router, prefix='/attendance', tags=['attendance'])
    router.include_router(school_calendars.router, prefix='/school-calendars', tags=['school-calendars'])
    router.include_router(google_subject_auth.router, prefix='/auth/google', tags=['auth'])
    router.include_router(line_subject_auth.router, prefix='/auth/line', tags=['auth'])
    return router
