# FACE.IT backend

Django 5.2 + Django REST Framework API for a university attendance system that
verifies students by face. It serves the React admin
([visages-attend-manager](../visages-attend-manager)) and the Android
attendance app.

- **Face engine:** dlib ResNet embeddings (the model behind `face_recognition`),
  128-d vectors, HOG detection, behind [`core/face_engine.py`](core/face_engine.py).
- **Auth:** JWT (SimpleJWT). Roles: `superadmin`, `staff`, `teacher`.
- **Docs:** OpenAPI schema at `/api/schema/`, Swagger UI at `/api/docs/`.
- **Runs on:** Linux, macOS and Windows with Python 3.11/3.12, or anywhere via Docker.
  No C++ compiler or CMake needed: dlib comes from the prebuilt `dlib-bin` wheel.

## Quick start (local Python)

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate      Linux/macOS:  source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env          # Windows: copy .env.example .env  (then set SECRET_KEY)
python manage.py migrate
python manage.py seed_demo    # optional demo data, users admin / staff1 / teacher1 (password FaceIt!2026)
python manage.py runserver 0.0.0.0:8000
```

Open http://localhost:8000/api/docs/ and authorise with a token from `POST /api/auth/login/`.
To create your own admin instead of the demo one: `python manage.py createsuperuser`.

## Quick start (Docker)

```bash
docker compose up --build        # API on :8000, Postgres in a volume, demo data seeded
docker compose down              # stop (data kept); add -v to wipe it
```

Set `SEED_DEMO=0` to skip demo data. Compose reads `SECRET_KEY`, `DEBUG`,
`ALLOWED_HOSTS` and the CORS/CSRF origins from your `.env`.

## Running with the admin frontend

```bash
# terminal 1 (this repo)
python manage.py runserver 0.0.0.0:8000
# terminal 2 (../visages-attend-manager)
cp .env.example .env          # VITE_API_URL=http://localhost:8000/api
npm install && npm run dev    # http://localhost:8080
```

Sign in with a demo user (`admin`, `staff1`, `teacher1`; password `FaceIt!2026`
after `seed_demo`). Face check-in lives under **Recognition**: choose a course,
start the session, and allow camera access. Browsers only grant the camera on
`localhost` or HTTPS, so use a tunnel or certificate when the UI is opened from
another device.

## Moving between machines / operating systems

- Everything OS-specific is in `.env` (never committed). Copy `.env` **together
  with** `db.sqlite3`: face encodings are encrypted with `SECRET_KEY`.
- If you must change `SECRET_KEY` on an existing database:
  `python manage.py rotate_encryption_key --old-secret-key '<old key>'`.
- Line endings are normalised by `.gitattributes`, so a checkout behaves the same on Windows and Linux.
- Docker gives an identical runtime everywhere (verified: same recognition scores in the Linux container and on Windows).

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | none (required unless `DEBUG=True`) | Django signing key; also encrypts stored face encodings |
| `DEBUG` | `False` | Debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hosts (add your LAN IP for phones) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:8080` | Browser origins allowed to call the API (Vite dev server) |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8080` | Origins trusted for CSRF (admin forms) |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Any `dj-database-url` style URL, e.g. `postgres://user:pass@host:5432/db` |
| `FACE_MATCH_THRESHOLD` | `0.6` | Max face distance for a match; lower = stricter. Calibrate with `evaluate_recognition` |
| `FACE_DETECTION_MODEL` | `hog` | `hog` (CPU) or `cnn` (more accurate, slow without GPU) |
| `EMAIL_BACKEND` | console | Django email backend |

## Tests

```bash
pytest            # 27 tests: auth, CRUD, roles, face engine, full session flow
```

The session tests enrol real faces (public-domain portraits in `core/tests/fixtures/`),
start a session, check in by photo, apply a manual override and end the session.

## Recognition research: benchmark and threshold calibration

```bash
python manage.py evaluate_recognition            # LFW benchmark (downloads ~180 MB once to datasets/)
python manage.py evaluate_recognition --quick    # 2 of 10 folds
python manage.py evaluate_recognition --dataset path/to/photos   # your own <person>/<image>.jpg set
```

It writes `reports/recognition_eval.md`, `.json` and charts (ROC, distance histograms,
threshold sweep, match latency). The admin UI reads it from `GET /api/recognition/report/`.
Reported: verification accuracy (LFW 10-fold protocol), ROC AUC, EER, FAR/FRR at the
current threshold, recommended balanced and secure (FAR ≤ 0.1%) thresholds, 1:N
identification (rank-1, false rejects, impostor acceptance), match latency from 10 to
100,000 enrolled faces, and operational statistics from your own attendance data
(manual-override rate, confidence distribution).

Why no model training: the embedding network is pretrained on ~3M faces. Enrolling a
student stores one embedding; recognition is a nearest-neighbour search over the course
roster. Nothing needs retraining when students join, which is what lets the system scale.

## Management commands

| Command | Purpose |
|---|---|
| `seed_demo [--password]` | Idempotent demo data (departments, courses, users, students, timetable) |
| `evaluate_recognition` | Benchmark + threshold calibration report |
| `rotate_encryption_key --old-secret-key` | Re-encrypt face encodings after changing `SECRET_KEY` |

## Roles

