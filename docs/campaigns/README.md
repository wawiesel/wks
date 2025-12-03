A campaign is a cohesive plan to update the code carried out by
- one human director
- one orchestrator bot and
- 3 agent bots.

1. The director comes up with the idea for the campaign and tells the orchestrator
2. The orchestrator creates a branch and PR off main, e.g. 2025-12-03_test-refactor.
3. The orchestrator adds a file describing the goal of the campaign at docs/campaigns/<branch>/index.md
4. The orchestrator then creates a new branch and PR off of the campaign branch for agent bot 1 and adds
   docs/campaigns/<branch>/agent1/GOAL.md
5. The director then creates an agent bot 1 and assigns them the goal.
6. The orchestrator and director spin up the other 2 bots in the same way.
7. The orchestrator reviews the PRs of the agents and accepts them into the campaign branch.
8. When all agent bots are done, the orchestrator performs any final fixups on the campaign branch.
9. The orchestrator reads and summarizes all activity into a final docs/campaigns/<branch>/index.md,
   which should be the only document left in docs/campaigns/<branch> when merging back into main.
10. The director reviews the campaign branch to merge back into main.

RULES:

- The orchestrator should NOT DO ANY WORK directly on the agent branches. Only provide reviews.
- The agent bots should not do any work that is not directly related to their assigned goal.
- The agent bots should pull any work on the campaign branch to ensure they are up to date.
- The orchestrator may choose to pull from main or make minor corrections, e.g. to test harness or other
changes supporting all bots on the campaign branch.
