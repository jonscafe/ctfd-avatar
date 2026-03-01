# Avatars Plugin for CTFd

Plugin sederhana untuk menambahkan fitur upload avatar/foto profil pada user dan team di CTFd.  
Tidak memerlukan perubahan database — semua avatar disimpan sebagai file di filesystem.

## Fitur

- **Upload avatar user** — di halaman Settings
- **Upload avatar team** — di modal edit team (hanya captain)
- **Fallback otomatis** — Uploaded file → Gravatar (user) → DiceBear identicon (team)
- **File-based storage** — tanpa modifikasi schema database
- **Docker-ready** — menggunakan `UPLOAD_FOLDER` config dari CTFd
- **Graceful degradation** — jika storage read-only, upload dinonaktifkan tapi halaman tetap berfungsi normal

## Persyaratan

- CTFd 3.x+
- Theme yang sudah mengintegrasikan template helper `avatar_url()` (contoh: theme `wreckit`)

## Instalasi

### 1. Copy plugin ke CTFd

```bash
cp -r avatars/ /path/to/CTFd/CTFd/plugins/avatars/
```

### 2. Restart CTFd

Plugin akan otomatis dimuat oleh CTFd saat startup.

### 3. Pastikan UPLOAD_FOLDER writable

Plugin menyimpan avatar di `UPLOAD_FOLDER/avatars/`. Pastikan folder ini writable.

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
      - UPLOAD_FOLDER=/var/uploads          # Volume writable
    volumes:
      - .data/CTFd/uploads:/var/uploads     # Persistent storage
      - ./CTFd/plugins/avatars:/opt/CTFd/CTFd/plugins/avatars:ro
```

## Konfigurasi

Plugin ini tidak memerlukan konfigurasi tambahan. Ia secara otomatis menggunakan:

| Config | Sumber | Default |
|--------|--------|---------|
| `UPLOAD_FOLDER` | CTFd config / env var | `<CTFd_root>/uploads/` |

### Konstanta Internal

| Konstanta | Nilai | Deskripsi |
|-----------|-------|-----------|
| `MAX_FILE_SIZE` | 2 MB | Ukuran maksimum file avatar |
| `ALLOWED_EXTENSIONS` | png, jpg, jpeg, gif, webp | Format file yang diizinkan |

## Storage

Avatar disimpan di filesystem dengan format nama:

```
UPLOAD_FOLDER/
└── avatars/
    ├── user_1.png
    ├── user_2.jpg
    ├── team_1.webp
    └── team_3.gif
```

- Setiap entity hanya boleh memiliki 1 avatar — upload baru otomatis menghapus yang lama
- Saat avatar dihapus, file dihapus dari disk

## API Endpoints

Semua endpoint terdaftar sebagai Flask Blueprint dan tersedia di root URL CTFd.

### GET `/avatars/<type>/<id>`

Menampilkan gambar avatar.

| Parameter | Tipe | Deskripsi |
|-----------|------|-----------|
| `type` | string | `user` atau `team` |
| `id` | integer | ID user atau team |

**Response:**
- `200` — Gambar avatar (cache 5 menit)
- `400` — Type bukan `user`/`team`
- `404` — Tidak ada avatar yang diupload

---

### POST `/avatars/user/upload`

Upload avatar untuk user yang sedang login.

**Auth:** Required (login)

**Body:** `multipart/form-data`

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `avatar` | file | File gambar (max 2MB, format: png/jpg/gif/webp) |
| `nonce` | string | CSRF nonce dari `Session.nonce` |

**Response:**
```json
// Sukses
{ "success": true, "url": "/avatars/user/1" }

// Gagal
{ "success": false, "errors": ["File too large. Max 2MB"] }
```

| Status | Kondisi |
|--------|---------|
| `200` | Upload berhasil |
| `400` | File tidak valid / tidak ada |
| `403` | Tidak terautentikasi |
| `503` | Storage tidak writable |

---

### POST `/avatars/team/upload`

Upload avatar untuk team. **Hanya captain** yang diizinkan.

**Auth:** Required (login, team captain)

**Body:** `multipart/form-data`

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `avatar` | file | File gambar (max 2MB, format: png/jpg/gif/webp) |
| `nonce` | string | CSRF nonce dari `Session.nonce` |

**Response:**
```json
// Sukses
{ "success": true, "url": "/avatars/team/5" }

