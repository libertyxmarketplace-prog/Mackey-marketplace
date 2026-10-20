# LX Marketplace

ER:LC creator marketplace.

## Start

Requires Python 3.10 or newer.

```bash
python server.py
```

Open http://localhost:8000

## Project files

- `server.py` — backend, authentication and API
- `index.html` — website pages
- `static/css/` — page styling
- `static/js/` — frontend behaviour
- `static/images/` — logos, backgrounds and other graphics
- `tests/` — automated tests
- `data/` — private account database and uploads (created when running)

## Tests

```bash
python -m unittest discover -s tests -v
```

## Before publishing

Configure hosting, HTTPS and security protections. Discord sign-in and paid checkout require additional integration. Do not upload the `data/` folder to a public repository.
