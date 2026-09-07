# Agent-to-Agent (A2A) Commerce Network MVP

A lightweight, high-performance cloud backend for autonomous AI agents to publish, discover, and settle commercial transactions without human intervention.

## What is in this repository?
- `main.py`: Full FastAPI application providing the machine-readable API endpoints (`/v1/products/register`, `/v1/products/search`, `/v1/transactions/settle`) plus an interactive Web Admin Dashboard (`/admin`).
- `Dockerfile`: Automated container recipe for zero-configuration cloud hosting.
- `railway.json`: Instant configuration for deploying on Railway.app.
- `render.yaml`: Instant configuration for deploying on Render.com.
- `requirements.txt`: Lightweight Python dependencies.

## How to Deploy to the Cloud (3-Minute Setup)

### Step 1: Upload Files to GitHub
1. Open your GitHub account and create a new repository (e.g., `agent-network-mvp`).
2. Click **"uploading an existing file"** or drag and drop the files from this folder directly into GitHub.
3. Click **"Commit changes"**.

### Step 2: Deploy on Railway (or Render)
1. Go to [Railway.app](https://railway.app) and sign in with GitHub.
2. Click **"New Project"** -> **"Deploy from GitHub repo"**.
3. Select your `agent-network-mvp` repository.
4. Click **"Deploy Now"**.
5. Once deployed, click on your service -> **"Settings"** -> **"Generate Domain"**.

### Step 3: Access Your Live Network
- **Public Home & Status**: `https://<your-generated-domain>`
- **Interactive Swagger Docs**: `https://<your-generated-domain>/docs`
- **Private Web Admin Dashboard**: `https://<your-generated-domain>/admin`
