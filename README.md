\# Business Lead Collector



Business Lead Collector is a Django + React application for discovering businesses across supported categories near a selected location and collecting publicly available lead information.



\## Features



\- Search businesses by location, category and radius

\- Interactive OpenStreetMap

\- OpenStreetMap / Overpass business discovery

\- Google Places provider support
\- Optional experimental Playwright browser-search provider

\- Business address, phone, email and website information

\- Free website enrichment

\- Apollo.io manager / decision-maker enrichment

\- Bulk business enrichment

\- CSV export

\- Excel export

\- Provider settings

\- Secure backend API-key storage

\- Data coverage indicators

\- Business details view



\## Technology Stack



\### Backend

\- Python

\- Django

\- Django REST Framework

\- OpenStreetMap / Overpass API

\- Nominatim

\- Google Places API

\- Apollo API

\- OpenPyXL



\### Frontend

\- React

\- Vite

\- Leaflet

\- React Leaflet



\## Data Providers



\### OpenStreetMap

The default business provider.



No API key is required.



OpenStreetMap data may not contain complete contact information for every business.



\### Google Places

Optional provider for richer business information such as:



\- Address

\- Phone number

\- Website

\- Location information



A Google Places API key is required.



\### Apollo

Optional people-enrichment provider used to find business decision-makers.



An Apollo API key is required.



\## Environment Setup



Copy:



`backend/.env.example`



to:



`backend/.env`



Then configure the required environment variables.



Never commit the real `.env` file.



\## Backend Setup



cd backend



python -m venv venv



venv\\Scripts\\activate



pip install -r requirements.txt



python manage.py migrate



python manage.py runserver



Backend:



http://127.0.0.1:8000



\## Frontend Setup



cd frontend



npm install



npm run dev



Frontend:



http://localhost:5173



\## Testing



Backend:



python manage.py check



python manage.py test hotels



Frontend:



npm run lint



npm run build



\## Current Status



The application currently supports multi-category business discovery, mapping, enrichment, provider configuration, decision-maker enrichment and lead export.



OpenStreetMap works as the free/default provider.



Google Places and Apollo are optional providers and require API keys.



\## Security



API keys are handled by the Django backend and are not exposed directly to the React frontend.



Real `.env` files, virtual environments, databases, build files and Node modules are excluded from Git.

\## Optional Playwright Provider

The browser-search provider runs only in Django and requires a matching Chromium runtime:

`pip install -r backend/requirements.txt`

`python -m playwright install chromium`

Configure `PLAYWRIGHT_HEADLESS`, `PLAYWRIGHT_TIMEOUT` (milliseconds), and
`PLAYWRIGHT_MAX_RESULTS` in `backend/.env`. Browser automation against third-party
pages is experimental: page structure, rate limits, CAPTCHAs, blocking, availability,
and applicable terms may prevent searches. The provider does not bypass these controls.

