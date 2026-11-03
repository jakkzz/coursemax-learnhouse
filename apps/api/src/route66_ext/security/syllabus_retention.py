"""Protect bound syllabuses inside the native writer's existing transaction."""
from fastapi import HTTPException
from sqlmodel import select

from src.route66_ext.adapters.native_deletion import deletion_targets
from src.route66_ext.db.academic_classes import AcademicClassEvent
from src.route66_ext.services.academic_rosters import serialize


async def protect_deletion(request, db, kind, identifier, user):
    # Native permission checks precede this hook. Re-read links under the same
    # lock as syllabus preparation/reordering, and hold it until the writer commits.
    await serialize(db)
    uuids = await deletion_targets(request, db, kind, identifier, user)
    if uuids:
        evidence = (await db.exec(select(AcademicClassEvent.id).where(
            AcademicClassEvent.kind == 'class_syllabus_prepared',
            AcademicClassEvent.details['activity_uuid'].as_string().in_(uuids),
        ).limit(1))).first()
        if evidence is not None:
            raise HTTPException(409, 'This syllabus is linked to academic history. Edit it instead of deleting it.')
