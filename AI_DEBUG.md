# AI Chat Debugging Guide

## How to Debug AI Issues

### Step 1: Open Browser Console
1. Press **F12** to open Developer Tools
2. Go to the **Console** tab
3. Try to use the AI chat
4. Look for error messages

### Step 2: Check for Common Issues

#### Issue: "AI form elements not found"
**Solution:** Refresh the page. The form might not have loaded properly.

#### Issue: "No current user found"
**Solution:** Log out and log back in.

#### Issue: "OpenAI API key not configured"
**Solution:** 
1. Make sure you've set the `OPENAI_API_KEY` environment variable
2. Restart your Flask server after setting it
3. Check `AI_SETUP.md` for instructions

#### Issue: "Empty response from AI service"
**Solution:** 
- Check your OpenAI API key is valid
- Check you have credits in your OpenAI account
- Check the server console for errors

#### Issue: Network errors
**Solution:**
- Make sure your Flask server is running
- Check the API URL in `api-service.js` is correct
- Check browser console for CORS errors

### Step 3: Check Server Logs

Look at your Flask server terminal window for error messages. Common errors:
- `OpenAI API error: ...` - API key or request issue
- `500 Internal Server Error` - Server-side error
- Connection refused - Server not running

### Step 4: Test API Directly

You can test the AI endpoint directly using curl or Postman:

```bash
curl -X POST http://localhost:8000/api/ai/advice \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Hello",
    "user_name": "Test User",
    "likes": "",
    "dislikes": "",
    "notes": [],
    "conversation_history": []
  }'
```

### What to Look For

**In Browser Console:**
- `Getting AI advice:` - Shows the question being sent
- `Calling AI API with:` - Shows the data being sent
- `AI API response:` - Shows what the server returned
- Any red error messages

**In Server Console:**
- `OpenAI API error:` - API-related errors
- `AI service error:` - General AI errors
- Any Python tracebacks

### Quick Fixes

1. **Clear browser cache** - Ctrl+Shift+Delete
2. **Hard refresh** - Ctrl+Shift+R
3. **Restart Flask server** - Stop and start again
4. **Check OpenAI API key** - Verify it's set correctly
5. **Check server is running** - Make sure Flask server is active

### Still Not Working?

Share these details:
1. Browser console errors (F12 → Console)
2. Server console errors (Flask terminal)
3. What happens when you click "Send" (does it show loading? error? nothing?)
4. Your OpenAI API key status (is it set? valid?)

