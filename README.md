# Prime Academy Backend

Minimal README listing the currently available API endpoints and a short explanation for each.

Requirements
------------
- Python 3.11

How to view API schema and docs
--------------------------------
- OpenAPI JSON (drf-spectacular): /schema/ (publicly accessible)
- Swagger UI: /api/docs/ (interactive docs; use "Authorize" to provide Bearer token if you want to try protected endpoints)

Authentication
--------------
- This project uses JWT (djangorestframework-simplejwt). Use the token endpoints to obtain tokens and include them as the Authorization header: "Authorization: Bearer <access_token>".
- To generate a static schema file locally you can run:

```bash
python manage.py spectacular --file schema.yml
```

- Common troubleshooting when schema is missing or incomplete:
	- The schema endpoint requires authentication (ensure it's publicly accessible) — it is configured publicly in `core/urls.py`.
	- Views that return dicts without serializers need `@extend_schema` annotations.
	- Import-time errors can prevent schema generation; run the `spectacular` command to see tracebacks.


### Backend Developer Instructions: Using Image Optimization


```python
IMAGE_FIELDS_OPTIMIZATION = {
    'image': {
        'max_size': (300, 300),       # Maximum dimensions
        'min_size': (100, 100),       # Minimum dimensions (optional)
        'max_bytes': 300*1024,        # Maximum: 300 KB
        'min_bytes': 50*1024,         # Minimum: 50 KB (skip optimization if smaller)
        'max_upload_mb': 5            # Maximum upload size before processing
    }
}
```

* **`max_size`**: Maximum width and height for the image.
* **`min_size`**: Minimum width and height (optional).
* **`max_bytes`**: Maximum file size after optimization.
* **`min_bytes`**: Skip further compression if already smaller.
* **`max_upload_mb`**: Maximum file size allowed for upload before optimization.

