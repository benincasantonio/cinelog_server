# Account Localization

Cinelog stores a private locale preference for each account. The preference restores the signed-in interface language and acts as the fallback language for live TMDB movie searches and details.

## Supported Locales

| Locale | Language |
|--------|----------|
| `en-US` | English |
| `fr-FR` | French |
| `it-IT` | Italian |

Locale values are normalized case-insensitively to one of these tags. Other values are rejected.

## Registration and Account Responses

`locale` is required by `POST /v1/auth/register`:

```json
{
  "firstName": "Ada",
  "lastName": "Lovelace",
  "email": "ada@example.com",
  "password": "securepassword123",
  "handle": "ada",
  "dateOfBirth": "1990-01-01",
  "locale": "it-IT",
  "verificationCode": "ABC123"
}
```

Self-account responses return the saved `locale`, including registration, login, `GET /v1/users/info`, and profile updates. Public profile responses do not expose another user's locale.

## Changing Locale

**Endpoint:** `PUT /v1/users/settings/locale`

The request is authenticated and requires the normal `X-CSRF-Token` header.

```json
{
  "locale": "fr-FR"
}
```

The response confirms the canonical saved value:

```json
{
  "locale": "fr-FR"
}
```

## Live TMDB Language

Clients should send the active locale through the standard `Accept-Language` header:

```http
Accept-Language: it-IT
```

The server honors quality weights and maps compatible variants to a supported locale. For example, `fr-CA,fr;q=0.9` selects `fr-FR`. When the header has no supported language, the saved account locale is used; malformed legacy state defensively falls back to `en-US`.

This localization currently applies only to live `GET /v1/movies/search` and `GET /v1/movies/{tmdb_id}` responses. Movie metadata persisted for logs and ratings remains canonical `en-US`; localized saved metadata is tracked in [server issue #214](https://github.com/benincasantonio/cinelog_server/issues/214).

## See Also

- [Technical: Account Localization](../technical/localization.md)
- [Authentication](authentication.md)
- [TMDB Movie Service](tmdb-service.md)