// Gagal
{ "success": false, "errors": ["Only the team captain can change the avatar"] }
```

| Status | Kondisi |
|--------|---------|
| `200` | Upload berhasil |
| `400` | File tidak valid / bukan anggota team |
| `403` | Bukan captain / tidak terautentikasi |
| `503` | Storage tidak writable |

---

### POST `/avatars/user/delete`

Hapus avatar user yang sedang login.

**Auth:** Required (login)

**Body:** `multipart/form-data`

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `nonce` | string | CSRF nonce |

**Response:**
```json
{ "success": true }
```

---

### POST `/avatars/team/delete`

Hapus avatar team. **Hanya captain** yang diizinkan.

**Auth:** Required (login, team captain)

**Body:** `multipart/form-data`

| Field | Tipe | Deskripsi |
|-------|------|-----------|
| `nonce` | string | CSRF nonce |

**Response:**
```json
{ "success": true }
```

## Template Helpers

Plugin mendaftarkan helper global di Jinja2 yang bisa dipakai di semua template.

### `avatar_url(entity_type, entity_id, fallback_email=None)`

Mengembalikan URL avatar dengan fallback chain:

1. **Uploaded avatar** → `/avatars/{type}/{id}` (jika file ada di disk)
2. **Gravatar** → `https://www.gravatar.com/avatar/{md5}?d=identicon` (jika `entity_type == "user"` dan `fallback_email` disediakan)
3. **DiceBear identicon** → `https://api.dicebear.com/7.x/identicon/svg?seed={id}` (fallback terakhir)

**Contoh penggunaan di template:**

```html
<!-- Avatar user dengan Gravatar fallback -->
<img src="{{ avatar_url('user', user.id, user.email) }}" alt="Avatar">

<!-- Avatar team dengan DiceBear fallback -->
<img src="{{ avatar_url('team', team.id) }}" alt="Team Avatar">

<!-- Di sidebar -->
<img src="{{ avatar_url('user', Session.id, User.email) }}" alt="">
```

### `md5` Template Filter

Filter untuk hashing MD5, berguna untuk Gravatar URL manual:

```html
<img src="https://www.gravatar.com/avatar/{{ user.email | md5 }}?d=identicon">
```

## Integrasi dengan Theme

Untuk mengintegrasikan plugin ini dengan theme CTFd custom, perlu modifikasi pada:

### 1. Template yang menampilkan avatar

Ganti hardcoded avatar URL dengan `avatar_url()`:

```html
<!-- Sebelum -->
<img src="/themes/core/static/img/default-avatar.png">

<!-- Sesudah -->
<img src="{{ avatar_url('user', user.id, user.email) }}">
```

### 2. Halaman Settings (upload user avatar)

Tambahkan Alpine.js component `AvatarUpload` di `assets/js/settings.js`:

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

### 3. Halaman Team Private (upload team avatar)

Tambahkan Alpine.js component `TeamAvatarUpload` di `assets/js/teams/private.js` — sama seperti di atas tapi endpoint-nya `/avatars/team/upload` dan `/avatars/team/delete`.

### 4. Scoreboard (client-side avatar)

Untuk avatar di scoreboard yang di-render via JavaScript, gunakan endpoint langsung dengan `onerror` fallback:

```html
<img src="/avatars/user/${id}"
     onerror="this.src='https://api.dicebear.com/7.x/identicon/svg?seed=${id}'">
```

## Troubleshooting

| Problem | Penyebab | Solusi |
|---------|----------|-------|
| `OSError: Read-only file system` | `UPLOAD_FOLDER` mengarah ke path read-only | Set env var `UPLOAD_FOLDER` ke volume writable (contoh: `/var/uploads`) |
| Avatar tidak muncul | Plugin tidak terinstal | Pastikan `CTFd/plugins/avatars/__init__.py` ada |
| "Avatar uploads not available" (503) | Folder avatars tidak bisa dibuat | Cek permission folder `UPLOAD_FOLDER/avatars/` |
| Upload berhasil tapi gambar tidak update | Browser cache | Hard refresh (Ctrl+Shift+R) atau append `?cb=timestamp` |
| "Only the team captain can change the avatar" | Bukan captain team | Hanya captain yang bisa upload/hapus avatar team |
| Gravatar tidak muncul | Email belum terdaftar di Gravatar | Daftar di [gravatar.com](https://gravatar.com), atau akan tampil identicon default |

## Arsitektur

```
Plugin Load Flow:
─────────────────
CTFd startup
  └─ load(app)
       ├─ _ensure_avatars_dir()      # Buat folder sekali saat startup
       ├─ Register Blueprint         # 5 route endpoints
       ├─ Register avatar_url()      # Jinja2 template global
       └─ Register md5 filter        # Jinja2 template filter

Request Flow (avatar_url):
──────────────────────────
Template render
  └─ avatar_url('user', 1, 'user@email.com')
       ├─ find_avatar('user', 1)     # Cek file di disk
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

## Lisensi

Plugin ini merupakan bagian dari theme Wreckit CTFd dan mengikuti lisensi yang sama dengan CTFd.
