## Tutor Bot Script

This is a script intended to be implemented into my fraternity's Discord bot. It posts a formatted message into a server that supports a system in which brothers can volunteer to tutor other brothers during a scheduled study session. 

The function is invoked by a command. When run, it will post a message structured as follows:

```text
Study Tables Preparation
Study Tables will be held on {date} at {place}.

Brothers need help with the courses listed below.
If you are able to tutor during Study Tables, please click the corresponding toggle button.

If you requested help, find a brother that is listed as a tutor for your course during Study Tables.

==============================
MECH-241 — Dr. Smith
• Assignment 1
• Quiz 2

Tutors:
demetri894

------------------------------
CHEM-132
• Midterm

Tutors:
—

==============================
```

Beneath the message, there are buttons that can be clicked to volunteer for a particular course.

---

## Prerequisites

- Python 3.12.4

---

## Running the program

### 1. Clone the repository

```bash
git clone https://github.com/demetri-0/discord-tutor-sign-up-bot.git
cd discord-tutor-sign-up-bot
```

### 2. Create a Python virtual environment

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create .env

Make a file named .env in the repo root:
```bash
DISCORD_TOKEN=your-bot-token-here
GUILD_ID=your-server-id-here
```

### 5. Add data storage
Make a file named sessions.json in discord-tutor-sign-up-bot/data.

### 6. Run the bot
```bash
python bot.py
```
