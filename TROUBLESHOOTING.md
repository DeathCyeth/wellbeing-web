# Troubleshooting Guide

## Common Issues and Solutions

### Issue: "Invalid username or password" on login

**Possible Causes:**
1. API endpoint doesn't match your backend
2. Request format is incorrect
3. Backend expects different field names
4. CORS issues preventing the request

**How to Debug:**
1. Open your browser's Developer Tools (Press F12)
2. Go to the "Console" tab
3. Try to log in
4. Look for messages starting with "API Request:" and "API Response:"
5. Check what URL is being called and what response you're getting

**Solutions:**
- If you see a 404 error, the endpoint is wrong. Check `api-service.js` and update the endpoint
- If you see a CORS error, your backend needs to allow requests from your web app
- If the response format is different, check the console logs to see what the backend is actually returning

### Issue: "Username already taken" when creating account

**Possible Causes:**
1. The username actually exists in the database
2. The API is returning a different error format
3. The endpoint for registration is incorrect

**How to Debug:**
1. Open Developer Tools (F12) → Console tab
2. Try to register
3. Check the "API Request:" and "API Response:" logs
4. Look at the actual error message from the server

**Solutions:**
- If the error says the username exists, try a different username
- If you see a different error message, the backend might be using different error formats
- Check if the registration endpoint matches your backend (might be `/register` instead of `/users`)

### Issue: Can't connect to server

**Possible Causes:**
1. Backend server is not running
2. Wrong API URL
3. Network/firewall issues

**How to Debug:**
1. Check if your backend server is running
2. Verify the API URL in `api-service.js` (line 3)
3. Try accessing the API URL directly in your browser (e.g., `http://localhost:8000/api/health`)

**Solutions:**
- Start your backend server
- Update the `API_BASE_URL` in `api-service.js` to match your server
- Check firewall settings

## Step-by-Step Debugging

### 1. Check API URL
Open `api-service.js` and verify line 3:
```javascript
const API_BASE_URL = 'http://localhost:8000/api';
```
Change this to match your actual backend URL.

### 2. Check Browser Console
1. Open the web app in your browser
2. Press F12 to open Developer Tools
3. Go to the "Console" tab
4. Try to log in or register
5. Look for:
   - "API Request:" - shows what URL and data is being sent
   - "API Response:" - shows what the server returned
   - Any red error messages

### 3. Test API Endpoints Directly
You can test your API endpoints using:
- Browser: Navigate to the URL (for GET requests)
- Postman or similar tool
- curl command:
  ```bash
  curl -X POST http://localhost:8000/api/users/login \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"test"}'
  ```

### 4. Common API Endpoint Variations

Your backend might use different endpoints. Common variations:

**Login:**
- `/api/users/login` (current)
- `/api/login`
- `/api/auth/login`
- `/login`

**Registration:**
- `/api/users` (current)
- `/api/register`
- `/api/auth/register`
- `/register`

To change endpoints, edit `api-service.js`:
- Line 77: Change `/users/login` to your login endpoint
- Line 93: Change `/users` to your registration endpoint

### 5. Check Response Format

The backend might return data in a different format. Check the console logs to see the actual response structure, then update the code accordingly.

For example, if the backend returns:
```json
{
  "success": true,
  "data": {
    "username": "test",
    "name": "Test User",
    "role": "Patient"
  }
}
```

You would need to update the `getUser` function to return `response.data` instead of `response`.

### 6. CORS Issues

If you see CORS errors in the console, your backend needs to allow cross-origin requests.

**For Express.js (Node.js):**
```javascript
const cors = require('cors');
app.use(cors());
```

**For Flask (Python):**
```python
from flask_cors import CORS
CORS(app)
```

**For Django (Python):**
```python
# Install django-cors-headers
# Add to settings.py:
INSTALLED_APPS = [
    ...
    'corsheaders',
]
MIDDLEWARE = [
    ...
    'corsheaders.middleware.CorsMiddleware',
]
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",  # Your web app URL
]
```

## Getting Help

When asking for help, provide:
1. The error message you see
2. Browser console logs (API Request/Response)
3. Your backend API URL
4. What backend framework you're using (if known)
5. The actual API endpoint structure your backend uses

