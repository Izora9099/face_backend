# Face Backend Project

## Overview

This project is a Django-based backend application designed for student attendance management using facial recognition. It allows for student registration with face data and subsequent attendance marking by comparing live images with registered faces.

## Prerequisites

Before you begin, ensure you have met the following requirements:
* Python (3.8 or higher recommended)
* pip (Python package installer)
* virtualenv (for creating isolated Python environments)

## Setup and Installation

Follow these steps to get your development environment set up:

### 1. Install Python

If you don't have Python installed, download and install it from [python.org](https://www.python.org/downloads/). Ensure that Python and pip are added to your system's PATH.

You can verify your Python installation by running:
```bash
python --version
pip --version
```

### 2. Create and Activate a Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies.

**On macOS and Linux:**
```bash
# Install virtualenv if you haven't already
pip install virtualenv

# Navigate to your project directory
cd path/to/your/face_backend

# Create a virtual environment (e.g., named 'venv')
python -m venv venv
# or
# virtualenv venv

# Activate the virtual environment
source venv/bin/activate
```

**On Windows:**
```bash
# Install virtualenv if you haven't already
pip install virtualenv

# Navigate to your project directory
cd path\to\your\face_backend

# Create a virtual environment (e.g., named 'venv')
python -m venv venv
# or
# virtualenv venv

# Activate the virtual environment
.\venv\Scripts\activate
```
You'll know the virtual environment is active when you see `(venv)` at the beginning of your command prompt.

### 3. Install Dependencies

This project uses Django and other libraries for facial recognition. Install them using pip:

