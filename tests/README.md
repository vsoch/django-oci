## Example Project for django_oci

This example is provided as a convenience feature to allow potential users to 
try out Django OCI straight from the app repo without having to create a django project.
It can also be used to develop django OCI in place.

**Important** the secret key is hard coded into [settings.py](settings.py).
You should obviously generate a new one for your project, and not add it to version control.

To run this example, follow these instructions:

1. Navigate to the `tests/example` directory
2. Install the requirements for the package:
		
```bash
pip install -r requirements.txt
```	

3. Make and apply migrations

```bash
python manage.py makemigrations
python manage.py migrate
```
	
4. Run the server

```bash
python manage.py runserver
```
		
5. Access from the browser at `http://127.0.0.1:8000`
