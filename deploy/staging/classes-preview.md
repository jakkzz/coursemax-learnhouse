# Classes and school identity — synthetic UI preview

## Scope

Admin-hosted `/dash/classes-preview`, discovered beside Courses in the native desktop dashboard and mobile menu. Existing session/dashboard gates remain, with organization-management gating for this design preview. Preview role selection is an in-memory demonstration, not native authorization. Fixtures are synthetic and public-source-safe; page actions make no API writes, send no messages and grant no real identities, roles, course assignments or enrollment.

Owner-approved direction: student and teacher school mappings; administrators resolve disputes, teachers flag issues; teachers see every section of an explicitly assigned course. Final institutional UI locations remain `/classes`, section Students, Users > School identities and Account > School identity. This preview does not implement those authorities or relax native dashboard access for teachers.

## Tasks

- Teacher: grouped courses → either assigned section → roster search/link/membership filters → flag a discrepancy without changing membership or linkage.
- Administrator: inspect student/teacher review queue, verify exact demo evidence, provide reason/confirmation and simulate a decision. Conflicting evidence cannot be approved; requests for more evidence remain pending.
- Student/teacher: inspect own school record, try explicitly synthetic evidence, confirm ownership and observe pending/approved demo state.
- English/Thai, 1440/390 task layouts, empty/loading/unavailable/retry and read-only/manual/withdrawn cases.

State survives navigation within the preview and resets on reload. This is not durable institutional audit storage. School verification method, delegated institutional authorization, historical access, actual classroom/attendance APIs and real migration remain unresolved.

## Resource and build policy

On 2026-10-14 the owner revised the staging minimum free-disk reserve to **10GiB**. `preflight.py` enforces it, retains 3GiB available RAM, and adds 2GiB before image pulls. Dependency relocation retains 10.1GiB with a maximum 900MiB newly generated dependency footprint. This does not authorize broad cleanup or application-image deletion.

The original build image is no longer cached. This release builds without pulling, using the exact current staging image ID:
`sha256:686f0e5d9bd4a5e401154c7a727a00d33c6f54011b692289ba64dc8d8673577f`.
Pass it as `LEARNHOUSE_WEB_BUILD_IMAGE` to the bounded build/type scripts. Both production bundle and generated-route TypeScript must pass. Earlier SIGKILL attempts are not valid artifacts. No forced worker-thread override is used.

`Dockerfile.classes-preview` overlays only a verified web delta on retained `coursemax-learnhouse:c972fcb5`. Complete desired-tree file/link/mode verification is mandatory; preserve old hashed assets for in-flight clients. Use clean artifact extraction for packaging, never a browser-tested tree whose runtime configuration points to the local test API.

## Deployment/recovery

Private release directory retains pre-release database/content/runtime snapshots, policy/source-menu snapshots, a checksummed saved c972fcb5 rollback image, complete web manifest, image verification, health, browser and identity-count evidence. Only staging app is recreated; gateway reloads routing, all other running container IDs remain unchanged. No migration/flag/provider-policy changes. Rollback loads the saved parent if necessary, recreates app with the same compose stack and restores only the supported source-menu URL; do not restore a database for this code-only change. The rollback also uses the owner-approved 10GiB gate, not obsolete 25GiB scripts.

## Validation record

Thirteen pure state/copy/source-safety cases and nine staging/resource tests pass. Full final build/types, compiled desktop/mobile task evidence, scoped finish review and actual staging checks must be recorded before release is called deployed. Mocked native API tests do not establish backend role/roster/identity parity or real school/provider acceptance.
