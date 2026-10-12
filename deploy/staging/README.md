# Restricted single-host staging

This deployment is **not production acceptance**. It uses only synthetic records.
The public gateway is a separate Compose profile so it cannot be exposed by an
ordinary `up -d` before native signup policy and validation are complete.

## Architecture

- Immutable upstream community image at source `45cf5d4f78cf537064070dc8e315a64990d14966`.
  Web/API/collaboration are separate processes inside that upstream image.
- Two tracked read-only overlays: `apps/web/server-wrapper.js` (server-only internal
  API URL) and `docker/nginx.conf` (suppress callback URL access logging). Record
  both the image digest and the clean fork commit for every release. Do not edit
  these bind-mounted files under a running release; use an isolated checkout.
- Separate PostgreSQL/pgvector, Redis and content volumes; no source-system data.
- Only the evaluator gateway joins the existing Traefik network. Database/cache
  have internal-only networking; no container publishes a host port.
- App gets dedicated outbound networking for eventual approved OAuth requests.
  AI, nudges, demo sync, HLS, email credentials and external analytics are disabled
  or unconfigured. Enterprise code is disabled.
- CPU/memory limits and bounded logs keep the initial stack small. These limits
  need actual startup/load verification, not assumptions from configuration.

## Private initialization

Run the generator once, choosing a protected directory **outside** the checkout:

```sh
python3 deploy/staging/init_runtime.py \
  --runtime-dir /absolute/private/runtime \
  --domain learn.example.com \
  --admin-email admin@example.com
```

The example account is a reserved synthetic bootstrap identity, not a migrated user.
The script generates unrelated database, JWT, collaboration, bootstrap-admin and
preview secrets. Credentials are never printed. Retrieve them locally from the
private `ACCESS.txt`; never commit or paste it into logs/issues.

The runtime directory is mode 0700. Files are 0600 except the read-only password
hash file (0444), which Nginx's unprivileged worker must read through its dedicated
mount; the private parent still prevents other host users from reaching it.
The generator refuses to replace existing files or write secrets under this repo.

## Resource gate — do not bypass

```sh
python3 deploy/staging/preflight.py --before-pull
```

Requires 27 GiB free (25 GiB floor plus image reserve) and 3 GiB available RAM.
After pulling, run without `--before-pull` and require the 25 GiB floor again.
It never prunes or changes anything. Cache cleanup requires separate approval.
The shell running these commands may be on the same machine as the deployment:
do not assume a local build uses different host resources.

## Controlled first launch

1. Check source cleanliness/push, image/source provenance, private runtime modes,
   existing-service health/revisions and the resource gate.
2. Validate Compose with `--env-file /absolute/private/runtime/compose.env` and
   `-f deploy/staging/compose.yaml config --quiet`. Never print fully expanded
   Compose/environment output containing secrets.
3. Pull only this project's digest-pinned images after the before-pull gate passes;
   recheck disk afterward. Do not rebuild large images on the shared host by default.
4. Start **app/db/redis only**, leaving the `public` profile off. Require all three
   application processes and both stores healthy. Auto-install uses the generated
   synthetic admin; no real users or courses are imported.
5. Authenticate to the local API using that bootstrap identity; tokens stay in
   memory. Resolve the actual organization ID from the default slug.
6. Use the supported admin API to set the organization's signup mechanism to
   `inviteOnly` (`PUT /api/v1/orgs/{id}/signup_mechanism`, query parameter
   `signup_mechanism=inviteOnly`) and verify the resulting configuration.
   Never accomplish this through direct database writes. The gateway separately
   blocks ordinary global/org password-signup endpoints; invitation flows remain
   protected by evaluator access plus application policy.
7. Verify disabled outbound features and private course defaults. Demonstrate
   native admin login and a synthetic teacher/student task flow.
8. Take private database/content backups and test a restore under a separate
   disposable project with no public routing. Record revision, schema and checksums.
9. Only then enable the `public` profile. Verify DNS/TLS, anonymous denial, valid
   evaluator access, native login/logout, private files, collaboration and mobile.
10. Provide the owner access instructions through the agreed private channel. The
    evaluator gate is not the app account; both credentials are in `ACCESS.txt`.

These are release steps, not claims they have been performed. Do not enable the
public profile simply because `docker compose config` passes.

## Evaluator access and bearer tokens

Basic authentication establishes a random `__Host-LH_preview` cookie. It is Secure,
HttpOnly, host-only, SameSite=Lax. Requests with that valid cookie can then carry
LearnHouse's own Bearer Authorization header; Basic credentials are stripped before
proxying upstream. Failed challenges do not mint cookies. API/files/WebSockets use
the same gate. This avoids putting ordinary Basic auth in front of every Bearer API
request, which would break the native application.

The cookie's eight-hour browser max-age is **not server-side token expiry**. This
is a temporary shared evaluator credential, not a substitute for native identity.
Revoke it by rotating both the preview token/config and password hash, then reload
only this gateway. Never rely on logging out of LearnHouse to revoke evaluator
access. Move to individual evaluator access when identity acceptance supports it.

The server wrapper writes the private API URL only to its server runtime JSON;
browser runtime config retains the public HTTPS URL. No JWT/OAuth secrets enter
`NEXT_PUBLIC_*` values. Single tenancy keeps application cookies host-only.

## Tests

```sh
python3 -m unittest discover -s deploy/staging -p 'test_staging.py' -v
node --test apps/web/tests/server-wrapper-runtime.test.mjs
RUN_GATEWAY_DOCKER_TESTS=1 python3 -m unittest discover -s deploy/staging -p 'test_gateway.py' -v
```

The optional gateway test uses an explicitly pinned **already cached** Nginx image,
`--pull=never`, no network, no host ports, no named volumes and synthetic credentials.
It removes only its uniquely named temporary container. This validates the auth
contract, not the candidate production image or the complete LearnHouse workflow.
Re-run equivalent probes against the actual candidate before public exposure.

## Backup and rollback boundaries

Back up database and content together with a protected secret/config recovery copy.
Redis needs an explicit treatment for active collaborative work; do not discard it
as disposable cache without proving all accepted state has been flushed.

For a failed first launch, disable only this gateway and preserve data/diagnostics.
For later releases, retain the previous immutable image and overlay checkout. Check
schema compatibility before rollback; never blindly downgrade a database with new
writes. DNS rollback cannot recover academic or collaborative evidence by itself.
No command here stops another Compose project or removes a data volume.

## License/source

Preserve upstream AGPL notices. Publish the fork's corresponding code as required,
including these overlays; private credentials/data are never part of that offer.
An evaluator must be given an accessible source link for the actual deployed commit.
