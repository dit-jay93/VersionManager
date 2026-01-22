# Versioned File Manager  
## v0.1 Functional Prototype – AI Code Agent Work Brief

> **Target Audience:** AI Code Agent (autonomous or assisted)  
> **Goal:** Build a runnable functional prototype to validate core concepts  
> **Timeline:** 7 days  
> **Platform:** macOS (primary), Windows-compatible architecture

---

## 1. Project Intent (Non-negotiable)

This project is **not** about UI polish or feature completeness.

The sole objective is to **verify that a document-oriented version management concept works in practice**, using a real, interactive desktop application.

Success is defined by:
- Seeing files in a list
- Creating versions with commit messages
- Detecting file modification
- Inspecting version history visually

Anything not directly serving this validation is **out of scope**.

---

## 2. Constraints & Ground Rules

### Must
- Desktop application
- Local-only (no network, no cloud)
- Deterministic behavior
- Clear separation between UI and logic

### Must NOT
- Implement full design system
- Optimize performance
- Implement collaboration features
- Over-engineer abstractions

---

## 3. Scope of Implementation (v0.1)

### 3.1 Application Layout

- Single main window
- 3-column layout:
  - **Sidebar** (static navigation placeholder)
  - **File List** (central)
  - **Inspector** (right panel, context-sensitive)

No visual effects required. Use default widgets.

---

### 3.2 File Registration Flow

**Trigger**
- User selects “Add File”

**Steps**
1. Native file picker opens
2. User selects a local file
3. System generates:
   - Display Name (from filename)
   - Internal file ID
4. Commit message input is **mandatory**
5. On confirmation:
   - File metadata stored
   - Version `v1` created
6. On cancel:
   - No data persisted (full rollback)

---

### 3.3 Version Model (Minimal)

Each registered file has:

- One or more versions
- Exactly **one commit message per version**
- No threaded comments
- No edits to commit messages after creation

Displayed fields:
- Version number (`v1`, `v2`…)
- Commit title
- Created timestamp

---

### 3.4 File Change Detection

Detection logic:
- Compare `file_size` and `modified_time`
- If changed:
  - Status becomes `MODIFIED`
- Otherwise:
  - Status remains `OK`

No hashing required at this stage.

---

### 3.5 Inspector Panel

Displays information for the currently selected file:

- Display Name (read-only)
- File path
- Current status (`OK` / `MODIFIED`)
- Version list

Inspector updates dynamically based on file selection.

---

### 3.6 Job / Task Feedback (Minimal)

When a verification action is triggered:
- Show textual state only:
  - “Verifying…”
  - “Done”

No progress bars, cancellation, or concurrency handling.

---

## 4. Explicitly Out of Scope

The following are **intentionally excluded**:

- Visual design (Glass, Dark mode, theming)
- Tag system
- Search
- Restore
- Relink
- Open-with rules
- Favorites
- Settings
- Export / Report
- Team / Sync features

---

## 5. Data Model (Minimal SQLite)

### Required Tables

#### files
- id (string / uuid)
- display_name
- file_path
- file_size
- modified_time
- status
- created_at

#### versions
- id
- file_id (FK)
- version_number
- commit_message
- created_at

> No migrations, no advanced constraints required.

---

## 6. Non-Functional Requirements

- App must launch without errors
- State must persist across restarts
- Crashes are unacceptable
- Edge cases can be ignored unless fatal

---

## 7. Development Timeline (7 Days)

### Day 1
- Project setup
- Basic window + layout skeleton

### Day 2
- File selection & registration logic
- SQLite persistence

### Day 3
- Version creation (`v1`)
- Commit message enforcement

### Day 4
- File list rendering
- Inspector binding

### Day 5
- Modification detection logic
- Status updates

### Day 6
- Basic task feedback
- Bug fixing

### Day 7
- Manual testing
- Cleanup
- Validation against success criteria

---

## 8. Definition of Done

The prototype is considered **complete** if:

- Files can be registered
- Versions appear correctly
- File modification is detected
- Inspector reflects correct state
- App can be used for basic evaluation

No further polish is required.

---

## 9. Post-Prototype Direction

After validation:
- UI/UX refinement
- Component sizing
- Tagging, search, relink
- Dark mode
- Team features (optional)

---

## 10. Instruction to AI Code Agent

> Prioritize correctness and clarity over elegance.  
> Do not invent features.  
> Follow this document strictly.
