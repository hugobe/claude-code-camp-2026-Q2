# Preweek Technical Documentation

## Technical Goal
- To understand the difference between a Skill, a Code Agent and Custom Agents.
- To set up everything: tbaMUD setup and playable connection for the Agent.
- Get an overview of the codebase, especially the MUD to be able to navigate around.

## Technical Uncertainty
- I'm uncertain whether a coding agent can reliably accomplish untypical tasks like playing a mud because it is using coding focused loops.
- I'm uncertain if running an agent to play the MUD will get too expensive and use too many tokens.

## Technical Hypotheses
- I expect that achieving reliable results requires more expensive and capable models as driver for the agent.
- I think building a basic agent will be easier I expect, but I'm not sure if a simple agent will be capable of accomplishing the tasks.

## Technical Observations
- A plain agent.md struggled to keep the player connected to the session, since it is based on a coding harness, it is used to only follow the instructions from the agent.md and creating and executing scripts, rather than interacting with a MUD.
- Skills achieved noticeably better results than an agent.md.
- Once you have a good and defined skill, even simpler and cheaper models can achieve good results.
- Markdown files become unreliable as memory for this case, because they become too large, making it harder for the agent to navigate and stay accurate

## Technical Conclusions
- A Skill is a defined set of tasks and instructions you can give any agent, which shows it what it's able to do and how to do it. 
- A Code Agent runs on a harness that's specialized for coding tasks.
- A Custom Agent is an agent with a specialized harness, tailored to a specific use-case.
- My hypothesis that achieving reliable results requires more expensive and capable models did not hold up, a good skill mattered more than the model.
- A coding harness is highly optimized for coding tasks, not for efficiently playing a game like tbaMUD. 
- Generic Markdown files work as a simple memory storage for simple tasks, but more complex and specialized use-cases need more specialized data storage.

## Key Takeaway
The harness you build your agent on top of defines what it's good at, a coding harness won't be able to play a game efficiently, even if it is able to run it and interact.

