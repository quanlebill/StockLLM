from typing import Any, Optional, List, Tuple, Dict

class OllamaPrompt:
    def get__storing__build_graph_prompt(book_name:str, content:str) -> str:
        prompt = f"""You are a knowledge graph builder. Below are page-by-page summaries of a document titled "{book_name}".

                Your job is to identify the structure of this document as a graph:
                - The root entity is the book itself: "{book_name}"
                - Identify CHAPTERS, SUB-FIELDS, and smaller sub-topics
                - For each entity include: which pages it spans, a short summary (use the provided summaries), included child entities, and 10-15 keywords

                Return ONLY valid JSON in this exact format, no explanation:
                {{
                  "entities": {{
                    "{book_name}": {{
                      "page_index": [[0, N]],
                      "summary": "...",
                      "included_entities": ["Chapter1", "Chapter2"],
                      "keywords": ["keyword1", ...]
                    }},
                    "Chapter1": {{
                      "page_index": [[from, to]],
                      "summary": "...",
                      "included_entities": ["SubField1"],
                      "keywords": [...]
                    }}
                  }},
                  "relationships": [
                    {{"from": "{book_name}", "to": "Chapter1"}},
                    {{"from": "Chapter1", "to": "SubField1"}}
                  ]
                }}

                Page summaries:
                {content}"""

        return prompt

    def get__retrieval_pipeline__keypoint_prompt(page_range: str,topic:str, pages_text:str) -> str:
        prompt = f"""
                You are reading pages {page_range} from a document about '{topic}'.
                Extract the key points as a concise bullet list based on the provided Text
                Focus on actionable facts, definitions, thresholds, and rules. Be specific.
                
                Text:
                {pages_text}
            """
        return prompt

    def get__self_improvement__ollama_preprocess_prompt(user:str, answer:str, comment:str) -> str:
        has_comment = bool(comment and comment.strip())

        prompt = f"""
            You are a financial knowledge assistant processing a Q&A block for knowledge graph extraction.
            User question: {user}
            Original answer: {answer}
            """
        cause_affect_instruction = """
            Label each entity or condition as either:
               - [CAUSE]   — entity whose state/value triggers the policy (e.g. "GDP < -1.2%", "Inflation > 3%")
               - [AFFECTS] — entity that is changed or impacted as a result (e.g. "Fed Fund Rate cut 0.5%", "Bond yields fall")
               Format bullets as: "• [CAUSE] GDP < -1.2%" or "• [AFFECTS] Fed Fund Rate → -0.5%"
            """

        if has_comment:
            prompt += f"""
            Comment/correction: {comment}
    
            Task:
            1. Rewrite the answer incorporating the correction from the comment. Keep it concise and factual.
            2. Extract ALL key information from the corrected answer as a bullet list. Include:
               - Numerical thresholds and magnitudes (e.g. "GDP < -1.2%", "rate +0.5%")
               - Directional relationships (e.g. "GDP falls → Fed cuts rates")
               - Conditional rules (e.g. "if inflation > 2% then Fed raises")
               - Named entities (indicators, institutions, sectors, instruments)
               - Time frames or qualifiers
            {cause_affect_instruction}
            Return ONLY valid JSON, no explanation:
            {{
              "fixed_answer": "...",
              "key_info": "• bullet 1\\n• bullet 2\\n..."
            }}
            """
        else:
            prompt += f"""
            No comment provided — the answer is assumed correct.
    
            Task:
            Extract ALL key information from the answer as a bullet list. Include:
               - Numerical thresholds and magnitudes (e.g. "GDP < -1.2%", "rate +0.5%")
               - Directional relationships (e.g. "GDP falls → Fed cuts rates")
               - Conditional rules (e.g. "if inflation > 2% then Fed raises")
               - Named entities (indicators, institutions, sectors, instruments)
               - Time frames or qualifiers
            {cause_affect_instruction}
            Return ONLY valid JSON, no explanation:
            {{
              "fixed_answer": "<copy the original answer unchanged>",
              "key_info": "• bullet 1\\n• bullet 2\\n..."
            }}
            """
        return prompt

    def get__docs_analysis__summraize_prompt(page_index:str, text:str) -> str:
        prompt = f"""
            Summarize the following page content concisely. 
            Focus on key concepts, facts, and information. Be brief but complete
            
            Text from page #{page_index}:
            {text}
        """
        return prompt