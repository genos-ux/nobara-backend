"""Tests for the contributors listing endpoint."""

from unittest.mock import patch

import pytest

from nabora_crm.core.security import create_invitation_token


@pytest.fixture()
def admin_headers(client):
    resp = client.post(
        "/v1/auth/login",
        json={"email": "admin@test.example", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _contributor_role_id(client, admin_headers):
    resp = client.get("/v1/roles", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    for role in resp.json():
        if role["name"] == "contributor":
            return role["id"]
    pytest.fail("contributor role not found")


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_list_contributors_includes_posts_and_status(
    mock_send_email, client, admin_headers
):
    """Contributors are returned with name, role, email, posts, and status."""
    role_id = _contributor_role_id(client, admin_headers)

    invite = client.post(
        "/v1/invitations",
        json={
            "full_name": "Listed Contributor",
            "email": "listed@test.example",
            "role_id": role_id,
        },
        headers=admin_headers,
    )
    assert invite.status_code == 201, invite.text
    user_id = invite.json()["id"]

    token = create_invitation_token(
        {"sub": user_id, "email": "listed@test.example"}
    )
    accept = client.post(
        "/v1/invitations/accept",
        json={"token": token, "password": "strongpassword123"},
    )
    assert accept.status_code == 200, accept.text

    login = client.post(
        "/v1/auth/login",
        json={"email": "listed@test.example", "password": "strongpassword123"},
    )
    contributor_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    post = client.post(
        "/v1/posts",
        json={
            "headline": "Contributor post",
            "practical_guidance": "Do the thing.",
            "section": "nutrition",
            "topic": "protein",
        },
        headers=contributor_headers,
    )
    assert post.status_code == 201, post.text
    post_id = post.json()["id"]

    resp = client.get("/v1/users/contributors", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert body["total"] >= 1
    assert body["pages"] >= 1
    contributors = body["items"]

    entry = next(c for c in contributors if c["email"] == "listed@test.example")
    assert entry["full_name"] == "Listed Contributor"
    assert entry["role"] == "contributor"
    assert entry["is_active"] is True
    assert entry["is_pending"] is False
    assert entry["post_count"] == 1
    assert entry["posts"][0]["id"] == post_id
    assert entry["posts"][0]["headline"] == "Contributor post"


@patch("nabora_crm.modules.invitations.service.send_invitation_email")
def test_list_contributors_search_and_pagination(
    mock_send_email, client, admin_headers
):
    """Search filters by name/email and pagination limits results."""
    role_id = _contributor_role_id(client, admin_headers)

    for name, email in (
        ("Search Alpha", "search.alpha@test.example"),
        ("Search Beta", "search.beta@test.example"),
    ):
        resp = client.post(
            "/v1/invitations",
            json={"full_name": name, "email": email, "role_id": role_id},
            headers=admin_headers,
        )
        assert resp.status_code == 201, resp.text

    found = client.get(
        "/v1/users/contributors", params={"search": "alpha"}, headers=admin_headers
    )
    assert found.status_code == 200, found.text
    body = found.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "search.alpha@test.example"

    by_email = client.get(
        "/v1/users/contributors",
        params={"search": "search.beta@"},
        headers=admin_headers,
    )
    assert by_email.status_code == 200, by_email.text
    assert by_email.json()["items"][0]["full_name"] == "Search Beta"

    paged = client.get(
        "/v1/users/contributors",
        params={"search": "search.", "page": 1, "page_size": 1},
        headers=admin_headers,
    )
    assert paged.status_code == 200, paged.text
    paged_body = paged.json()
    assert paged_body["total"] == 2
    assert paged_body["pages"] == 2
    assert len(paged_body["items"]) == 1

    page2 = client.get(
        "/v1/users/contributors",
        params={"search": "search.", "page": 2, "page_size": 1},
        headers=admin_headers,
    )
    assert page2.status_code == 200, page2.text
    assert page2.json()["items"][0]["email"] != paged_body["items"][0]["email"]


def test_contributors_requires_permission(client):
    """Users without users:read cannot list contributors."""
    login = client.post(
        "/v1/auth/login",
        json={"email": "listed@test.example", "password": "strongpassword123"},
    )
    if login.status_code != 200:
        pytest.skip("contributor fixture user not available")
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.get("/v1/users/contributors", headers=headers)
    assert resp.status_code == 403
