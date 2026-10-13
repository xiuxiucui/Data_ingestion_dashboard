# AI Workflow Report

## AI Tool Used

OpenAI Codex with GPT 5.6 sol was used as a development assistant to review the requirement.md, implement the Flask and Pydantic solution, and develop the unittests and documentation.

## Example Prompts

- After i have manually written the requirement.md, I have ask the agent to "Can you read through this requirement.md and propose a implementation plan"
- After i realized the logging is missing, i ask the agent to "Please implement logging, which capture the incoming request body for future debug use"
- For the Bonus UI part, i have asked the agent "Please generate a UI for the user to input json and send to each respective api end point, include sample input"
## Suggestion Accepted

I was not aware how to create run time  in memory pydantic model, when AI proposed to use `pydantic.create_model()`, i did some research and accepted it
The agent proposed locking mechanism when accessing the store, `self._lock()` was used, which is something i did not think of.

## Suggestion Rejected or Deferred
The AI suggested CQRS model, because the agent suspected there will be a less writing and more reading.  However, this will be a very light weight app, so i rejected it

## Validation
Unit testing was generated as proposed Test driven development, and it was reviewed. 
Manual test with Bruno calling the API endpoint
