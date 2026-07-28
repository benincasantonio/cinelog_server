"""End-to-end coverage for basic public-profile following."""

import pytest

from tests.e2e.conftest import register, register_and_login


def _user_data(suffix: str, visibility: str) -> dict:
    return {
        "email": f"{suffix}@example.com",
        "password": "securepassword123",
        "firstName": suffix.title(),
        "lastName": "Follow",
        "handle": suffix,
        "dateOfBirth": "1990-01-01",
        "profileVisibility": visibility,
    }


async def _login(client, user_data: dict) -> dict:
    response = await client.post(
        "/v1/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    assert response.status_code == 200
    return response.json()


class TestFollowE2E:
    async def test_follow_survives_visibility_change_and_unfollow_is_idempotent(self, async_client):
        target = _user_data("followtarget", "public")
        follower = _user_data("privatefollower", "private")
        await register(async_client, target)
        follower_login = await register_and_login(async_client, follower)

        follow_response = await async_client.put(
            f"/v1/users/{target['handle']}/follow",
            headers={"X-CSRF-Token": follower_login["csrfToken"]},
        )
        duplicate_response = await async_client.put(
            f"/v1/users/{target['handle']}/follow",
            headers={"X-CSRF-Token": follower_login["csrfToken"]},
        )

        assert follow_response.status_code == 204
        assert duplicate_response.status_code == 204

        target_profile = await async_client.get(f"/v1/users/{target['handle']}/profile")
        assert target_profile.status_code == 200
        assert target_profile.json()["followerCount"] == 1
        assert target_profile.json()["followingCount"] == 0
        assert target_profile.json()["isFollowing"] is True

        target_login = await _login(async_client, target)
        update_response = await async_client.put(
            "/v1/users/settings/profile",
            json={"profileVisibility": "private"},
            headers={"X-CSRF-Token": target_login["csrfToken"]},
        )
        assert update_response.status_code == 200

        follower_login = await _login(async_client, follower)
        preserved_response = await async_client.put(
            f"/v1/users/{target['handle']}/follow",
            headers={"X-CSRF-Token": follower_login["csrfToken"]},
        )
        assert preserved_response.status_code == 204

        preserved_profile = await async_client.get(f"/v1/users/{target['handle']}/profile")
        assert preserved_profile.json()["followerCount"] == 1
        assert preserved_profile.json()["isFollowing"] is True
        assert preserved_profile.json()["dateOfBirth"] is None

        unfollow_response = await async_client.delete(
            f"/v1/users/{target['handle']}/follow",
            headers={"X-CSRF-Token": follower_login["csrfToken"]},
        )
        duplicate_unfollow = await async_client.delete(
            f"/v1/users/{target['handle']}/follow",
            headers={"X-CSRF-Token": follower_login["csrfToken"]},
        )

        assert unfollow_response.status_code == 204
        assert duplicate_unfollow.status_code == 204
        final_profile = await async_client.get(f"/v1/users/{target['handle']}/profile")
        assert final_profile.json()["followerCount"] == 0
        assert final_profile.json()["isFollowing"] is False

    @pytest.mark.parametrize("visibility", ["private", "followers_only"])
    async def test_new_follow_rejects_non_public_target(self, async_client, visibility):
        target = _user_data("nonpublictarget", visibility)
        follower = _user_data("publicfollower", "public")
        await register(async_client, target)
        follower_login = await register_and_login(async_client, follower)

        response = await async_client.put(
            f"/v1/users/{target['handle']}/follow",
            headers={"X-CSRF-Token": follower_login["csrfToken"]},
        )

        assert response.status_code == 403
        assert response.json()["error_code_name"] == "PROFILE_NOT_PUBLIC"

    async def test_self_follow_is_rejected(self, async_client):
        user = _user_data("selffollower", "public")
        login = await register_and_login(async_client, user)

        response = await async_client.put(
            f"/v1/users/{user['handle']}/follow",
            headers={"X-CSRF-Token": login["csrfToken"]},
        )

        assert response.status_code == 400
        assert response.json()["error_code_name"] == "SELF_FOLLOW_NOT_ALLOWED"

    async def test_mutual_follows_have_independent_counts(self, async_client):
        alice = _user_data("mutualalice", "public")
        bob = _user_data("mutualbob", "public")
        await register(async_client, bob)
        alice_login = await register_and_login(async_client, alice)

        alice_follows = await async_client.put(
            f"/v1/users/{bob['handle']}/follow",
            headers={"X-CSRF-Token": alice_login["csrfToken"]},
        )
        assert alice_follows.status_code == 204

        bob_login = await _login(async_client, bob)
        bob_follows = await async_client.put(
            f"/v1/users/{alice['handle']}/follow",
            headers={"X-CSRF-Token": bob_login["csrfToken"]},
        )
        assert bob_follows.status_code == 204

        alice_profile = await async_client.get(f"/v1/users/{alice['handle']}/profile")
        assert alice_profile.json()["followerCount"] == 1
        assert alice_profile.json()["followingCount"] == 1
        assert alice_profile.json()["isFollowing"] is True

        bob_profile = await async_client.get(f"/v1/users/{bob['handle']}/profile")
        assert bob_profile.json()["followerCount"] == 1
        assert bob_profile.json()["followingCount"] == 1
        assert bob_profile.json()["isFollowing"] is False
