"""Tests for the posts CRUD endpoints."""

import uuid

import pytest

from nabora_crm.core.security import hash_password
from nabora_crm.db.session import SessionLocal
from nabora_crm.modules.roles.models import Role
from nabora_crm.modules.users.models import User


def _login(client, email: str, password: str) -> dict[str, str]:
    resp = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture()
def admin_headers(client):
    return _login(client, "admin@test.example", "testpass123")


@pytest.fixture()
def contributor_headers(client):
    email = "contributor@test.example"
    password = "contribpass123"

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if not existing:
            role = db.query(Role).filter(Role.name == "contributor").first()
            db.add(
                User(
                    email=email,
                    hashed_password=hash_password(password),
                    role_id=role.id,
                    is_active=True,
                )
            )
            db.commit()
    finally:
        db.close()

    return _login(client, email, password)


def _payload(**overrides) -> dict:
    data = {
        "headline": "Protein timing",
        "introduction": "When to eat protein",
        "evidence_explanation": "Studies show...",
        "practical_guidance": "Eat 1.6g/kg/day.",
        "sources_references": "Journal of Nutrition",
        "section": "nutrition",
        "topic": "protein",
        "image_url": "https://res.cloudinary.com/demo/image/upload/sample.jpg",
        "placeholder_color": "#4F46E5",
    }
    data.update(overrides)
    return data


