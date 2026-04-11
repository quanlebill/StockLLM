## Task
- Creating a retrieval pipeline, reduce the need of multiple API call 

## Description
- Erase all the ncp connect to retrieve skill
- create 1 pipeline to retrieving only
- The function take in the following string:
  + Type: Either Question or Statement
  + If Question, specify Question Word
  + Entities List of Entities
  + Relationship: List of type of relationship with it direction. "relationship_type/relationship_direction"
- Example: 
```
{
"Query #1": {
                "Type": "Question",
                "Question Word": "How"
                "Entities": [GDP, Inflation]
                "Relationship":  ["affect/right"]
            }
"Query #2": {
                "Type": "Statement",
                "Entities": [GDP, Sector]
                "Relationship":  ["indicate/right"]
            }
}
```
- first lowercase entire string
- parse it back into list of question
```
["Question|How|GDP, Inflation|affect/right", "Statement|GDP, Sector|indicate/right"]
```
- Use each of these question to query
- Create a list of retrieving 
- Use each process, run concurrently for each retrieval:
  - Cache hit check
  - LightRAG query
- Pipeline for lightRAG query:
  - run a retrieval on document in the graph, selecting top 5 sub_field of a chapter of a book, get the summary
  - use the summary to do graph traversal in neo4j up to 2 connection, retrieve top 5 neighbors
  - The document may have document index specific, load this index, fork a processor, load these document page to ollam3 to pick keypoint then return
  - concatenate retrieval from graph traversal, and keypoint pick from document to return
- if the cache hit then we yield the information from cache first, tell LLM answer with cache while waiting for retrieval
- After that yield the answer

## Key Idea
- Agent do not have to call API multiple time, the retrieving pipeline is hard code
- Agent only call once to receive information
- If the information is unclear, ask the agent to format different question and run it again

# Workflow For Agent
- Ask the agent to use the string format above to create necessary improved queries for the user queries
- Ask it to call the skill with the formatted input
- Wait for result, if hit yield first, answer with it while waiting for full retrieval
- This is a fast way to response, make any changes if you think its necessary