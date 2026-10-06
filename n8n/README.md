# 🔗 n8n Workflows Setup & Integration Guide

This directory contains two pre-configured, importable n8n workflows designed to seamlessly connect your FastAPI Multi-Agent Crew with an n8n Form trigger and Email/Google Docs delivery.

---

## 📁 Workflow Files Included

1. **`research_request_workflow.json`**:
   - **Trigger**: n8n Form Trigger with interactive fields (Topic, Report Type, Questions, Audience, Depth, Email).
   - **Action**: Sends HTTP POST request to FastAPI (`http://localhost:8000/research`) with `X-API-Key`.
   - **Response**: Displays immediate user confirmation on form submit.

2. **`report_delivery_workflow.json`**:
   - **Trigger**: Webhook listener (`POST http://localhost:5678/webhook/report-delivery`).
   - **Actions**:
     - Sends beautifully styled HTML report via **Gmail**.
     - (Optional) Creates a formatted Google Document with the report markdown in **Google Docs**.

---

## 🚀 Step-by-Step Setup Guide

### Step 1: Launch n8n Locally
Open your terminal and run:
```bash
npx n8n
```
*n8n will start locally and open in your browser at: **`http://localhost:5678`***.

---

### Step 2: Import Workflows into n8n
1. Open n8n (`http://localhost:5678`).
2. In the top-left menu, click **Workflows** ➔ **Add Workflow** ➔ Click the **three dots (...)** menu in the top-right corner.
3. Select **Import from File**.
4. Select `n8n/research_request_workflow.json`.
5. Repeat for `n8n/report_delivery_workflow.json`.

---

### Step 3: Connect Credentials in n8n

#### A. Gmail Credentials
1. Open the **"Report Delivery"** imported workflow.
2. Double-click the **Gmail** node.
3. Under **Credential for Gmail**, click **Create New Credential**.
4. Select **Gmail OAuth2 API**.
5. Follow n8n's screen prompt to authenticate with your Google/Gmail account.
6. Click **Save**.

#### B. Google Docs Credentials (Optional)
1. Double-click the **Google Docs** node.
2. Select **Create New Credential** ➔ **Google Docs OAuth2 API**.
3. Authenticate with your Google account and save.

---

### Step 4: Configure Webhook URL in `.env`
1. Open the **"Report Delivery"** workflow in n8n.
2. Click on the **Report Delivery Webhook** node.
3. Copy the **Production Webhook URL** (e.g., `http://localhost:5678/webhook/report-delivery`).
4. Open your `.env` file in the main project folder and update:
   ```env
   N8N_DELIVERY_WEBHOOK_URL=http://localhost:5678/webhook/report-delivery
   ```

---

### Step 5: Activate Workflows
1. In the top-right corner of both workflows in n8n, toggle the **Active** switch to **ON**.
2. Open the **Form URL** from the "Research Request" workflow to test submitting a brief!

---

## 🇵🇰 Quick Guide in Roman Urdu

1. **n8n Start Karen:** Terminal mein `npx n8n` chalayein.
2. **Workflows Import Karen:** `http://localhost:5678` par ja kar dono `.json` files ko n8n mein Import from File se load karen.
3. **Gmail Connect Karen:** Report Delivery workflow mein Gmail node open karke Google account sign-in karen.
4. **Webhook URL Copy Karen:** Webhook node se URL copy karke `.env` mein `N8N_DELIVERY_WEBHOOK_URL` mein paste karen.
5. **Workflows Active Karen:** Top-right par Toggle Active switch ko ON karen.
