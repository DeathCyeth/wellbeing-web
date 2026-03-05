# Quick Fix for "Failed to Fetch" Error

## The Problem
"Failed to fetch" means your web app cannot connect to your backend server.

## Quick Solutions

### 1. Check if Your Backend Server is Running

**For Python/Flask:**
```bash
# Check if Flask server is running
# Usually runs on port 5000 or 8000
```

**For Node.js/Express:**
```bash
# Check if Node server is running
# Usually runs on port 3000 or 8000
```

**To check what's running:**
- Open Task Manager (Ctrl+Shift+Esc)
- Look for Python, Node, or your backend process
- Or check the terminal where you started your backend

### 2. Update the API URL

Open `api-service.js` and check line 3:

```javascript
const API_BASE_URL = 'http://localhost:8000/api';
```

**Common backend URLs:**
- Flask (Python): `http://localhost:5000/api` or `http://127.0.0.1:5000/api`
- Express (Node.js): `http://localhost:3000/api` or `http://localhost:8000/api`
- Django (Python): `http://localhost:8000/api`
- FastAPI (Python): `http://localhost:8000/api`

**Change it to match your backend!**

### 3. Start Your Backend Server

If your backend isn't running, start it:

**Flask:**
```bash
python app.py
# or
flask run
```

**Express:**
```bash
node server.js
# or
npm start
```

**Django:**
```bash
python manage.py runserver
```

### 4. Test the Connection

1. Open the web app in your browser
2. On the login screen, click **"Test Server Connection"** button
3. This will tell you if the server is reachable

### 5. Check Browser Console

1. Press **F12** to open Developer Tools
2. Go to **Console** tab
3. Try to log in
4. Look for error messages - they will tell you exactly what's wrong

### 6. Common Issues

**CORS Error:**
- Your backend needs to allow requests from your web app
- Add CORS headers to your backend

**Wrong Port:**
- Make sure the port in `api-service.js` matches your backend port

**Backend Not Running:**
- Start your backend server first, then open the web app

## Still Having Issues?

1. Check what port your backend is actually running on
2. Update `API_BASE_URL` in `api-service.js` to match
3. Make sure your backend server is running
4. Check the browser console (F12) for detailed error messages

