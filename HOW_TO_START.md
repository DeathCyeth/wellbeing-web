# How to Start the Server - Step by Step

## The Problem
You're getting "Cannot connect to server" because the backend server isn't running.

## Solution: Start the Server

### Option 1: Using the Batch File (Easiest)

1. **Double-click** `start-server.bat` in the `wellbeing-web` folder
2. A black window will open showing the server starting
3. **Keep that window open** - don't close it!
4. You should see:
   ```
   ==================================================
   Wellbeing Companion Backend Server
   ==================================================
   Server starting on http://localhost:8000
   ==================================================
   ```

### Option 2: Using PowerShell/Command Prompt

1. Open PowerShell or Command Prompt
2. Navigate to the folder:
   ```bash
   cd C:\Users\Jamie\wellbeing-web
   ```
3. Start the server:
   ```bash
   python server.py
   ```
4. **Keep the window open** - the server must keep running!

### Verify It's Working

1. Open your web app in a browser
2. Click the **"Test Server Connection"** button on the login screen
3. You should see: "✓ Server connection successful!"

## Important Notes

- ✅ **The server MUST be running** whenever you use the web app
- ✅ **Don't close the server window** - keep it open
- ✅ The server runs on `http://localhost:8000`
- ✅ The database (`wellbeing.db`) will be created automatically

## Troubleshooting

### "python is not recognized"
- Try `python3` instead
- Or install Python from python.org

### "No module named 'flask'"
Run this command:
```bash
pip install Flask flask-cors
```

### Port 8000 already in use
- Another program is using port 8000
- Close other programs or change the port in `server.py` (last line)

### Still can't connect?
1. Make sure the server window is open and shows "Running on..."
2. Check the API URL in `api-service.js` is `http://localhost:8000/api`
3. Open browser console (F12) and look for error messages

## Quick Test

Once the server is running, you can test it by opening this URL in your browser:
```
http://localhost:8000/api/health
```

You should see: `{"status":"ok"}`

