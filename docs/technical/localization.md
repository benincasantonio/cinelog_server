# Account Localization — Technical Details

## Persistence and Validation

Migration `008_add_locale_to_users` adds `users.locale` as non-null text, backfills existing rows to `en-US`, retains that server default, and enforces `ck_users_locale` for `en-US`, `fr-FR`, and `it-IT`.

`LocaleStr` and `validate_locale` live in `app/types/user_validation.py` and are exported through `app.types`. Request validation strips whitespace and canonicalizes tag casing. Locale is required during registration and can be changed independently through `PUT /v1/users/settings/locale`.

Account-oblivion erasure resets locale to `en-US`. Public-profile schemas deliberately omit it.

## Request Locale Resolution

Locale-aware endpoints use `locale_dependency`:

1. Parse `Accept-Language` and order entries by their `q` quality value and original position.
2. Prefer an exact supported tag.
3. Match the primary language when the region differs, such as `it-CH` to `it-IT`.
4. Ignore wildcards, malformed entries, unsupported languages, and entries with `q=0`.
5. When no header value matches, load the authenticated user's current locale from PostgreSQL.
6. Use `en-US` only when the user or stored locale is unavailable or malformed.

The supported-header path performs no preference query. PostgreSQL remains authoritative, and database failures are not converted into language fallbacks. Locale is not stored in JWTs or in a separate Redis preference cache.

## TMDB Integration

`TMDBService.search_movie` and `get_movie_details` pass the selected full locale tag as TMDB's `language` query parameter. Cache keys include locale to prevent one language's payload from serving another:

| Operation | Key |
|-----------|-----|
| Search | `cinelog:tmdb:search:{locale}:{normalized_query}` |
| Details | `cinelog:tmdb:details:{locale}:{tmdb_id}` |

Legacy cache keys are no longer read and expire through their existing TTL.

`MovieService.find_or_create_movie` always requests `en-US` before persisting a canonical movie row. Live localized TMDB responses are not stored in PostgreSQL and log/history responses are not hydrated per movie. Persisted localized movie text is deferred to [server issue #214](https://github.com/benincasantonio/cinelog_server/issues/214).

## API and Rollout

Locale appears in self-account response schemas and in the dedicated locale-update response. It is intentionally absent from public profiles.

Registration now requires `locale`, which is a breaking request-contract change. Deployment must be coordinated with [frontend issue #82](https://github.com/benincasantonio/cinelog_web/issues/82), which adds the registration field, restores i18n from `/v1/users/info`, persists menu changes, and sends `Accept-Language`.

## See Also

- [Functional: Account Localization](../functional/localization.md)
- [Technical: Authentication](authentication.md)
- [Technical: TMDB Service](tmdb-service.md)
