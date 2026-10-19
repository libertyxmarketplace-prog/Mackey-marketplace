# LX Marketplace

A self-hosted marketplace for community-made ER:LC digital assets.

## Start

Install Python 3.10 or newer, then run:

```bash
python server.py
```

Open http://localhost:8000. The database and uploaded files are saved in `data/`. Back up that folder before updating.

## Features

Accounts, profile pictures, creator uploads, listing images, livery codes, department filters, saved listings, and free asset claims/downloads. New installs start with no listings.

## Limitations

Paid checkout and Discord login are not connected. This is a local self-hosted application, not a security-audited public deployment. For public hosting, add HTTPS, CSRF protection, rate limits, moderation, backup automation, and a supported production server.

## Tests

Run `python -m unittest discover -s tests -v`.
