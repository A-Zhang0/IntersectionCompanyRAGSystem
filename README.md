# April Zhang — Portfolio

A 4-page static site: `index.html` (home), `projects.html`, `about.html`, `contact.html`,
sharing one `styles.css` and `script.js`. No build step — plain HTML/CSS/JS.

## 1. Put it on GitHub (no command line needed)

1. Go to github.com, sign in, click the **+** in the top right → **New repository**.
2. Name it `your-username.github.io` (replacing `your-username` with your actual GitHub
   username, exactly). This special name makes GitHub host it at that URL automatically.
   - If you'd rather keep it at a sub-path like `your-username.github.io/portfolio`, name
     it anything you like (e.g. `portfolio`) instead — same steps below, just a different URL.
3. Leave it **public**, don't add a README (you already have one), click **Create repository**.
4. On the new repo's page, click **uploading an existing file**.
5. Drag in every file from this folder (`index.html`, `projects.html`, `about.html`,
   `contact.html`, `styles.css`, `script.js`, `README.md`) and commit.
6. Go to **Settings → Pages** (left sidebar). Under "Build and deployment," set
   **Source** to `Deploy from a branch`, branch `main`, folder `/root`. Save.
7. Wait ~1 minute, then visit the URL GitHub shows you there. That's your live site.

Any time you want to update it: edit a file locally, or use GitHub's web editor (press
`.` on your repo page to open it in a browser-based VS Code), commit, and the live site
updates automatically within a minute or two.

## 2. Adding your research project and hackathon files

You don't need to put your full VS Code project into this same repo unless you want to —
most people either:

- **Link out**: keep your research/hackathon code in its own separate GitHub repo, and
  just link to it from `projects.html` (I've left `project-links` spots ready for this —
  add `<a href="https://github.com/you/repo-name">View code</a>` inside a project block).
- **Embed a folder**: create a `projects/` folder inside this portfolio repo, and put a
  trimmed-down version of each project inside (code + a short `README.md` per project),
  then link to `projects/roadway-rag/` etc. Good if you want everything in one place.

Either way, the easiest path from VS Code:
1. In VS Code, open the project folder.
2. Install the **GitHub Pull Requests and Issues** extension, or just use VS Code's
   built-in Source Control tab (the icon with branching lines).
3. Click "Publish to GitHub" — VS Code will create a new repo for you and push the code,
   or you can push into a subfolder of this portfolio repo if you'd rather.
4. Copy the resulting repo URL into `projects.html` where marked.

If you'd rather just hand me the files directly in this chat, I can write proper project
write-ups and wire up the links myself — just share them whenever you're ready.

## 3. Things still marked "edit me"

- `projects.html` — the hackathon project section (title, event, description, tags)
- `contact.html` — LinkedIn/GitHub links (commented out until you add them), and a
  `resume.pdf` file if you want the download button to work
- Anywhere you see a dashed gold box — that's a placeholder note to yourself

I intentionally left your phone number off the public site — the resume version is fine
for applications, but I'd avoid publishing a phone number on a page anyone on the internet
can find. Easy to add back if you disagree.
