# Intelligence Briefing System

A beginner-friendly guide to installing, running, and understanding this project.

---

## What Does This Project Do?

The Intelligence Briefing System is an automated research assistant. You give it
a topic — for example, "climate change policy" — and it:

1. Reads a list of websites from a file called `sources.txt`
2. Visits each website and downloads the article text
3. Summarises each article into a few sentences
4. Identifies the most important claims and checks whether they are supported
5. Writes a professional briefing report combining everything it found
6. Optionally emails that report to you

All of this happens automatically. You just type one command and read the result.

---

## How the Planner–Worker Architecture Works

This project is organised like a small team of specialists, each with one job.

```
You type a topic
       │
       ▼
  [ Planner ]          Decides what to research and in what order
       │
       ▼
  [ Orchestrator ]     The manager — tells each worker what to do and when
       │
       ├──▶ [ Web Collector ]   Fetches articles from the URLs in sources.txt
       │
       ├──▶ [ Summarizer ]      Condenses each article into 3–5 sentences
       │
       ├──▶ [ Verifier ]        Extracts key claims and checks them against evidence
       │
       ├──▶ [ Writer ]          Combines everything into a final briefing report
       │
       └──▶ [ Emailer ]         Sends the report to your inbox (optional)
```

Each worker is a separate Python file inside the `workers/` folder. Results are
saved automatically to a local database file (`briefing.db`) so nothing is lost.

---

## Project Structure

```
workeragent/
│
├── orchestrator.py          ← Run this to start the system
├── planner.py               ← Creates the research plan
├── emailer.py               ← Sends the report by email
├── sources.txt              ← List of websites to read (edit this)
├── briefing.db              ← Database created automatically on first run
│
├── workers/
│   ├── web_collector.py     ← Downloads articles
│   ├── summarizer.py        ← Summarises articles
│   ├── verifier.py          ← Checks claims
│   └── writer.py            ← Writes the final report
│
├── store/
│   └── sqlite_store.py      ← Saves all data to the database
│
├── .env                     ← Your private API keys (you create this)
├── .env.example             ← Template showing what goes in .env
├── Dockerfile               ← For running in Docker
└── requirements.txt         ← Python packages needed
```

---

## STEP 1 — Install Python

If you do not have Python installed:

1. Go to https://www.python.org/downloads/
2. Download the latest version (3.11 or newer)
3. Run the installer — tick **"Add Python to PATH"** before clicking Install

To check Python is working, open PowerShell and type:

```powershell
python --version
```

You should see something like `Python 3.11.9`.

---

## STEP 2 — Download the Project

If you have Git installed:

```powershell
git clone https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
cd YOUR-REPO-NAME
```

Or simply download and unzip the project folder, then open PowerShell inside it:

```powershell
cd C:\Users\YourName\Downloads\workeragent
```

---

## STEP 3 — Install Dependencies

In PowerShell, from inside the project folder, run:

```powershell
pip install -r requirements.txt
```

This installs all the Python packages the project needs. You only need to do
this once.

---

## STEP 4 — STEP: ADD YOUR API KEY

The system uses OpenAI to read and analyse articles. You need a free API key.

### Get an OpenAI API key

1. Go to https://platform.openai.com/api-keys
2. Sign in or create a free account
3. Click **Create new secret key**
4. Copy the key — it starts with `sk-`

### Create your .env file

1. In the project folder, find the file called `.env.example`
2. Make a copy of it and name the copy exactly `.env` (no .txt extension)
3. Open `.env` in Notepad and replace the placeholder values with your real ones:

```
OPENAI_API_KEY=sk-your-real-key-here
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-gmail@gmail.com
SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_TO=recipient@example.com
```

Save the file. You are now ready to run the system.

> **Important:** Never share your `.env` file with anyone. It contains private
> keys that give access to paid services.

---

## STEP 5 — Edit sources.txt

`sources.txt` is the list of websites the system will read. Open it in Notepad
and add one URL per line:

```
https://www.bbc.com/news
https://apnews.com
https://www.reuters.com
```

Rules:
- One URL per line
- Lines that start with `#` are ignored (use them for notes)
- Use full URLs including `https://`

You can add as many or as few sources as you like. Start with 2–3 while you are
getting familiar with the system.

---

## STEP 6 — Run the Application

Open PowerShell in the project folder and run:

```powershell
python orchestrator.py "your research topic"
```

Replace `"your research topic"` with whatever you want to research. Examples:

```powershell
python orchestrator.py "artificial intelligence regulation"
python orchestrator.py "renewable energy trends 2025"
python orchestrator.py "global food security"
```

The system will print its progress as it works through each step, then display
the finished briefing report in the terminal.

### Optional flags

Send the report to an email address:

```powershell
python orchestrator.py "your topic" --email you@example.com
```

Hide the step-by-step progress and only show the final report:

```powershell
python orchestrator.py "your topic" --quiet
```

---

## STEP 7 — Enable Email Delivery

To have the report emailed to you automatically, you need a Gmail App Password.
This is different from your regular Gmail password.

### Set up a Gmail App Password

