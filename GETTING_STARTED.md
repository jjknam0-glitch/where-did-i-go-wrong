# Getting started

A step-by-step guide for running **Where Did I Go Wrong?** on your own computer, opening it on your phone, putting it online, and turning it into an app. No programming experience needed.

**Contents**

1. [Install the tools](#1-install-the-tools)
2. [Download the code](#2-download-the-code)
3. [Start the app](#3-start-the-app)
4. [Add an API key (to read handwriting)](#4-add-an-api-key-to-read-handwriting)
5. [Try it out](#5-try-it-out)
6. [Use it on your phone](#6-use-it-on-your-phone)
7. [Put it online](#7-put-it-online)
8. [Make it an app](#8-make-it-an-app)
9. [Publish the website](#9-publish-the-website)
10. [Troubleshooting](#10-troubleshooting)
11. [Starting by hand (if the start script doesn't work)](#11-starting-by-hand)

---

## 1. Install the tools

You need two free programs: **Python** (runs the math engine) and **Node.js** (runs the web app). Install each one once.

### Windows

1. **Python**
   1. Go to <https://www.python.org/downloads/> and click the yellow **Download Python 3.x** button.
   2. Open the downloaded file.
   3. **Important:** on the first screen, tick **"Add python.exe to PATH"** at the bottom.
   4. Click **Install Now**.
2. **Node.js**
   1. Go to <https://nodejs.org/> and download the **LTS** version.
   2. Open it and click **Next** through the installer, keeping the default options.
3. Restart your computer. This makes sure Windows finds both programs.

### Mac

1. **Python**
   1. Go to <https://www.python.org/downloads/> and click **Download Python 3.x**.
   2. Open the `.pkg` file and click through the installer.
2. **Node.js**
   1. Go to <https://nodejs.org/> and download the **LTS** version.
   2. Open the `.pkg` file and click through the installer.

### Check that it worked

Open a terminal:

- **Windows:** press the Windows key, type `PowerShell` and press Enter.
- **Mac:** press ⌘ Space, type `Terminal` and press Enter.

Type these two lines, pressing Enter after each:

```
python --version
node --version
```

On a Mac, use `python3 --version` instead of the first line.

You should see something like `Python 3.13.1` and `v22.11.0`. Python needs to be **3.11 or newer** and Node **20 or newer**.

If you get "not recognized" or "command not found", see [Troubleshooting](#10-troubleshooting).

---

## 2. Download the code

**Easiest: download a ZIP**

1. Open the project's page on GitHub.
2. Click the green **Code** button, then **Download ZIP**.
3. Unzip it somewhere easy to find, such as your Desktop. You'll get a folder like `where-did-i-go-wrong-main`.

**If you use Git**

```
git clone https://github.com/jjknam0-glitch/where-did-i-go-wrong.git
```

---

## 3. Start the app

### Windows

1. Open the project folder in File Explorer.
2. Double-click **`start.bat`**.
   - If Windows shows "Windows protected your PC", click **More info**, then **Run anyway**.

### Mac

1. Open Terminal.
2. Type `cd ` (with a space after it). Drag the project folder from Finder into the Terminal window, then press Enter.
3. Type this and press Enter:

   ```
   ./start.sh
   ```

### What happens next

- **The first run takes 3 to 5 minutes** while it downloads what the app needs. Later runs start in a few seconds.
- When you see **"Ready. Open http://localhost:5173"**, open <http://localhost:5173> in Chrome, Edge or Safari.
- Keep the terminal window open while you use the app.
- To stop the app:
  - **Mac:** press **Ctrl + C** in the terminal.
  - **Windows:** press **Ctrl + C**, then close the second window titled "API".

The app works straight away for typed problems and the built-in sample photos. To read your **own handwriting**, add an API key (next step).

---

## 4. Add an API key (to read handwriting)

The app uses an AI model only to *read* handwriting; the math itself is checked by a math engine on your computer. You need a key from **one** of these providers:

| Provider | Cost | Where to get a key |
|---|---|---|
| **Anthropic (Claude)**, recommended | Pay as you go; $5 of credit covers thousands of photos | <https://console.anthropic.com> |
| **Google Gemini** | Has a free tier | <https://aistudio.google.com/apikey> |
| OpenAI | Pay as you go | <https://platform.openai.com/api-keys> |

### Getting an Anthropic key

1. Go to <https://console.anthropic.com> and create an account.
2. Open **Billing** and add a small amount of credit, for example $5.
3. Open **API Keys** and click **Create Key**.
4. Copy the key. It starts with `sk-ant-`. Keep it private, like a password.

### Getting a Google Gemini key

1. Go to <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key** and copy it.

### Putting the key in the app

1. In the project folder, open the `backend` folder. Open the file named **`.env`** with Notepad (Windows) or TextEdit (Mac).
   - The start script created this file on its first run.
   - On a Mac, press ⌘ Shift . in Finder to show files whose names start with a dot.
2. Paste your key after the equals sign, with no spaces.
   - **Anthropic key:**

     ```
     ANTHROPIC_API_KEY=sk-ant-your-key-here
     ```

   - **Gemini key:** leave `ANTHROPIC_API_KEY=` empty. Delete the `#` at the start of the `# GEMINI_API_KEY=` line and paste your key:

     ```
     GEMINI_API_KEY=your-key-here
     ```

3. Save the file.
4. Stop the app and start it again (step 3).

To check that it worked, open <http://localhost:8000/api/health>. It should say `"transcription":true`.

---

## 5. Try it out

- **Check a sample:** on the home screen, tap one of the sample problems. You'll see the confirm screen, then the result with the broken line circled in red.
- **Type a problem:** tap **Type it instead** and enter your work one line per box.
- **Use the camera:** tap **Check a problem**. On a laptop the webcam works at `localhost`. Hold a page of worked math up to it; the camera takes the photo by itself once the page is sharp.
- **Try the paid features:** go to **More → Plans → Try Plus**. Payments aren't switched on, so every plan is free while you test.

---

## 6. Use it on your phone

Your phone and computer must be on **the same Wi-Fi**.

### Quick test (photo upload only)

1. When the app starts, the terminal shows a **Network** address, such as `http://192.168.1.23:5173`. Type that address into your phone's browser.
2. The upload button works this way.
3. The **live camera won't open**, because phones only allow the camera on secure (`https://`) sites.

### Full test with the live camera (free HTTPS tunnel)

1. Make a free account at <https://ngrok.com> and follow its instructions to install `ngrok`.
2. With the app running, open a **second** terminal and run:

   ```
   ngrok http 5173
   ```

3. ngrok prints an address like `https://abcd-12-34.ngrok-free.app`. Open it on your phone. The camera now works.

To use the app without your computer running, put it online (next step).

---

## 7. Put it online

You need a free [GitHub](https://github.com) account with the code in one of your repositories. If you downloaded a ZIP, create a new repository on GitHub and upload the files.

### Option A: one service on Render (simplest)

The included `Dockerfile` builds the whole app into a single service with one web address.

1. Sign up at <https://render.com> with your GitHub account.
2. Click **New → Web Service** and pick your repository.
3. Render detects the Dockerfile. Choose an instance type; **Free** works for trying it out.
4. Under **Environment Variables**, add `ANTHROPIC_API_KEY` (or `GEMINI_API_KEY`) with your key.
5. Click **Deploy**. After about 10 minutes you get an address like `https://where-did-i-go-wrong.onrender.com`.

Notes on the free tier:

- It sleeps after 15 minutes without visitors, so the first visit after that takes about a minute to wake it.
- Accounts and share links are erased whenever the service restarts. To keep them:
  1. Upgrade to a paid instance and attach a **Disk** mounted at `/data`.
  2. The app already stores its data there.

### Option B: Vercel for the web app + Render for the API

This setup loads faster for users, because Vercel serves the pages from a worldwide network.

1. **API on Render.**
   1. In Render, click **New → Blueprint** and pick your repository. It reads `render.yaml`.
   2. Fill in `ANTHROPIC_API_KEY`. Leave `CORS_ORIGINS` as `*` for now.
   3. Deploy. Note the address, e.g. `https://where-did-i-go-wrong-api.onrender.com`.
2. **Web app on Vercel.**
   1. Sign up at <https://vercel.com> with GitHub. Click **Add New → Project** and import your repository.
   2. Set **Root Directory** to `frontend`.
   3. Under **Environment Variables**, add `VITE_API_URL` with the Render address from step 1. Do not add a slash at the end.
   4. Deploy. You get an address like `https://where-did-i-go-wrong.vercel.app`.
3. **Lock the API to your site.**
   1. Back in Render, set `CORS_ORIGINS` to your Vercel address.
   2. Save. Render restarts the API.

### Option C: any computer with Docker

```
docker build -t wdigw .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-ant-... -v wdigw-data:/data wdigw
```

Then open <http://localhost:8000>.

---

## 8. Make it an app

There are two ways. Most people only need the first.

### Way 1: install it from the browser (free, nothing to submit)

The app is already a **Progressive Web App**: once installed, it gets its own icon, opens full screen without browser bars, and opens even without a connection. This works on any address that starts with `https://`, such as your Render or Vercel address.

**iPhone / iPad**
1. Open your app's address in **Safari**.
2. Tap the **Share** button (square with an arrow), scroll down and tap **Add to Home Screen**, then **Add**.

**Android**
1. Open the address in **Chrome**.
2. Tap **Install** when it's offered. Or open the **⋮** menu and choose **Install app**.

**Windows / Mac computer**
1. Open the address in **Chrome** or **Edge**.
2. Click the install icon at the right end of the address bar, or open the **⋮** menu and choose **Install**.

Inside the app, **More → Install the app** shows these same steps.

On iPhone, an app added to the Home Screen keeps its history separate from Safari. Sign in under **More → Account & settings** to carry your history over.

### Way 2: put it in the App Store and Google Play

This wraps the same web app in a native shell using [Capacitor](https://capacitorjs.com). The project already includes `frontend/capacitor.config.json`.

**What you need:**

| | iPhone (App Store) | Android (Google Play) |
|---|---|---|
| Computer | A Mac | Windows, Mac or Linux |
| Software | [Xcode](https://apps.apple.com/app/xcode/id497799835) (free) | [Android Studio](https://developer.android.com/studio) (free) |
| Developer account | [Apple Developer Program](https://developer.apple.com/programs/), $99/year | [Google Play Console](https://play.google.com/console), $25 once |

**Steps:**

1. **Put the API online first** (step 7). A phone app can't reach `localhost`. Note your API address.
2. **Install Capacitor.** In a terminal, inside the `frontend` folder:

   ```
   npm install @capacitor/core @capacitor/cli @capacitor/ios @capacitor/android
   ```

3. **Build the web app pointed at your online API.** Replace the addresses with yours:

   - **Mac:**

     ```
     VITE_API_URL=https://your-api.onrender.com VITE_PUBLIC_URL=https://your-app.vercel.app npm run build
     ```

   - **Windows PowerShell:**

     ```
     $env:VITE_API_URL="https://your-api.onrender.com"; $env:VITE_PUBLIC_URL="https://your-app.vercel.app"; npm run build
     ```

   Notes on the two addresses:

   - `VITE_PUBLIC_URL` is your website address. It makes share links open on the web.
   - With the single-service Render setup, both addresses are the same.

4. **Create the native projects** (first time only):

   ```
   npx cap add ios
   npx cap add android
   ```

5. **Allow the camera.**
   - **iPhone:** open `ios/App/App/Info.plist` and add, inside the main `<dict>`:

     ```xml
     <key>NSCameraUsageDescription</key>
     <string>Take a photo of your math work so we can check it.</string>
     <key>NSPhotoLibraryUsageDescription</key>
     <string>Choose a photo of your math work to check.</string>
     ```

   - **Android:** open `android/app/src/main/AndroidManifest.xml` and add, above the `<application` line:

     ```xml
     <uses-permission android:name="android.permission.CAMERA" />
     ```

6. **Let the app talk to your API.**
   1. In Render, add these to `CORS_ORIGINS`, separated by commas: `capacitor://localhost,https://localhost`.
   2. Keep your website address in the list too.
7. **Copy the web app into the native projects.** Run this after every change and rebuild:

   ```
   npx cap sync
   ```

8. **Open and run.**
   - Run `npx cap open ios`. In Xcode, pick your iPhone at the top and press ▶.
   - Run `npx cap open android`. In Android Studio, pick your phone and press ▶.
9. **App icons.** The icons are in `frontend/public/icons/`. To generate every size the stores need:
   1. Run `npm install -D @capacitor/assets`.
   2. Put a 1024×1024 PNG at `frontend/assets/icon.png`.
   3. Run `npx capacitor-assets generate`.
10. **Submit to the stores.** Build a release from Xcode or Android Studio and upload it to the store.
    - Apple: [App Store Connect](https://appstoreconnect.apple.com).
    - Google: the [Play Console](https://play.google.com/console).
    - Both stores ask for screenshots, a privacy policy URL and a content rating.
    - Because the app is for students, Apple's review also checks its Kids category and data rules. The in-app Privacy page is a good start for your privacy policy.

---

## 9. Publish the website

The `website/` folder has a ready-made product page, a single `index.html` plus an `img/` folder.

1. Open `website/index.html` in a text editor and find this line near the bottom:

   ```js
   const APP_URL = "";
   ```

2. Put your app's address between the quotes, e.g. `"https://where-did-i-go-wrong.vercel.app"`. Every "Open the app" button will then link there.
3. Publish the folder. Any of these is free:
   - **Netlify Drop:** go to <https://app.netlify.com/drop> and drag the `website` folder onto the page.
   - **Vercel:** import your repository again as a new project and set **Root Directory** to `website`.
   - **GitHub Pages:** in your repository go to **Settings → Pages**, choose your branch, and set the folder to `/website`. GitHub Pages only offers the `/` (root) or `/docs` folders, so rename `website` to `docs` first.

To preview it on your computer, double-click `website/index.html`.

---

## 10. Troubleshooting

| Problem | Fix |
|---|---|
| `python` or `node` is "not recognized" / "command not found" | Restart the computer after installing. On Windows, reinstall Python and tick **Add python.exe to PATH**. On a Mac, use `python3`. |
| Mac says `permission denied: ./start.sh` | Run `chmod +x start.sh` once, then `./start.sh` again. |
| "Port 5173 is already in use" or "address already in use" (8000) | The app is already running in another window. Close that window, or restart the computer. |
| The page says "Can't reach the server" | The API isn't running. Look at the terminal (on Windows, the "API" window) for a red error message. |
| Photos of my own work ask me to type every line | No API key is set, or it's wrong. Check `backend/.env` and <http://localhost:8000/api/health>. |
| Camera doesn't open on my phone | Phones need `https://`. Use ngrok (step 6) or the online version (step 7). Also check that the browser has camera permission in the phone's settings. |
| Camera doesn't open on my laptop | Allow the camera when the browser asks. Click the camera icon in the address bar to change it. |
| `pip install` fails on Windows with a "Microsoft Visual C++" message | Your Python is too new for one of the packages. Install Python 3.12 or 3.13 from python.org, delete the `backend\.venv` folder and run `start.bat` again. |
| Something else broke after an update | Delete `backend/.venv` and `frontend/node_modules`, then run the start script again for a clean install. |

---

## 11. Starting by hand

If the start script doesn't work on your computer, these are the same steps it runs. You need **two** terminal windows.

**Terminal 1: the API**

- **Windows (PowerShell)**, inside the project folder:

  ```
  cd backend
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  copy .env.example .env
  .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
  ```

- **Mac:**

  ```
  cd backend
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  cp .env.example .env
  .venv/bin/python -m uvicorn app.main:app --port 8000
  ```

**Terminal 2: the web app** (same on Windows and Mac), inside the project folder:

```
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

Next time, you only need the last line in each terminal, run from the same `backend` / `frontend` folders:

- Terminal 1:
  - Windows: `.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000`
  - Mac: `.venv/bin/python -m uvicorn app.main:app --port 8000`
- Terminal 2: `npm run dev`

For running the tests and how the app works inside, see the [README](README.md).
