# Deploying Auditoria Inteligente to Streamlit Community Cloud

Streamlit Community Cloud offers free hosting for Streamlit applications with no credit card required. This guide outlines the steps to deploy your application.

## Prerequisites

1. **GitHub Account** - You'll need a public repository (free tier requires public repos)
2. **Git** installed locally (for pushing code)
3. Your application files ready

## Step-by-Step Deployment Guide

### 1. Prepare Your Repository

Your application is mostly ready, but ensure these files are in your repo:

```
Auditoria/
├── app.py
├── requirements.txt
├── README.md (optional but recommended)
├── ArquivosPDF/ (directory for PDFs - note: files won't persist between sessions)
├── divergentes_imgs/ (directory for images)
├── documentos_nf/ 
├── notas_fiscais/
├── pwa/
└── [your data files: .csv, .xlsx, etc.]
```

### 2. Important Considerations for Streamlit Cloud

#### File Persistence
- **IMPORTANT**: Streamlit Cloud instances are ephemeral - files written to disk don't persist between sessions or after redeploy
- PDF uploads will work during a session but won't save permanently
- For persistent storage, you'd need to integrate with external storage (like Google Drive API, AWS S3, etc.)
- For your use case with 4 users, you can:
  - Work with data during sessions and download results
  - Or modify the app to use GitHub releases/data persistence (more complex)

#### Data Files
Your existing data files (.csv, .xlsx) in the repository will be available as read-only resources
- These are committed to Git and will be available to your app
- If users need to upload new data that should persist, consider:
  - Having users download/upload data each session
  - Using Google Sheets as a backend (requires API setup)
  - Using Streamlit's session state for temporary data during a session

### 3. Deployment Steps

#### Option A: Using Streamlit Cloud Website (Recommended)

1. **Push your code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Streamlit Cloud deployment"
   git branch -M main
   git remote add origin https://github.com/yourusername/your-repo-name.git
   git push -u origin main
   ```

2. **Go to** [streamlit.io/cloud](https://streamlit.io/cloud)

3. **Sign in with GitHub**

4. **Click "New app"**

5. **Select your repository, branch (usually main), and main file path** (`app.py`)

6. **Click "Deploy!"**

7. **Wait for deployment** - Streamlit Cloud will:
   - Install dependencies from `requirements.txt`
   - Run `streamlit run app.py`
   - Provide you with a shareable URL

#### Option B: Using GitHub Actions (Alternative)

Create `.github/workflows/streamlit.yml`:
```yaml
name: Deploy to Streamlit Cloud

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: streamlit/cloud-action@main
      with:
        # Optional: specify branch and main file
        # branch: main
        # main_file_path: app.py
```

### 4. Required Files Checklist

Ensure these are in your repository:

- [x] `app.py` - Main Streamlit application
- [x] `requirements.txt` - Python dependencies
- [ ] `packages.txt` - Only needed if you have system-level dependencies (you don't appear to)
- [ ] `.streamlit/config.toml` - Optional for custom configuration
- [x] README.md - Helpful for users

Your `requirements.txt` looks good:
```
pandas
streamlit
plotly
PyMuPDF
pytesseract
Pillow
openpyxl
```

### 5. Application-Specific Notes

#### Authentication
Your app has built-in username/password authentication using environment variables:
- `APP_USERNAME` (default: admin)
- `APP_PASSWORD` (default: admin123)
- `APP_USERS` for additional users

**For Streamlit Cloud:**
You'll need to set these as secrets in the Streamlit Cloud dashboard:
1. After deploying, go to your app's settings
2. Go to "Secrets" section
3. Add:
   - `APP_USERNAME`: your_desired_username
   - `APP_PASSWORD`: your_strong_password
   - `APP_USERS`: user1:pass1,user2:pass2 (optional)

#### AI Features
Your app uses OpenRouter/OpenAI for AI features:
- Requires `OPENAI_API_KEY` or `OPENROUTER_API_KEY` environment variable

**For Streamlit Cloud:**
Add as a secret:
- `OPENAI_API_KEY`: your_api_key_here
*(Get from https://openrouter.ai/ or https://platform.openai.com/)*

#### File Uploads
PDF upload functionality should work during sessions, but remember:
- Uploaded files won't persist after session ends or redeploy
- Consider adding a note in your app informing users to download results

### 6. Post-Deployment Configuration

After deployment:
1. Test all functionality
2. Set environment variables/secrets as needed
3. Share the URL with your 4 users
4. Consider adding usage instructions in your README

### 7. Limitations to Be Aware Of

- **Public Repository Required** (free tier): Your code will be visible
- **Sleeping**: App may sleep after inactivity, taking ~10-30 seconds to wake up
- **Resource Limits**: Shared CPU/memory (should be fine for 4 light users)
- **No Persistent Storage**: As mentioned above
- **Deployment Time**: ~2-5 minutes typically

### 8. Troubleshooting Tips

If deployment fails:
1. Check the logs in Streamlit Cloud dashboard
2. Common issues:
   - Missing dependencies in requirements.txt
   - Syntax errors in Python code
   - Large file sizes exceeding limits
   - Memory usage too high

### 9. Example Workflow for Your Users

1. Users visit your Streamlit Cloud URL
2. They log in using credentials you set via secrets
3. They upload PDFs for the current session
4. They run the audit
5. They view results and download any reports/visualizations
6. When session ends or they return later, they need to re-upload PDFs

### 10. Enhancing Persistence (Optional Advanced)

If you need true persistence beyond sessions, consider:
- Integrating with Google Drive API for PDF storage
- Using Firebase or Supabase for metadata
- Storing processed results in Google Sheets
- These would require additional API keys and code modifications

## Next Steps

1. Create a GitHub repository with your code
2. Push your initial commit
3. Deploy via streamlit.io/cloud
4. Configure secrets for authentication and AI API
5. Test with sample data
6. Share with your 4 users

The process should take less than 30 minutes from start to having a live application.