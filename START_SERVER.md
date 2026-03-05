# How to Start the Backend Server

## Quick Start

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or if that doesn't work:
   ```bash
   pip install Flask flask-cors
   ```

2. **Start the server:**
   ```bash
   python server.py
   ```

3. **You should see:**
   ```
   ==================================================
   Wellbeing Companion Backend Server
   ==================================================
   Database: wellbeing.db
   Server starting on http://localhost:8000
   API Base URL: http://localhost:8000/api
   ==================================================
   ```

4. **Keep the server running** - Don't close the terminal window!

5. **Open your web app** - The web app should now be able to connect.

## Troubleshooting

### "python is not recognized"
- Try `python3` instead of `python`
- Or install Python from python.org

### "pip is not recognized"
- Try `pip3` instead of `pip`
- Or use `python -m pip install Flask flask-cors`

### Port 8000 already in use
- Change the port in `server.py` (last line): `app.run(..., port=8001)`
- Then update `api-service.js` line 3 to match the new port

### Still getting "Failed to fetch"
1. Make sure the server is running (check the terminal)
2. Check that the API URL in `api-service.js` matches the server port
3. Open browser console (F12) and check for errors

## What the Server Does

- Creates a SQLite database (`wellbeing.db`) in the same folder
- Provides REST API endpoints for:
  - User login/registration
  - User management
  - Preferences (likes/dislikes)
  - Doctor notes
- Handles CORS so your web app can connect

## Database Location

The database file `wellbeing.db` will be created in the same folder as `server.py`.