```bash
pip install Django face_recognition numpy
```
**Note:** The `face_recognition` library depends on `dlib` and `Pillow`. `dlib` might require system-level dependencies (like CMake and a C++ compiler) to be installed first. Please refer to the [dlib installation guide](http://dlib.net/compile.html) and [face_recognition installation guide](https://github.com/ageitgey/face_recognition#installation) for more details, especially if you encounter issues during `pip install face_recognition`.

(TODO: It is highly recommended to create a `requirements.txt` file for easier dependency management: `pip freeze > requirements.txt`)

### 4. Apply Migrations

Once Django is installed, apply the database migrations:
```bash
python manage.py migrate
```

## Running the Development Server

To start the Django development server:
```bash
python manage.py runserver
```
By default, the server will run on `http://127.0.0.1:8000/`. You can access the application by opening this URL in your web browser.

## Project Structure

The project is organized as follows:

*   **`face_backend/`**: This is the main Django project directory.
    *   [`face_backend/settings.py`](face_backend/settings.py): Contains all the project settings, such as database configuration, installed apps, middleware, static files, etc.
    *   [`face_backend/urls.py`](face_backend/urls.py): The main URL configuration for the project. It includes URL patterns from other apps.
    *   [`face_backend/wsgi.py`](face_backend/wsgi.py): Entry-point for WSGI-compatible web servers to serve your project.
    *   [`face_backend/asgi.py`](face_backend/asgi.py): Entry-point for ASGI-compatible web servers.
*   **`core/`**: This Django app handles the core functionalities of the application, including student registration, face encoding, and attendance tracking.
    *   [`core/models.py`](core/models.py): Defines the database models: `Student` (stores student information and face encodings) and `AttendanceRecord` (stores attendance logs).
    *   [`core/views.py`](core/views.py): Contains the view logic for handling API requests related to student registration and attendance.
    *   [`core/urls.py`](core/urls.py): URL configurations specific to the `core` app.
    *   [`core/admin.py`](core/admin.py): Registers models with the Django admin interface.
    *   [`core/apps.py`](core/apps.py): Configuration for the `core` app.
    *   [`core/migrations/`](core/migrations/): Directory storing database migration files.
*   **[`manage.py`](manage.py)**: A command-line utility that lets you interact with this Django project in various ways (e.g., running the development server, creating migrations).
*   **[`db.sqlite3`](db.sqlite3)**: The default SQLite database file used for development.
*   **`debug_*.jpg`**: Image files saved for debugging purposes during student registration. These are not part of the core application logic and can be ignored or cleaned up.

## Key Components & API Endpoints

The `core` app provides the following functionalities and API endpoints. All API endpoints are prefixed with `/api/`.

### Models
(Defined in [`core/models.py`](core/models.py))

*   **`Student`**:
    *   `name`: `CharField` - The name of the student.
    *   `matric_number`: `CharField` (unique) - The student's matriculation number.
    *   `face_encoding`: `BinaryField` - Stores the binary representation of the student's facial encoding.
    *   `registered_on`: `DateTimeField` - Timestamp of when the student was registered.
*   **`AttendanceRecord`**:
    *   `student`: `ForeignKey` to `Student` - The student for whom attendance is recorded.
    *   `timestamp`: `DateTimeField` - Timestamp of when the attendance was recorded.
    *   `status`: `CharField` - Status of the attendance (e.g., "Present").

### API Endpoints / Views
(Logic defined in [`core/views.py`](core/views.py), URLs in [`core/urls.py`](core/urls.py) and [`face_backend/urls.py`](face_backend/urls.py))

*   **`POST /api/register/`**
    *   **View:** [`register_student`](core/views.py:12)
    *   **Description:** Registers a new student. Expects `name`, `matric_number`, and an `image` file in the POST request. The image is processed to extract facial encodings.
    *   **Request Body (form-data):**
        *   `name` (string): Student's name.
        *   `matric_number` (string): Student's matriculation number.
        *   `image` (file): Image file containing the student's face.
    *   **Responses:**
        *   `200 OK`: Student registered successfully.
        *   `400 Bad Request`: Missing fields or no face found in the image.
        *   `405 Method Not Allowed`: If not a POST request.
        *   `409 Conflict`: Student with the given matric number already exists.
        *   `500 Internal Server Error`: Server-side error during processing.

*   **`POST /api/attendance/`**
    *   **View:** [`take_attendance`](core/views.py:72)
    *   **Description:** Marks attendance for a student. Expects an `image` file in the POST request. The face in the image is compared against registered students.
    *   **Request Body (form-data):**
        *   `image` (file): Image file containing a face for attendance.
    *   **Responses:**
        *   `200 OK`: Attendance recorded successfully for a recognized student.
        *   `400 Bad Request`: No image provided.
        *   `404 Not Found`: No face found in the image, or face not recognized among registered students.
        *   `500 Internal Server Error`: Server-side error during processing.

*   **`POST /api/post/`**
    *   **View:** [`post_student_data`](core/views.py:101)
    *   **Description:** Saves basic student information (`name`, `matric_number`) without an initial face scan. The `face_encoding` field is left empty. This might be used for a two-step registration process.
    *   **Request Body (form-data):**
        *   `name` (string): Student's name.
        *   `matric_number` (string): Student's matriculation number.
    *   **Responses:**
        *   `200 OK`: Student info saved.
        *   `400 Bad Request`: Missing fields or student already exists.

*   **`GET /api/notify/`**
    *   **View:** [`notify`](core/views.py:120)
    *   **Description:** A simple notification endpoint. Returns a JSON message. Can accept an optional `message` query parameter.
    *   **Query Parameters:**
        *   `message` (string, optional): Custom message to be echoed.
    *   **Responses:**
        *   `200 OK`: Returns a JSON object with `status: 'info'` and the message.

### URLs
*   Project-level URLs are defined in [`face_backend/urls.py`](face_backend/urls.py), which includes `core.urls` under the `/api/` prefix.
*   App-level URLs for the `core` app are in [`core/urls.py`](core/urls.py).

## Creating a Superuser (Admin User)

To access the Django admin interface, you'll need to create a superuser:
```bash
python manage.py createsuperuser
```
Follow the prompts to set a username, email, and password.

Once created, you can access the admin panel at `http://127.0.0.1:8000/admin/`. Through the admin interface, you can:
*   Manage **Students**: View, add, edit, and delete student records. The list view displays student names, matriculation numbers, and registration dates.
*   Manage **Attendance Records**: View, add, edit, and delete attendance records. The list view displays the associated student, timestamp, and attendance status.

## Running Tests

To run the automated tests for the project (if any are defined in [`core/tests.py`](core/tests.py)):
```bash
python manage.py test
```

## Deployment to Production

Deploying a Django application to production involves several steps and considerations beyond the scope of the development server (`runserver`). Here's a general outline:

1.  **Choose a Web Server:** Use a production-grade web server like Gunicorn or uWSGI.
2.  **WSGI/ASGI:** Configure your web server to communicate with your Django application via WSGI (e.g., using [`face_backend/wsgi.py`](face_backend/wsgi.py)) or ASGI.
3.  **Static Files:** Configure serving of static files (CSS, JavaScript, images). Run `python manage.py collectstatic` to gather all static files into a single directory.
4.  **Database:** Use a robust production database (e.g., PostgreSQL, MySQL) instead of SQLite. Update [`face_backend/settings.py`](face_backend/settings.py) accordingly.
5.  **Security:**
    *   Set `DEBUG = False` in [`face_backend/settings.py`](face_backend/settings.py).
    *   Configure `ALLOWED_HOSTS` in [`face_backend/settings.py`](face_backend/settings.py).
    *   Set a strong `SECRET_KEY` and keep it confidential.
    *   Use HTTPS.
6.  **Environment Variables:** Store sensitive information (like `SECRET_KEY`, database credentials) in environment variables, not in the codebase.
7.  **Process Manager:** Use a process manager like Supervisor or systemd to manage your application server.

Example with Gunicorn:
```bash
# Install Gunicorn
pip install gunicorn

# Run Gunicorn (replace 'face_backend.wsgi' if your project name is different)
gunicorn face_backend.wsgi:application --bind 0.0.0.0:8000
```

(TODO: Add more specific deployment instructions if a particular platform or setup is intended, e.g., Docker, Heroku, AWS).

## Generating `requirements.txt`

It is good practice to have a `requirements.txt` file to list all project dependencies. You can generate it after installing all necessary packages in your virtual environment:
```bash
pip freeze > requirements.txt
```
Then, others (or your future self) can install all dependencies with:
```bash
pip install -r requirements.txt
```
This replaces the need to `pip install Django face_recognition numpy` individually. Remember to update this file if you add more dependencies.

## Contributing

If you'd like to contribute to this project, please follow these general guidelines:
1. Fork the repository.
2. Create a new feature branch (`git checkout -b feature/your-feature-name`).
3. Make your changes and commit them with clear messages.
4. Ensure your code adheres to any existing style guidelines.
5. If adding new features, include or update tests.
6. Push your branch to your fork (`git push origin feature/your-feature-name`).
7. Create a Pull Request against the main repository's `main` or `master` branch.

## License

(TODO: Specify the license for this project. If unsure, MIT is a common and permissive choice for open-source projects.)
Example: This project is licensed under the MIT License - see the LICENSE.md file for details (if you create one).