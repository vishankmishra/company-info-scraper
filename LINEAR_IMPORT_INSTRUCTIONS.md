# Linear Import Instructions

## 📁 File Ready
**File:** `linear_import.csv`  
**Contains:** 30 issues (1 Epic + 6 Phases + 23 Subtasks)  
**Total Story Points:** 89

---

## 🚀 How to Import (One-Time Upload)

### Step 1: Access Linear Import
1. Open your Linear workspace
2. Click on your **Team name** in the sidebar
3. Go to **Settings** → **Import** (or directly go to `https://linear.app/[your-team]/settings/import`)

### Step 2: Upload CSV
1. Click **"Import from CSV"**
2. Select the `linear_import.csv` file
3. Linear will show a preview of the data

### Step 3: Map Columns (Important!)
Linear will ask you to map CSV columns to Linear fields. Use this mapping:

| CSV Column | Map to Linear Field |
|------------|---------------------|
| Title | **Title** |
| Description | **Description** |
| Status | **Status** |
| Priority | **Priority** |
| Estimate | **Estimate** (Story Points) |
| Labels | **Labels** |
| Parent | **Parent Issue** |
| Assignee | **Assignee** (leave empty or map to yourself) |
| Due Date | **Due Date** (leave empty for now) |

### Step 4: Configure Import Settings
- ✅ **Create parent issues if they don't exist** (IMPORTANT - This creates the hierarchy)
- ✅ **Create labels if they don't exist**
- ✅ **Link parent-child relationships**

### Step 5: Review & Import
1. Review the preview - you should see:
   - 1 Epic (Corporate Scraper)
   - 6 Phase issues (children of Epic)
   - 23 Subtasks (children of Phases)
2. Click **"Import"**
3. Wait for completion (~30 seconds)

### Step 6: Verify
After import, check:
- ✅ Epic issue exists with 89 story points
- ✅ 6 Phase issues linked as children
- ✅ 23 Subtasks linked to their phases
- ✅ Labels applied (backend, scraping, ml-llm, production, etc.)
- ✅ Story points set on all issues
- ✅ Status correctly set (Done, In Progress, Todo)

---

## 📊 What You'll Get

### Epic Structure
```
📦 Corporate Scraper - Complete Implementation (89 points)
├── ✅ Phase 1: Critical Reliability Fixes (13 points) - DONE
│   ├── ✅ PH1-S1: Increase Ollama Timeout (2 pts)
│   ├── ✅ PH1-S2: Add Retry Logic (3 pts)
│   ├── ✅ PH1-S3: Result Validation (3 pts)
│   └── ✅ PH1-S4: Fix Deprecated APIs (2 pts)
│
├── 🟡 Phase 2: Architecture Decoupling (16 points) - 75% DONE
│   ├── ✅ PH2-S1: Async LLM Service (5 pts)
│   ├── ✅ PH2-S2: Extraction Queue (5 pts)
│   ├── ✅ PH2-S3: Remove Subprocess (3 pts)
│   └── 🔄 PH2-S4: Consolidate LLM Code (3 pts)
│
├── 🟡 Phase 3: Dual-Path Scraping (15 points) - 60% DONE
│   ├── ✅ PH3-S1: Static Site Detector (3 pts)
│   ├── ✅ PH3-S2: Static Scraper (5 pts)
│   ├── 🔄 PH3-S3: Orchestrator Integration (3 pts)
│   └── 📋 PH3-S4: Browser Context Reuse (2 pts)
│
├── 🔴 Phase 4: Parallel Batch Processing (12 points) - 35% DONE
│   ├── 🔄 PH4-S1: Async Batch Processor (5 pts)
│   ├── ✅ PH4-S2: Concurrency Limits (3 pts)
│   └── 📋 PH4-S3: Parallel LLM Workers (5 pts)
│
├── 🟡 Phase 5: Google ADK Integration (13 points) - 65% DONE
│   ├── ✅ PH5-S1: ADK Dependency (2 pts)
│   ├── ✅ PH5-S2: ADK Agent Wrappers (5 pts)
│   └── 🔄 PH5-S3: ADK Workflow (5 pts)
│
└── 🟢 Phase 6: Production Hardening (20 points) - 70% DONE
    ├── ✅ PH6-S1: Health Check (3 pts)
    ├── ✅ PH6-S2: Graceful Shutdown (3 pts)
    ├── ✅ PH6-S3: JSON Logging (3 pts)
    ├── ✅ PH6-S4: Documentation (5 pts)
    └── ✅ PH6-S5: Integration Tests (5 pts)
```

### Labels Created
- `backend`
- `scraping`
- `ml-llm`
- `production`
- `phase-1` through `phase-6`
- `reliability`
- `config`
- `llm`
- `validation`
- `quality`
- `architecture`
- `async`
- `performance`
- `testing`
- And more...

### Progress Summary
- **Total:** 89 story points
- **Completed:** 35 points (39%)
- **In Progress:** 19 points (21%)
- **Todo:** 35 points (40%)

---

## 🔧 Troubleshooting

### Issue: Parent-child relationships not working
**Fix:** Make sure you enabled "Create parent issues if they don't exist" during import.

### Issue: Labels not created
**Fix:** Enable "Create labels if they don't exist" in import settings.

### Issue: Story points not showing
**Fix:** Make sure "Estimate" column is mapped to "Estimate" or "Story Points" field in Linear.

### Issue: Some tasks missing
**Fix:** Check that the CSV has 30 rows (1 Epic + 6 Phases + 23 tasks). If not, re-download the CSV.

---

## ✨ After Import

### Recommended Next Steps:
1. **Assign yourself** to the "In Progress" and "Todo" tasks
2. **Set due dates** for upcoming week's tasks:
   - PH3-S4: Browser Context Reuse
   - PH4-S1: Batch Processor
   - PH4-S3: Parallel LLM Workers
3. **Create a Sprint/Cycle** in Linear and add the priority tasks
4. **Add the Epic to your Project** if you have a "Corporate Scraper" project in Linear

### Weekly Updates:
- Update task status as you complete them
- Add comments with blockers/learnings
- Adjust story points if estimates were off
- Move completed tasks to "Done"

---

## 📞 Need Help?

If the CSV import doesn't work:
1. Check Linear's documentation: https://linear.app/docs/import-from-csv
2. Verify your CSV file has all 30 rows
3. Make sure your Linear workspace has permission to import
4. Try importing to a test team first

---

**Ready to import! Just upload `linear_import.csv` once and you're all set! 🚀**