def test_contributor_can_create_draft(client, contributor_headers):
    resp = client.post("/v1/posts", json=_payload(), headers=contributor_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "draft"
    assert body["section"] == "nutrition"
    assert body["image_url"].startswith("https://res.cloudinary.com")
    assert body["author_email"] == "contributor@test.example"


def test_create_requires_practical_guidance_and_topic(client, contributor_headers):
    resp = client.post(
        "/v1/posts",
        json={"section": "fitness"},
        headers=contributor_headers,
    )
    assert resp.status_code == 422


def test_invalid_section_and_color_are_rejected(client, contributor_headers):
    bad_section = client.post(
        "/v1/posts",
        json=_payload(section="cardio"),
        headers=contributor_headers,
    )
    assert bad_section.status_code == 422

    bad_color = client.post(
        "/v1/posts",
        json=_payload(placeholder_color="blue"),
        headers=contributor_headers,
    )
    assert bad_color.status_code == 422


def test_contributor_submits_and_admin_publishes(client, contributor_headers, admin_headers):
    created = client.post(
        "/v1/posts", json=_payload(topic="review-flow"), headers=contributor_headers
    )
    assert created.status_code == 201
    post_id = created.json()["id"]

    submitted = client.post(
        f"/v1/posts/{post_id}/submit", headers=contributor_headers
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "pending_review"

    forbidden = client.post(f"/v1/posts/{post_id}/publish", headers=contributor_headers)
    assert forbidden.status_code == 403

    published = client.post(f"/v1/posts/{post_id}/publish", headers=admin_headers)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"


def test_admin_unpublishes_published_post(
    client, contributor_headers, admin_headers
):
    created = client.post(
        "/v1/posts", json=_payload(topic="unpublish-me"), headers=contributor_headers
    )
    post_id = created.json()["id"]
    client.post(f"/v1/posts/{post_id}/submit", headers=contributor_headers)
    client.post(f"/v1/posts/{post_id}/publish", headers=admin_headers)

    forbidden = client.post(
        f"/v1/posts/{post_id}/unpublish", headers=contributor_headers
    )
    assert forbidden.status_code == 403

    unpublished = client.post(
        f"/v1/posts/{post_id}/unpublish", headers=admin_headers
    )
    assert unpublished.status_code == 200, unpublished.text
    assert unpublished.json()["status"] == "unpublished"

    # An unpublished post can be edited by its author and resubmitted.
    edited = client.patch(
        f"/v1/posts/{post_id}",
        json={"headline": "Revised after unpublish"},
        headers=contributor_headers,
    )
    assert edited.status_code == 200, edited.text

    resubmitted = client.post(
        f"/v1/posts/{post_id}/submit", headers=contributor_headers
    )
    assert resubmitted.status_code == 200, resubmitted.text
    assert resubmitted.json()["status"] == "pending_review"


def test_post_status_counts(client, contributor_headers):
    before = client.get("/v1/posts/stats", headers=contributor_headers)
    assert before.status_code == 200, before.text
    before_body = before.json()
    assert set(before_body) == {
        "draft",
        "pending_review",
        "published",
        "unpublished",
        "total",
    }

    client.post(
        "/v1/posts", json=_payload(topic="count-me"), headers=contributor_headers
    )

    after = client.get("/v1/posts/stats", headers=contributor_headers).json()
    assert after["draft"] == before_body["draft"] + 1
    assert after["total"] == before_body["total"] + 1
    assert after["total"] == (
        after["draft"]
        + after["pending_review"]
        + after["published"]
        + after["unpublished"]
    )


def test_contributor_can_update_and_delete_own_post(client, contributor_headers):
    created = client.post(
        "/v1/posts", json=_payload(topic="edit-me"), headers=contributor_headers
    )
    post_id = created.json()["id"]

    updated = client.patch(
        f"/v1/posts/{post_id}",
        json={"headline": "Updated headline"},
        headers=contributor_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["headline"] == "Updated headline"

    deleted = client.delete(f"/v1/posts/{post_id}", headers=contributor_headers)
    assert deleted.status_code == 204

    missing = client.get(f"/v1/posts/{post_id}", headers=contributor_headers)
    assert missing.status_code == 400


def test_list_and_filter_posts(client, contributor_headers):
    fitness = client.post(
        "/v1/posts",
        json=_payload(topic="fitness-topic", section="fitness"),
        headers=contributor_headers,
    ).json()
    nutrition = client.post(
        "/v1/posts",
        json=_payload(topic="nutrition-topic", section="nutrition"),
        headers=contributor_headers,
    ).json()

    resp = client.get(
        "/v1/posts?section=fitness&page_size=100", headers=contributor_headers
    )
    assert resp.status_code == 200, resp.text
    posts = resp.json()["items"]
    ids = {p["id"] for p in posts}
    assert fitness["id"] in ids
    assert nutrition["id"] not in ids
    expected_keys = {
        "id",
        "headline",
        "introduction",
        "evidence_explanation",
        "practical_guidance",
        "sources_references",
        "section",
        "topic",
        "image_url",
        "placeholder_color",
        "status",
        "author_id",
        "author_email",
        "created_at",
        "updated_at",
        "title",
        "author",
    }
    assert expected_keys <= set(posts[0])
    assert posts[0]["title"] == posts[0]["headline"]
    assert posts[0]["author"] == posts[0]["author_email"]


def test_status_filter_and_pagination(client, contributor_headers):
    for i in range(3):
        client.post(
            "/v1/posts",
            json=_payload(topic=f"page-topic-{i}", status="draft"),
            headers=contributor_headers,
        )

    page_one = client.get(
        "/v1/posts?status=draft&page=1&page_size=2", headers=contributor_headers
    )
    assert page_one.status_code == 200, page_one.text
    body = page_one.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    assert body["total"] >= 3
    assert body["pages"] >= 2
    assert all(item["status"] == "draft" for item in body["items"])

    page_two = client.get(
        "/v1/posts?status=draft&page=2&page_size=2", headers=contributor_headers
    )
    assert page_two.status_code == 200
    first_ids = {item["id"] for item in body["items"]}
    second_ids = {item["id"] for item in page_two.json()["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_contributor_sees_only_own_posts_admin_sees_all(
    client, contributor_headers, admin_headers
):
    admin_post = client.post(
        "/v1/posts", json=_payload(topic="admin-topic"), headers=admin_headers
    )
    assert admin_post.status_code == 201
    admin_post_id = admin_post.json()["id"]

    contributor_list = client.get("/v1/posts", headers=contributor_headers)
    assert contributor_list.status_code == 200
    contributor_ids = {p["id"] for p in contributor_list.json()["items"]}
    assert admin_post_id not in contributor_ids

    admin_list = client.get("/v1/posts", headers=admin_headers)
    assert admin_list.status_code == 200
    admin_ids = {p["id"] for p in admin_list.json()["items"]}
    assert admin_post_id in admin_ids


def _ensure_role(client, admin_headers, name, permission_names):
    """Create a custom role or return the existing one's ID."""
    created = client.post(
        "/v1/roles",
        json={"name": name, "permission_names": permission_names},
        headers=admin_headers,
    )
    if created.status_code == 201:
        return created.json()["id"]
    assert created.status_code == 400, created.text
    roles = client.get("/v1/roles", headers=admin_headers).json()
    return next(r["id"] for r in roles if r["name"] == name)


def _create_user_with_role(email, password, role_id):
    """Create or update a user with the given role directly in the DB."""
    role_uuid = uuid.UUID(str(role_id))
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                hashed_password=hash_password(password),
                role_id=role_uuid,
                is_active=True,
            )
            db.add(user)
        else:
            user.hashed_password = hash_password(password)
            user.role_id = role_uuid
            user.is_active = True
        db.commit()
    finally:
        db.close()


def test_list_posts_visibility_is_permission_based(
    client, admin_headers, contributor_headers
):
    """posts:review grants the all-posts view regardless of the role name."""
    shared = client.post(
        "/v1/posts",
        json=_payload(topic="permission-visibility-shared"),
        headers=contributor_headers,
    )
    assert shared.status_code == 201, shared.text
    shared_id = shared.json()["id"]

    author_role_id = _ensure_role(
        client,
        admin_headers,
        "custom-author",
        ["posts:read", "posts:write"],
    )
    _create_user_with_role("custom-author@test.example", "custompass123", author_role_id)
    author_headers = _login(client, "custom-author@test.example", "custompass123")

    own = client.post(
        "/v1/posts",
        json=_payload(topic="permission-visibility-own"),
        headers=author_headers,
    )
    assert own.status_code == 201, own.text
    own_id = own.json()["id"]

    author_list = client.get("/v1/posts", headers=author_headers)
    assert author_list.status_code == 200, author_list.text
    author_ids = {p["id"] for p in author_list.json()["items"]}
    assert own_id in author_ids
    assert shared_id not in author_ids

    reviewer_role_id = _ensure_role(
        client,
        admin_headers,
        "custom-reviewer",
        ["posts:read", "posts:review"],
    )
    _create_user_with_role(
        "custom-reviewer@test.example", "custompass123", reviewer_role_id
    )
    reviewer_headers = _login(client, "custom-reviewer@test.example", "custompass123")

    reviewer_list = client.get("/v1/posts", headers=reviewer_headers)
    assert reviewer_list.status_code == 200, reviewer_list.text
    reviewer_ids = {p["id"] for p in reviewer_list.json()["items"]}
    assert shared_id in reviewer_ids
    assert own_id in reviewer_ids
