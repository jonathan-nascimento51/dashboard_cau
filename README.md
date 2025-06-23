# Dash GLPI Dashboard

This project provides a simple [Dash](https://dash.plotly.com/) application that consumes data from a GLPI instance and displays ticket metrics.

## Installation

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd dashboard_cau
   ```
2. **Create a virtual environment and install dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure environment variables**
   Copy `env.example` to `.env` and fill in your credentials:
   ```bash
   cp env.example .env
   ```
   Example snippet:
   ```env
   GLPI_URL=http://your-glpi-url.example/api/
   APP_TOKEN=your-app-token
   USER_TOKEN=your-user-token
   ```
   See `env.example` for the full list and details.

## Running the application

With the virtual environment activated and the `.env` file configured, run:
```bash
python app.py
```
The Dash server will start on `http://localhost:8050` by default.

## Notes
* The application expects valid credentials for a GLPI API instance.
* Additional environment variables may be used internally; refer to the source code if customisation is required.