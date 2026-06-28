<div align="center">
  <h1>📓 Notion Workspace Setup Guide</h1>
  <p>Step-by-step instructions to connect Resource Scrapper to your Notion databases.</p>
</div>

---

This guide walks you through setting up your Notion workspace and databases to connect with **Resource Scrapper**. 

Follow these steps to generate your Notion Integration Token, create a parent page, run the setup script to auto-generate the database structures, and configure your environment variables.

## 🛠️ Step-by-Step Setup

### Step 1: Create a Notion Integration

To allow the system to write to your Notion workspace, you need to create a Notion integration:

1. Go to the [Notion Developer Portal - My Integrations](https://www.notion.so/my-integrations).
2. Click the **`+ New integration`** button.
3. Configure the integration settings:
   - **Associated workspace**: Select the Notion workspace you want to use.
   - **Name**: Enter a name (e.g., `Resource Scrapper`).
4. Click **Submit** to create the integration.
5. In the **Secrets** tab, copy the **`Internal Integration Token`** (it starts with `secret_...`). 
   - *Keep this token secure! You will need it for your `.env` file.*

---

### Step 2: Create a Parent Page in Notion

Next, designate a parent page in your Notion workspace where the system will host all 5 of its databases.

1. Open Notion in your browser or desktop app.
2. Create a new page (e.g., name it `Knowledge Hub`).
3. Leave it completely blank (no templates, just an empty page).

---

### Step 3: Grant the Integration Access to the Page

Notion's security model requires you to explicitly share your page with the newly created integration.

1. Navigate to your newly created parent page (e.g., `Knowledge Hub`).
2. Click the **`...`** (three dots) menu in the top-right corner of the page.
3. Scroll down and click **`Add connections`** (or **`Connect to`**).
4. Search for your integration name (e.g., `Resource Scrapper`) and select it.
5. Confirm the access prompt. The integration now has permission to create sub-pages/databases under this page.

---

### Step 4: Extract the Parent Page ID

You need the unique page ID of your parent page to tell the setup script where to build the databases.

1. Copy the URL of your parent page from the browser address bar or by clicking the **Share** button and copying the link.
   - The URL will look like:
     `https://www.notion.so/myworkspace/Knowledge-Hub-a1b2c3d4e5f67890a1b2c3d4e5f67890`
2. Extract the **Page ID**, which is the 32-character hexadecimal string at the end of the URL.
   - In the example above, the Page ID is `a1b2c3d4e5f67890a1b2c3d4e5f67890`.

---

### Step 5: Run the Auto-Setup Script

The automated setup script connects to Notion, constructs the five required databases with exact schemas (including custom selection tags, checkboxes, and relation layouts), and prints out the resulting database IDs.

1. Navigate to the `knowledgeflow` directory:
   ```bash
   cd knowledgeflow
   ```
2. Activate your virtual environment and run the setup script, passing your **Page ID** and **Integration Token**:
   ```bash
   python scripts/setup_notion.py --page-id <extracted-page-id> --token <your-notion-token>
   ```

---

### Step 6: Update your `.env` File

Once the script runs successfully, it will print out a block of environment variables:

```text
============================================================
✅ All databases created! Copy these lines into your .env file:
============================================================
NOTION_SOURCES_DB_ID=a1b2c3d4e5f67890a1b2c3d4e5f67890
NOTION_RESOURCES_DB_ID=a1b2c3d4e5f67890a1b2c3d4e5f67890
NOTION_CATEGORIES_DB_ID=a1b2c3d4e5f67890a1b2c3d4e5f67890
NOTION_CREATORS_DB_ID=a1b2c3d4e5f67890a1b2c3d4e5f67890
NOTION_KNOWLEDGE_DB_ID=a1b2c3d4e5f67890a1b2c3d4e5f67890
============================================================
```

1. Open the `.env` file in the `knowledgeflow/` directory.
2. Insert your `NOTION_TOKEN`.
3. Paste the five generated database IDs into their corresponding fields.

You are now fully configured and ready to go! 🎉
