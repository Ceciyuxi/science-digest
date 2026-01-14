# Science Digest - GitHub Setup Guide

Follow these steps to set up automatic daily updates and GitHub Pages hosting.

---

## Step 1: Create a GitHub Repository

1. Go to [github.com](https://github.com) and sign in (or create an account)

2. Click the **+** icon in the top-right corner and select **New repository**

3. Configure your repository:
   - **Repository name**: `science-digest` (or any name you prefer)
   - **Description**: "Daily science news digest"
   - **Visibility**: Public (required for free GitHub Pages)
   - Leave other options unchecked

4. Click **Create repository**

---

## Step 2: Push Your Code to GitHub

Open Terminal and run these commands:

```bash
# Navigate to the project folder
cd /Users/yuxiliu/Desktop/science-digest

# Initialize git repository
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Science Digest with GitHub Actions"

# Add your GitHub repository as remote (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/science-digest.git

# Push to GitHub
git branch -M main
git push -u origin main
```

**Note**: Replace `YOUR_USERNAME` with your actual GitHub username.

---

## Step 3: Enable GitHub Pages

1. Go to your repository on GitHub

2. Click **Settings** (gear icon in the top menu)

3. In the left sidebar, click **Pages**

4. Under **Build and deployment**:
   - **Source**: Select **GitHub Actions**

5. GitHub Pages is now configured!

---

## Step 4: Enable GitHub Actions

1. Go to your repository on GitHub

2. Click the **Actions** tab

3. If prompted, click **I understand my workflows, go ahead and enable them**

4. You should see the **Daily Science Digest** workflow listed

---

## Step 5: Run the Workflow Manually (First Time)

1. In the **Actions** tab, click **Daily Science Digest**

2. Click **Run workflow** (dropdown on the right)

3. Click the green **Run workflow** button

4. Wait for the workflow to complete (takes 2-3 minutes)

---

## Step 6: View Your Live Page

After the workflow completes successfully:

1. Go to **Settings** > **Pages**

2. You'll see a message: "Your site is live at..."

3. Click the link to view your Science Digest!

**Your URL will be**: `https://YOUR_USERNAME.github.io/science-digest/`

---

## How It Works

- **Daily Updates**: The workflow runs automatically every day at 8:00 AM UTC
- **Manual Updates**: You can trigger an update anytime from the Actions tab
- **GitHub Pages**: The site automatically updates after each workflow run

---

## Customizing the Schedule

To change when the digest updates, edit `.github/workflows/daily-digest.yml`:

```yaml
on:
  schedule:
    # Current: 8:00 AM UTC daily
    - cron: '0 8 * * *'
```

**Cron format**: `minute hour day month weekday`

Examples:
- `'0 14 * * *'` = 2:00 PM UTC (6:00 AM PST)
- `'0 12 * * *'` = 12:00 PM UTC (4:00 AM PST)
- `'0 6 * * *'` = 6:00 AM UTC (10:00 PM PST previous day)

---

## Troubleshooting

### Workflow fails with permission error

1. Go to **Settings** > **Actions** > **General**
2. Under "Workflow permissions", select **Read and write permissions**
3. Click **Save**

### Pages not deploying

1. Go to **Settings** > **Pages**
2. Make sure **Source** is set to **GitHub Actions**

### No articles showing

The script only fetches from free, open-access sources. If a source is temporarily unavailable, fewer articles may appear.

---

## Local Development

To run the script locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the script
python science_digest.py

# Run without opening browser
python science_digest.py --no-browser
```

---

## File Structure

```
science-digest/
├── .github/
│   └── workflows/
│       └── daily-digest.yml    # GitHub Actions workflow
├── science_digest.py           # Main Python script
├── science_digest.html         # Generated digest (local)
├── index.html                  # Generated digest (GitHub Pages)
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules
├── SETUP.md                    # This setup guide
└── README.md                   # Project documentation
```
