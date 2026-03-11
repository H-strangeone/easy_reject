# JobTracker

JobTracker is a small tool that scans your Gmail inbox and keeps track
of your job applications. It looks for job-related emails and organizes
them so you can see which companies you applied to, which ones rejected
you, and which ones invited you for assessments or interviews.

Everything runs locally on your machine and your emails are not sent
anywhere.

------------------------------------------------------------------------

# Running the Project

## 1. Install Python

Download and install Python (version **3.9 or newer**) from:

https://www.python.org/downloads/

During installation make sure you check:

Add Python to PATH

------------------------------------------------------------------------

## 2. Install Dependencies

Open the project folder and run:

pip install -r requirements.txt

Or double click:

install.bat

------------------------------------------------------------------------

## 3. Create Google OAuth Credentials

The app needs permission to read your Gmail inbox.

1.  Go to https://console.cloud.google.com
2.  Create a **new project**
3.  Open **APIs & Services → Library**
4.  Search for **Gmail API** and click **Enable**
5.  Go to **APIs & Services → Credentials**
6.  Click **Create Credentials → OAuth Client ID**
7.  Choose **Desktop App**
8.  Download the JSON file
9.  Rename it to:

credentials.json

10. Place it inside the project folder
11. Open **OAuth consent screen → Test Users**
12. Add your Gmail address

------------------------------------------------------------------------

## 4. Run the Application

You can start the app in two ways.

### Option 1

Double click:

Run JobTracker.bat

### Option 2

Run manually:

python app.py

------------------------------------------------------------------------

## 5. Configure the App

Inside the app:

1.  Open **Settings**
2.  Select your `credentials.json`
3.  Add the Gmail account(s) you want to scan
4.  Save
5.  Authorise them(here or anyways you have to do it later)
6.  If you want to use llama-3.1-8b-instant for better context then put in your llm api key i was using groq so the option there is for groq you can just change it to whatever you want to use just make some changes in app.py and gmail_scanner.py for those api functions , use claude, chatgpt or whatever you like and get it fixed for yourself , also you can use any other model cause it had a higher rpd .( this whole step is optional though you can skip this cause on llms the call intervals are a bit timetaking so its your call)
------------------------------------------------------------------------

## 6. Start the First Scan

Click:

Scan Gmail Now

Your browser will open for Google login.

Allow Gmail **read-only access**.

After that, the app will scan your emails and start tracking job
applications.

