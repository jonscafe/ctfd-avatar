# Avatars Plugin for CTFd

A simple plugin to add avatar/profile photo upload features for users and teams in CTFd.  
No database changes needed — all avatars are stored as files in the filesystem.

## Features

- **User avatar upload** — on Settings page
- **Team avatar upload** — in the team edit modal (captain only)
- **Automatic fallback** — Uploaded file → Gravatar (user) → DiceBear identicon (team)
- **File-based storage** — no database schema modification
- **Docker-ready** — uses CTFd's `UPLOAD_FOLDER` config
- **Graceful degradation** — if storage is read-only, uploading is disabled but the page remains functional

## Requirements

- CTFd 3.x+
- Theme that integrates the `avatar_url()` template helper (for example: `wreckit` theme)

## Installation

### 1. Copy the plugin to CTFd

```bash
cp -r avatars/ /path/to/CTFd/CTFd/plugins/avatars/
```

### 2. Restart CTFd

The plugin will be loaded automatically by CTFd on startup.

### 3. Ensure UPLOAD_FOLDER is writable

The plugin saves avatars in `UPLOAD_FOLDER/avatars/`. Make sure this folder is writable.

**Bare metal / VM:**
```bash
# Default UPLOAD_FOLDER = CTFd/uploads/
mkdir -p /path/to/CTFd/CTFd/uploads/avatars
chmod 755 /path/to/CTFd/CTFd/uploads/avatars
```

**Docker:**
```yaml
# docker-compose.yml
services:
  ctfd:
    environment:
      - UPLOAD_FOLDER=/var/uploads          # Writable volume
    volumes:
      - .data/CTFd/uploads:/var/uploads     # Persistent storage
      - ./CTFd/plugins/avatars:/opt/CTFd/CTFd/plugins/avatars:ro
```

## Configuration

This plugin does not require additional configuration. It automatically uses:

| Config           | Source               | Default                  |
|------------------|---------------------|--------------------------|
| `UPLOAD_FOLDER`  | CTFd config / env   | `<CTFd_root>/uploads/`   |

### Internal Constants

| Constant             | Value              | Description                     |
|----------------------|--------------------|---------------------------------|
| `MAX_FILE_SIZE`      | 2 MB               | Maximum avatar file size        |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, webp | Allowed file formats      |

## Storage

Avatars are stored in the filesystem with the naming format:

```
UPLOAD_FOLDER/
└── avatars/
    ├── user_1.png
    ├── user_2.jpg
    ├── team_1.webp
    └── team_3.gif
```

- Each entity may have only 1 avatar — uploading a new one deletes the old
- When an avatar is deleted, the file is removed from disk

## API Endpoints

All endpoints are registered as Flask Blueprints and available at the CTFd root URL.

### GET `/avatars/<type>/<id>`

Displays the avatar image.

| Parameter  | Type    | Description                    |
|------------|---------|--------------------------------|
| `type`     | string  | `user` or `team`               |
| `id`       | integer | User or team ID                |

**Response:**
- `200` — Avatar image (cached 5 minutes)
- `400` — Type is not `user`/`team`
- `404` — No avatar uploaded

---

### POST `/avatars/user/upload`

Upload an avatar for the logged-in user.

**Auth:** Required (login)

**Body:** `multipart/form-data`

| Field    | Type   | Description                                      |
|----------|--------|--------------------------------------------------|
| `avatar` | file   | Image file (max 2MB, format: png/jpg/gif/webp)   |
| `nonce`  | string | CSRF nonce from `Session.nonce`                  |

**Response:**
```json
// Success
{ "success": true, "url": "/avatars/user/1" }

// Failure
{ "success": false, "errors": ["File too large. Max 2MB"] }
```

| Status | Condition                                    |
|--------|----------------------------------------------|
| `200`  | Upload successful                            |
| `400`  | Invalid / missing file                       |
| `403`  | Not authenticated                            |
| `503`  | Storage not writable                         |

---

### POST `/avatars/team/upload`