| Role | Can do |
|---|---|
| `superadmin` | Everything, including admin users, system and security settings, backups |
| `staff` | Manage departments, levels, courses, students, enrolment, timetable; read reports and audit logs |
| `teacher` | Read academics; see students, attendance and sessions only for courses they teach; run sessions and mark attendance for those courses |

## API

All routes are under `/api/`. Authenticate with `Authorization: Bearer <access>`.
Lists of students and attendance are paginated (`?page=`, `?page_size=` up to 500)
and return `{count, next, previous, results}`; other lists return plain arrays.
Attendance status is one of `present`, `late`, `absent`, `excused`.

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | `auth/login/` | `{username, password}` → `{access, refresh, user}` |
| POST | `auth/refresh/` | `{refresh}` → `{access, refresh}` |
| GET | `auth/user/` | Current user with `role` and `permissions` |

### Academics (router CRUD: GET list, POST, GET/PUT/PATCH/DELETE `<id>/`)
| Path | Extras |
|---|---|
| `departments/` | `?active_only=true`; `GET departments/<id>/stats/` |
| `specializations/` | `?department=` |
| `levels/` | `?active_only=true` |
| `courses/` | `?department= &level= &specialization= &search=`; `GET courses/<id>/students/`, `GET courses/<id>/attendance/`, `POST courses/<id>/enroll-students/` `{student_ids}` |

### Students
| Method | Path | Notes |
|---|---|---|
| GET/POST | `students/` | Paginated; `?department= &level= &specialization= &course= &status= &search=` |
| GET/PUT/PATCH/DELETE | `students/<id>/` | Never includes the face encoding; `face_enrolled` flag instead |
| POST | `students/<id>/enroll-face/` | multipart `image`; rejects no face, several faces, or a face already enrolled (409) |
| GET | `students/<id>/courses/` | |
| POST | `students/<id>/enroll-courses/` | `{course_ids}` |
| POST | `students/<id>/auto-assign-courses/` | By department/level/specialization |
| GET | `students/<id>/attendance-summary/` | Counts per status and per course |
| POST | `enrollment/student/` | `{student_id, course_ids}` |
| POST | `enrollment/bulk/` | `{course_ids, department_id?, specialization_id?, level_id?}` |

### Attendance
| Method | Path | Notes |
|---|---|---|
| GET/POST | `attendance/` | Paginated; `?course_id= &student_id= &status= &date= &date_from= &date_to=`; POST `{student, course, status, notes}` |
| GET/PUT/PATCH/DELETE | `attendance/<id>/` | Corrections |

### Sessions (Android contract: keep these paths and keys)
| Method | Path | Notes |
|---|---|---|
| POST | `sessions/start/` | `{course_id, duration_minutes?, grace_period_minutes?, room?}` → `{success, message, session_id, session}` |
| POST | `attendance/checkin/` | **No auth** (kiosk). multipart `session_id`, `image` → `{success, message, student_id, student_name, matric_number, status, check_in_time, confidence, distance, threshold}` |
| GET | `sessions/<session_id>/stats/` | `{success, stats}` |
| POST | `sessions/end/` | `{session_id}`; students who did not check in are marked absent |
| POST | `sessions/<session_id>/mark/` | Manual override `{student_id, status, notes?}` |
| GET | `sessions/` | `?status= &course=` |

These four Android routes are also served without the `/api/` prefix for older builds.

### Recognition
| Method | Path | Notes |
|---|---|---|
| POST | `register-student/` | Create student + enrol face in one call (multipart) |
| POST | `recognize-face/` | multipart `course_id`, `image`; marks today's attendance; returns `confidence`, `distance`, `threshold` |
| GET | `recognition/report/` | Latest benchmark report |

### Dashboard and analytics
`GET dashboard/stats/`, `analytics/departments/`, `analytics/courses/`, `analytics/teachers/` (teachers see their own courses only).

### Timetable
`timetable/entries/` (GET, POST), `timetable/entries/<id>/` (GET, PUT, PATCH, DELETE), `timetable/timeslots/`, `timetable/rooms/` (GET, POST), `timetable/teachers/`, `timetable/courses/` (GET).

### Administration (superadmin; staff can read)
| Path | Notes |
|---|---|
| `admin-users/` (GET), `admin-users/create/` (POST), `admin-users/<id>/` (PUT, PATCH, DELETE = deactivate), `admin-users/<id>/delete/` | |
| `security/activities/`, `security/login-attempts/`, `security/active-sessions/`, `security/statistics/` | `?days=` |
| `security/settings/`, `security/settings/update/`, `security/sessions/<key>/terminate/` | |
| `system/stats/`, `system/settings/`, `system/settings/update/`, `system/test-email/`, `system/backup/create/`, `system/backups/` | Backups are JSON dumps in `backups/` |

Legacy flat lists `get-students/` and `get-attendance/` remain for old clients.

## Biometric data

Uploaded photos are processed in memory and discarded. Only the 128-d encoding is
stored, encrypted at rest (`django-cryptography`). Encodings are never returned by the
API and never logged. No endpoint serves enrolment photos.

## Project layout

```
core/
  face_engine.py      single recognition engine (encode / match)
  evaluation.py       benchmark metrics used by evaluate_recognition
  permissions.py      role checks
  views/              auth, academics, students, attendance, sessions,
                      recognition, timetable, security, system
  management/commands seed_demo, evaluate_recognition, rotate_encryption_key
  tests/              pytest suite + fixture photos
face_backend/         settings (env-driven) and root URLs
scripts/              older data-population scripts
```
