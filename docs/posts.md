# Posts

Covers creating posts, the review lifecycle, and admin publish/unpublish actions.

---

## Permissions Required

| Action | Permission |
|--------|------------|
| Read posts | `posts:read` (public guests may read published posts) |
| Create and edit posts | `posts:write` |
| Delete posts | `posts:delete` |
| Publish, unpublish, request changes | `posts:review` |

**Visibility:** Contributors only see their own posts. Users with `posts:review` see all posts. Unauthenticated guests can list and fetch published posts without a token.

---

## Post Status Lifecycle

```
           [Author]                         [Reviewer / Admin]
              │                                      │
           create                                    │
              │                                      │
           draft ──── submit ──► pending_review ─────┤
              ▲                        │              │
              │             ┌──────────┤              │
              │       changes_requested               ├──► published
              └──── re-submit ◄────────┘              │
                                                      └──► unpublished
                                                               │
                                                    (can re-publish)
```

| Status | Who sets it |
|--------|-------------|
| `draft` | Author on create, or default |
| `pending_review` | Author via submit action (or on create) |
| `changes_requested` | Reviewer via request-changes action |
| `published` | Reviewer via publish action |
| `unpublished` | Reviewer via unpublish action |

---

## Enum Values

**Sections:**
- `nutrition`
- `fitness`

**Topics:**
- `Nutrition Basics`
- `Health & Wellness`
- `Supplement Education`
- `Ingredients Explained`
- `Public Health Topics`
- `Training`
- `Performance`
- `Recovery`
- `Fitness Education`

---

## Create Post

```
POST /v1/posts
```

**Request body:**
```json
{
  "practical_guidance": "Full post content — required.",
  "section": "nutrition",
  "topic": "Nutrition Basics",
  "headline": "Why protein matters",
  "introduction": "A short intro paragraph.",
  "evidence_explanation": "What the research says.",
  "sources_references": "1. Smith et al. 2024",
  "image_url": "https://example.com/image.jpg",
  "placeholder_color": "#3a7bd5",
  "status": "draft"
}
```

- `practical_guidance` is the only required field besides `section` and `topic`.
- Set `status` to `"pending_review"` to submit immediately on creation instead of saving as a draft.
- `placeholder_color` must be a valid hex code (`#fff` or `#ffffff`).

**Response (201):** Full post object (see shape below).

---

## Post Object Shape

```json
{
  "id": "uuid",
  "headline": "Why protein matters",
  "introduction": "...",
  "evidence_explanation": "...",
  "practical_guidance": "...",
  "sources_references": "...",
  "review_note": null,
  "section": "nutrition",
  "topic": "Nutrition Basics",
  "image_url": "https://example.com/image.jpg",
  "placeholder_color": "#3a7bd5",
  "status": "draft",
  "author_id": "uuid",
  "author_email": "jane@example.com",
  "created_at": "2026-11-15T10:00:00Z",
  "updated_at": "2026-11-15T10:00:00Z"
}
```

`review_note` is populated when a reviewer requests changes. Show it to the author so they know what to fix.

---

## List Posts

```
GET /v1/posts
```

This endpoint is public. Without an `Authorization` header, only `published` posts are returned (the `status` filter is ignored for guests).

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page, 1–100 (default: 10) |
| `section` | string | Filter by section (`nutrition` or `fitness`) |
| `topic` | string | Filter by topic |
| `status` | string | Filter by status |

**Response:**
```json
{
  "items": [
    {
      ...all PostOut fields...,
      "title": "Why protein matters",
      "author": "jane@example.com",
      "author_name": "Jane Doe"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 10,
  "pages": 2
}
```

`title` mirrors `headline` and `author` mirrors `author_email` — both are provided for backwards compatibility. `author_name` is only populated for users with `posts:review`.

---

## Post Status Counts (Dashboard Badge)

```
GET /v1/posts/stats
```

**Response:**
```json
{
  "draft": 2,
  "pending_review": 1,
  "changes_requested": 0,
  "published": 8,
  "unpublished": 1,
  "total": 12
}
```

Counts reflect the same visibility rules as the list endpoint.

---

## Get Single Post

```
GET /v1/posts/{post_id}
```

Public: no token is required to fetch a `published` post. Returns the full post object.

---

## Update Post

```
PATCH /v1/posts/{post_id}
```

All fields are optional. Only the author can update their own posts.

**Request body:**
```json
{
  "headline": "Updated title",
  "practical_guidance": "Revised content",
  "section": "fitness",
  "topic": "Health & Wellness"
}
```

**Response:** Updated post object.

---

## Delete Post

```
DELETE /v1/posts/{post_id}
```

Returns `204 No Content`. Authors can delete their own posts; admins can delete any post.

---

## Workflow Actions

### Submit for Review (Author)

Transitions post from `draft` or `changes_requested` to `pending_review`.

```
POST /v1/posts/{post_id}/submit
```

No body required. Returns the updated post object.

**Side effect:** Notifies users with `posts:review` permission that a new post is awaiting review (`post_submitted` notification).

---

### Request Changes (Reviewer)

Transitions post from `pending_review` to `changes_requested` and stores a note for the author.

```
POST /v1/posts/{post_id}/request-changes
```

**Request body:**
```json
{ "note": "Please expand the evidence section and add sources." }
```

Returns the updated post object. The `review_note` field on the post is now populated.

**Side effect:** Notifies the author with a `post_changes_requested` notification including the note.

---

### Publish (Reviewer)

Transitions post from `pending_review` to `published`.

```
POST /v1/posts/{post_id}/publish
```

No body required. Returns the updated post object.

**Side effect:** Notifies the author with a `post_published` notification.

---

### Unpublish (Reviewer)

Transitions post from `published` to `unpublished`.

```
POST /v1/posts/{post_id}/unpublish
```

No body required. Returns the updated post object.

**Side effect:** Notifies the author with a `post_unpublished` notification.

---

## Suggested UI Flows

**Contributor view:**
1. Create post as draft → edit until ready → click Submit for Review.
2. If `changes_requested`: show `review_note` → allow editing → re-submit.
3. Use status filters and stats to build a personal dashboard.

**Reviewer / Admin view:**
1. Filter by `status=pending_review` to see the review queue.
2. Open post → Publish or Request Changes.
3. Use `GET /v1/posts/stats` to show a pending review count badge.
