# WKS Campaigns

A **Campaign** is a cohesive, strategic effort to update the WKS codebase, executed by a coordinated team of a human Director and AI Agents.

## Roles

*   **Director** (Human): Defines the campaign vision, sets goals, creates agents, and approves the final merge.
*   **Orchestrator** (AI): Manages the campaign lifecycle, coordinates agents, reviews Pull Requests, and maintains campaign documentation.
*   **Agents** (AI): Autonomous workers that execute specific tasks assigned by the Director or Orchestrator.

## Workflow Lifecycle

### 1. Initialization
1.  **Director** conceives the campaign idea.
2.  **Orchestrator** creates a new branch off `main` following the naming convention: `YYYY-MM-DD_campaign-name` and creates a PR.
3.  **Orchestrator** initializes the campaign documentation at `docs/campaigns/<branch>/index.md`, defining the goals and scope.

### 2. Delegation
1.  **Orchestrator** identifies subtasks and creates branches and PRs for agents (e.g., adding `docs/campaigns/<branch>/agent1/GOAL.md` only on that branch).
2.  **Director** instantiates Agent bots and assigns them to their respective tasks/branches.

### 3. Execution & Review
1.  **Agents** perform work on their assigned branches.
2.  **Agents** ensure they stay up-to-date with the campaign branch.
3.  **Orchestrator** reviews Agent PRs, requests changes if necessary, and merges them into the campaign branch.
    *   *Note: Orchestrator does not push code to agent branches directly.*

### 4. Completion
1.  **Orchestrator** performs final integration checks and fixups on the campaign branch.
2.  **Orchestrator** summarizes all activity in the final `docs/campaigns/<branch>/index.md`.
3.  **Director** reviews the campaign branch and merges it back into `main`.

## Rules of Engagement

*   **Orchestrator Authority**: The Orchestrator manages the `campaign` branch. It should not modify `agent` branches directly.
*   **Agent Focus**: Agents must strictly adhere to their assigned `GOAL.md`.
*   **Synchronization**: All bots must regularly pull from the upstream campaign branch to minimize conflicts.
*   **Intervention**: The Orchestrator may make minor corrections (e.g., to test harnesses) directly on the campaign branch to unblock agents.
