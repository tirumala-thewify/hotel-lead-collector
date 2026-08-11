\# Hotel Lead Collector



Hotel Lead Collector is a Django + React application for discovering hotels near a selected location and collecting publicly available lead information.



\## Features



\- Search hotels by location and radius

\- Interactive OpenStreetMap

\- OpenStreetMap / Overpass hotel discovery

\- Google Places provider support

\- Hotel address, phone, email and website information

\- Free website enrichment

\- Apollo.io manager / decision-maker enrichment

\- Bulk hotel enrichment

\- CSV export

\- Excel export

\- Provider settings

\- Secure backend API-key storage

\- Data coverage indicators

\- Hotel details view



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

The default hotel provider.



No API key is required.



OpenStreetMap data may not contain complete contact information for every hotel.



\### Google Places

Optional provider for richer hotel information such as:



\- Address

\- Phone number

\- Website

\- Location information



A Google Places API key is required.



\### Apollo

Optional people-enrichment provider used to find hotel decision-makers.



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



The application currently supports hotel discovery, mapping, enrichment, provider configuration, manager enrichment and lead export.



OpenStreetMap works as the free/default provider.



Google Places and Apollo are optional providers and require API keys.



\## Security



API keys are handled by the Django backend and are not exposed directly to the React frontend.



Real `.env` files, virtual environments, databases, build files and Node modules are excluded from Git.

