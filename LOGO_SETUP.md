# Logo Setup Instructions

## How to Add Your Logo

1. **Place your logo image** in the `wellbeing-web` folder
2. **Name it `logo.png`** (or update the filename in the code)
3. **Refresh your browser** - the logo will appear automatically!

## Supported Formats

- PNG (recommended - supports transparency)
- JPG/JPEG
- SVG (scalable vector graphics)
- GIF

## Logo Locations

Your logo will appear in two places:
1. **Login/Register screen** - Main logo at the top
2. **AI Companion section** - Smaller logo next to "AI Companion" heading

## Customizing Logo Size

If you need to adjust the logo size, edit `styles.css`:

**Main Logo (Login screen):**
```css
.main-logo {
    width: 64px;  /* Change this */
    height: 64px; /* Change this */
}
```

**AI Companion Logo:**
```css
.ai-logo {
    width: 48px;  /* Change this */
    height: 48px; /* Change this */
}
```

## Using a Different Filename

If your logo has a different name (e.g., `my-logo.png`), update these files:

**In `index.html`**, find and replace:
- `src="logo.png"` → `src="my-logo.png"`

## Tips

- **Transparent background**: Use PNG with transparency for best results
- **Square images work best**: The logos are displayed in square containers
- **File size**: Keep images under 500KB for fast loading
- **Resolution**: 200x200px to 400x400px is ideal

## Troubleshooting

**Logo not showing?**
- Check the filename matches exactly (case-sensitive on some systems)
- Make sure the file is in the `wellbeing-web` folder
- Check browser console (F12) for errors
- Try a different image format (PNG recommended)

**Logo too big/small?**
- Adjust the width/height in `styles.css` (see above)

**Logo looks blurry?**
- Use a higher resolution image
- Make sure it's not being stretched