1. Go to your Google Account at https://myaccount.google.com
2. Click **Security** in the left menu
3. Under "How you sign in to Google", make sure **2-Step Verification** is ON
4. Go to https://myaccount.google.com/apppasswords
5. Under "App name", type `BriefingSystem` and click **Create**
6. Google will show a 16-character password like `abcd efgh ijkl mnop`
7. Copy it exactly, spaces included

### Add the password to your .env file

Open your `.env` file and fill in:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-gmail@gmail.com
SMTP_APP_PASSWORD=abcd efgh ijkl mnop
EMAIL_TO=the-address-to-send-to@example.com
```

Now run the system normally. The report will be emailed automatically when it
finishes.

---

## STEP 8 — Read the Output Files

### Terminal output

While the system runs, it prints its progress:

```
[1/5] Creating research plan...
[2/5] Collecting articles from sources.txt...
  Fetching: https://www.bbc.com/news
    Saved: BBC News - Home
[3/5] Summarizing articles...
[4/5] Verifying key claims...
[5/5] Writing briefing report...

============================================================
  BRIEFING REPORT
============================================================

EXECUTIVE SUMMARY
...
```

The finished report appears in full at the end.

### briefing.db — the database

Every run is saved to `briefing.db`, a SQLite database in the project folder.
You can open it with a free tool called **DB Browser for SQLite**:

1. Download from https://sqlitebrowser.org/dl/
2. Open `briefing.db`
3. Browse these tables:

| Table | What it contains |
|---|---|
| `runs` | One row per run — topic, date, status |
| `articles` | The raw text fetched from each URL |
| `summaries` | The AI-generated summary for each article |
| `verifications` | Each claim and its verdict |
| `reports` | The final briefing report text |

---

## Running with Docker

Docker lets you run the system inside a container without installing Python or
any packages on your machine.

### Install Docker Desktop

Download from https://www.docker.com/products/docker-desktop/ and run the
installer.

### Build the container image

Run this once from inside the project folder:

```powershell
docker build -t briefing-system .
```

### Run the container

```powershell
docker run --rm --env-file .env briefing-system "your research topic"
```

Send the report by email:

```powershell
docker run --rm --env-file .env briefing-system "your research topic" --email you@example.com
```

### Persist data between runs

By default, the database is lost when the container exits. To keep it, and to
use your local `sources.txt`, add volume mounts:

```powershell
docker run --rm `
  --env-file .env `
  -v "${PWD}/sources.txt:/app/sources.txt" `
  -v "${PWD}/briefing.db:/app/briefing.db" `
  briefing-system "your research topic"
```

---

## Deploying to GitHub

Putting your project on GitHub keeps it backed up and makes it easy to share
or continue working on another computer.

> **Before you start:** Make sure your `.env` file exists and that `.gitignore`
> lists `.env`. Your private API keys must never be uploaded to GitHub.

### Step 1 — Create a repository on GitHub

1. Go to https://github.com and sign in (or create a free account)
2. Click the **+** button in the top-right corner and choose **New repository**
3. Give it a name, e.g. `intelligence-briefing`
4. Leave it set to **Private** if you do not want it public
5. Do **not** tick "Add a README" — you already have one
6. Click **Create repository**
7. Copy the repository URL shown on the next page, e.g.
   `https://github.com/your-username/intelligence-briefing.git`

### Step 2 — Open PowerShell in the project folder

```powershell
cd C:\Users\YourName\OneDrive\AIAlchemy\workeragent
```

### Step 3 — Initialise Git

```powershell
git init
```

### Step 4 — Stage all files

```powershell
git add .
```

### Step 5 — Create the first commit

```powershell
git commit -m "Initial commit"
```

### Step 6 — Connect to GitHub

Paste the URL you copied in Step 1:

```powershell
git remote add origin https://github.com/your-username/intelligence-briefing.git
```

### Step 7 — Push to GitHub

```powershell
git branch -M main
git push -u origin main
```

Your code is now on GitHub. For future changes, use:

```powershell
git add .
git commit -m "Describe what you changed"
git push
```

---

## Troubleshooting

**"OPENAI_API_KEY is not set"**
Your `.env` file is missing or in the wrong folder. Make sure it is named
exactly `.env` (not `.env.txt`) and is in the same folder as `orchestrator.py`.

**"sources.txt not found"**
Make sure `sources.txt` exists in the project folder and contains at least one URL.

**"No articles were collected"**
The URLs in `sources.txt` may be unreachable. Try opening them in a browser
first to confirm they work.

**Email not arriving**
Check your spam folder. Make sure you used an App Password, not your regular
Gmail password. Confirm `SMTP_USER` and `EMAIL_TO` are both set in `.env`.

**"pip is not recognised"**
Python was not added to your PATH during installation. Re-run the Python
installer and tick "Add Python to PATH".

---

## Security Checklist

- [ ] `.env` file exists locally and contains your real keys
- [ ] `.env` is listed in `.gitignore` — confirm with `cat .gitignore`
- [ ] You have not pasted your API key into any chat or document
- [ ] Your GitHub repository is set to **Private** (or you are comfortable with it being public)