Upload an avatar for a team. **Only captain** is allowed.

**Auth:** Required (login, team captain)

**Body:** `multipart/form-data`

| Field    | Type   | Description                                      |
|----------|--------|--------------------------------------------------|
| `avatar` | file   | Image file (max 2MB, format: png/jpg/gif/webp)   |
| `nonce`  | string | CSRF nonce from `Session.nonce`                  |

**Response:**
```json
// Success
{ "success": true, "url": "/avatars/team/5" }

// Failure
{ "success": false, "errors": ["Only the team captain can change the avatar"] }
```

| Status | Condition                                    |
|--------|----------------------------------------------|
| `200`  | Upload successful                            |
| `400`  | Invalid file / not a team member             |
| `403`  | Not captain / not authenticated              |
| `503`  | Storage not writable                         |

---

### POST `/avatars/user/delete`

Delete the avatar for the logged-in user.

**Auth:** Required (login)

**Body:** `multipart/form-data`

| Field    | Type   | Description                                      |
|----------|--------|--------------------------------------------------|
| `nonce`  | string | CSRF nonce                                       |

**Response:**
```json
{ "success": true }
```

---

### POST `/avatars/team/delete`

Delete the team avatar. **Only captain** is allowed.

**Auth:** Required (login, team captain)

**Body:** `multipart/form-data`

| Field    | Type   | Description                                      |
|----------|--------|--------------------------------------------------|
| `nonce`  | string | CSRF nonce                                       |

**Response:**
```json
{ "success": true }
```

## Template Helpers

The plugin registers global helpers in Jinja2 available to all templates.

### `avatar_url(entity_type, entity_id, fallback_email=None)`

Returns the avatar URL with fallback chain:

1. **Uploaded avatar** → `/avatars/{type}/{id}` (if file exists on disk)
2. **Gravatar** → `https://www.gravatar.com/avatar/{md5}?d=identicon` (if `entity_type == "user"` and `fallback_email` is provided)
3. **DiceBear identicon** → `https://api.dicebear.com/7.x/identicon/svg?seed={id}` (last fallback)

**Example Usage in Template:**

```html
<!-- User avatar with Gravatar fallback -->
<img src="{{ avatar_url('user', user.id, user.email) }}" alt="Avatar">

<!-- Team avatar with DiceBear fallback -->
<img src="{{ avatar_url('team', team.id) }}" alt="Team Avatar">

<!-- In sidebar -->
<img src="{{ avatar_url('user', Session.id, User.email) }}" alt="">
```

### `md5` Template Filter

MD5 hashing filter, useful for manual Gravatar URL:

```html
<img src="https://www.gravatar.com/avatar/{{ user.email | md5 }}?d=identicon">
```

## Theme Integration

To integrate this plugin with a custom CTFd theme, you need to modify:

### 1. Templates displaying avatar

Replace hardcoded avatar URLs with `avatar_url()`:

```html
<!-- Before -->
<img src="/themes/core/static/img/default-avatar.png">

<!-- After -->
<img src="{{ avatar_url('user', user.id, user.email) }}">
```

### 2. Settings Page (user avatar upload)

Add Alpine.js component `AvatarUpload` in `assets/js/settings.js`:

```javascript
Alpine.data("AvatarUpload", () => ({
  avatarSrc: "",
  hasCustomAvatar: false,
  avatarError: null,
  avatarSuccess: false,

  init() {
    const userId = window.init.userId;
    this.avatarSrc = `${window.init.urlRoot}/avatars/user/${userId}?cb=${Date.now()}`;
    fetch(`${window.init.urlRoot}/avatars/user/${userId}`, { method: "HEAD" })
      .then(resp => { if (resp.ok) this.hasCustomAvatar = true; })
      .catch(() => {});
  },

  async uploadAvatar(event) {
    this.avatarError = null;
    this.avatarSuccess = false;
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      this.avatarError = "File too large. Maximum size is 2MB.";
      return;
    }
    const formData = new FormData();
    formData.append("avatar", file);
    formData.append("nonce", window.init.csrfNonce);
    try {
      const resp = await fetch(`${window.init.urlRoot}/avatars/user/upload`, {
        method: "POST", body: formData
      });
      const data = await resp.json();
      if (data.success) {
        this.avatarSrc = `${window.init.urlRoot}/avatars/user/${window.init.userId}?cb=${Date.now()}`;
        this.hasCustomAvatar = true;
        this.avatarSuccess = true;
        setTimeout(() => { this.avatarSuccess = false; }, 3000);
      } else {
        this.avatarError = data.errors?.[0] || "Upload failed.";
      }
    } catch { this.avatarError = "Upload failed."; }
    event.target.value = "";
  },

  async removeAvatar() {
    const formData = new FormData();
    formData.append("nonce", window.init.csrfNonce);
    try {
      const resp = await fetch(`${window.init.urlRoot}/avatars/user/delete`, {
        method: "POST", body: formData
      });
      const data = await resp.json();
      if (data.success) {
        this.avatarSrc = `${window.init.urlRoot}/avatars/user/${window.init.userId}?cb=${Date.now()}`;
        this.hasCustomAvatar = false;
      }
    } catch {}
  },
}));
```

### 3. Team Private Page (team avatar upload)

Add Alpine.js component `TeamAvatarUpload` in `assets/js/teams/private.js` — similar to above but endpoints are `/avatars/team/upload` and `/avatars/team/delete`.

### 4. Scoreboard (client-side avatar)

For avatars in the scoreboard rendered via JavaScript, use the endpoint directly with `onerror` fallback:

```html
<img src="/avatars/user/${id}"
     onerror="this.src='https://api.dicebear.com/7.x/identicon/svg?seed=${id}'">
```

## Troubleshooting

| Problem                               | Cause                                         | Solution                                   |
|----------------------------------------|-----------------------------------------------|--------------------------------------------|
| `OSError: Read-only file system`       | `UPLOAD_FOLDER` points to a read-only path    | Set `UPLOAD_FOLDER` env to a writable volume (e.g. `/var/uploads`) |
| Avatar not showing                     | Plugin not installed                          | Ensure `CTFd/plugins/avatars/__init__.py` exists |
| "Avatar uploads not available" (503)   | Avatars folder cannot be created              | Check `UPLOAD_FOLDER/avatars/` folder permissions |
| Successful upload but image not updated| Browser cache                                 | Hard refresh (Ctrl+Shift+R) or append `?cb=timestamp` |
| "Only the team captain can change the avatar" | Not team captain                      | Only captain can upload/remove team avatar  |
| Gravatar not appearing                 | Email not registered at Gravatar              | Register at [gravatar.com](https://gravatar.com), or default identicon will be shown |

## Architecture

```
Plugin Load Flow:
─────────────────
CTFd startup
  └─ load(app)
       ├─ _ensure_avatars_dir()      # Create folder once on startup
       ├─ Register Blueprint         # 5 route endpoints
       ├─ Register avatar_url()      # Jinja2 template global
       └─ Register md5 filter        # Jinja2 template filter

Request Flow (avatar_url):
──────────────────────────
Template render
  └─ avatar_url('user', 1, 'user@email.com')
       ├─ find_avatar('user', 1)     # Check file on disk
       │   ├─ Found? → return "/avatars/user/1"
       │   └─ Not found? ↓
       ├─ Has email? → Gravatar URL
       └─ No email? → DiceBear URL

Upload Flow:
────────────
POST /avatars/user/upload
  ├─ Check _avatars_dir_writable
  ├─ Auth check (authed_only)
  ├─ Validate file (type, size)
  ├─ Delete existing avatar files
  ├─ Save new file: user_{id}.{ext}
  └─ Return JSON { success: true }
```

## License

This plugin is part of the Wreckit CTFd theme and follows the same license as CTFd.

---

Let me know if you want this saved as a file or if you need any specific details edited!
